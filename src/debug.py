"""
fix_ytd_cash_flow.py

One script for the whole year-to-date (YTD) cash-flow fix:

  STEP 1  DETECT    - find FLOW positions (income statement + cash flow) whose
                      10-Q values are cumulative (a discrete quarter is ~90d; a
                      YTD Q2 ~180d, YTD Q3 ~270d). Detection is by DURATION, not
                      by ticker, so it generalises to any cumulative reporter.
  STEP 2  PREVIEW   - compute the discrete-quarter values, matching quarters
                      EXPLICITLY by fiscal quarter (Q1/Q2/Q3 from the period-end
                      month):
                          Q1 (month 3) : already discrete -> untouched
                          Q2 (month 6) : discrete = YTD_Q2 - YTD_Q1
                          Q3 (month 9) : discrete = YTD_Q3 - YTD_Q2
                      A quarter whose same-year baseline is missing (e.g. a first
                      window year with no Q1) is reported UNFIXABLE and never
                      de-cumulated against a wrong baseline.
  STEP 3  APPLY     - write discrete values back (only with --apply).
  STEP 4  VERIFY    - re-check that no cumulative rows remain.

SAFE BY DEFAULT - dry run prints everything and writes nothing:

    python fix_ytd_cash_flow.py                      # detect + preview only
    python fix_ytd_cash_flow.py --apply              # commit de-cumulation
    python fix_ytd_cash_flow.py --apply --drop-unfixable
        also delete the unfixable YTD rows so no cumulative value pollutes the
        discrete-quarter panel.

Applied rows get value / duration_days / fact_start_date updated to the discrete
quarter, and selection_status -> '<old>+decumulated' (audit trail, idempotent).
"""

from __future__ import annotations

import sys
from contextlib import closing

import pandas as pd

import B_database

FLOW_STATEMENTS = ("income_statement", "cash_flow_statement")
QUARTER_MAX_DAYS = 130                       # > this = cumulative
MONTH_TO_QUARTER = {3: 1, 6: 2, 9: 3, 12: 4}


def fmt(v) -> str:
    return "n/a" if v is None or pd.isna(v) else f"{v:,.0f}"


def load_flows(connection) -> pd.DataFrame:
    df = pd.read_sql_query("SELECT * FROM financial_facts", connection)
    if df.empty:
        return df
    df["fact_end_date"] = pd.to_datetime(df["fact_end_date"], errors="coerce")
    flows = df[
        df["selection_status"].ne("missing")
        & df["form"].eq("10-Q")
        & df["statement_type"].isin(FLOW_STATEMENTS)
        & df["fact_end_date"].notna()
        & df["duration_days"].notna()
        & (df["duration_days"] > 0)
    ].copy()
    flows["fiscal_year"] = flows["fact_end_date"].dt.year
    flows["quarter"] = flows["fact_end_date"].dt.month.map(MONTH_TO_QUARTER)
    flows["is_cumulative"] = flows["duration_days"] > QUARTER_MAX_DAYS
    return flows


def detect(flows: pd.DataFrame) -> set[str]:
    profile = (
        flows.groupby(["ticker", "position", "statement_type"])
        .agg(n=("duration_days", "size"),
             median_duration=("duration_days", "median"),
             max_duration=("duration_days", "max"))
        .reset_index()
    )
    profile["classification"] = profile["max_duration"].apply(
        lambda d: "YTD (cumulative)" if d > QUARTER_MAX_DAYS else "discrete"
    )
    ytd = profile[profile["classification"] == "YTD (cumulative)"]

    print("=" * 100)
    print("STEP 1  DETECT - cumulative flow positions (10-Q)")
    print("=" * 100)
    if ytd.empty:
        print("No YTD flow positions found. Nothing to de-cumulate.")
    else:
        print(ytd[["ticker", "position", "n", "median_duration", "max_duration"]].to_string(index=False))
    return set(ytd["position"].unique())


def compute(flows: pd.DataFrame, ytd_positions: set[str]) -> tuple[list[dict], list[dict]]:
    updates: list[dict] = []
    skipped: list[dict] = []
    target = flows[flows["position"].isin(ytd_positions)]

    for (ticker, position, fiscal_year), grp in target.groupby(["ticker", "position", "fiscal_year"]):
        by_q = {int(r["quarter"]): r for _, r in grp.iterrows()}
        for q in (2, 3):
            row = by_q.get(q)
            if row is None or not bool(row["is_cumulative"]):
                continue
            baseline = by_q.get(q - 1)
            if baseline is None or pd.isna(baseline["value"]) or pd.isna(row["value"]):
                skipped.append({
                    "id": row["id"], "ticker": ticker, "fiscal_year": fiscal_year,
                    "quarter": f"Q{q}", "period_end": row["fact_end_date"].date().isoformat(),
                    "ytd_value": row["value"], "reason": f"no Q{q - 1} baseline in {fiscal_year}",
                })
                continue
            updates.append({
                "id": row["id"], "ticker": ticker, "position": position,
                "fiscal_year": fiscal_year, "quarter": f"Q{q}",
                "period_end": row["fact_end_date"].date().isoformat(),
                "old_value": row["value"], "new_value": row["value"] - baseline["value"],
                "old_duration": int(row["duration_days"]),
                "new_duration": int((row["fact_end_date"] - baseline["fact_end_date"]).days),
                "new_start": baseline["fact_end_date"].date().isoformat(),
                "selection_status": row["selection_status"],
            })
    return updates, skipped


def preview(updates: list[dict], skipped: list[dict], drop_unfixable: bool) -> None:
    print("\n" + "=" * 100)
    print(f"STEP 2  PREVIEW - {len(updates)} quarter(s) to de-cumulate, {len(skipped)} unfixable")
    print("=" * 100)
    if updates:
        cols = ["ticker", "fiscal_year", "quarter", "period_end",
                "old_value", "new_value", "old_duration", "new_duration"]
        with pd.option_context("display.max_rows", None):
            print(pd.DataFrame(updates)[cols].to_string(
                index=False, formatters={"old_value": fmt, "new_value": fmt}))
        neg = sum(1 for u in updates if u["new_value"] < 0)
        if neg:
            print(f"\n{neg} discrete value(s) negative - legitimate for a net-outflow quarter.")
    if skipped:
        verb = "WILL DELETE" if drop_unfixable else "left as YTD"
        print(f"\nUNFIXABLE ({verb}):")
        print(pd.DataFrame(skipped)[
            ["ticker", "fiscal_year", "quarter", "period_end", "ytd_value", "reason"]
        ].to_string(index=False, formatters={"ytd_value": fmt}))


def apply(connection, updates: list[dict], skipped: list[dict], drop_unfixable: bool) -> None:
    cursor = connection.cursor()
    for u in updates:
        status = u["selection_status"]
        if not status.endswith("+decumulated"):
            status = f"{status}+decumulated"
        cursor.execute(
            "UPDATE financial_facts SET value=?, duration_days=?, fact_start_date=?, "
            "selection_status=? WHERE id=?",
            (u["new_value"], u["new_duration"], u["new_start"], status, u["id"]),
        )
    dropped = 0
    if drop_unfixable:
        for s in skipped:
            cursor.execute("DELETE FROM financial_facts WHERE id=?", (s["id"],))
            dropped += 1
    connection.commit()
    print(f"\nApplied {len(updates)} de-cumulation(s)"
          + (f", dropped {dropped} unfixable row(s)" if dropped else "") + " and committed.")


def verify(connection, ytd_positions: set[str]) -> None:
    print("\n" + "=" * 100)
    print("STEP 4  VERIFY")
    print("=" * 100)
    flows = load_flows(connection)
    remaining = flows[flows["position"].isin(ytd_positions) & flows["is_cumulative"]]
    if remaining.empty:
        print("No cumulative rows remain for the target positions. YTD issue closed.")
    else:
        print(f"{len(remaining)} cumulative row(s) still present (unfixable rows kept, or re-run needed):")
        print(remaining[["ticker", "position", "fiscal_year", "quarter", "duration_days"]].to_string(index=False))


def main() -> None:
    apply_changes = "--apply" in sys.argv
    drop_unfixable = "--drop-unfixable" in sys.argv

    with closing(B_database.get_connection()) as connection:
        flows = load_flows(connection)
        if flows.empty:
            print("No quarterly flow rows found - run the pipeline first.")
            return

        ytd_positions = detect(flows)
        if not ytd_positions:
            return

        updates, skipped = compute(flows, ytd_positions)
        preview(updates, skipped, drop_unfixable)

        if not updates and not (drop_unfixable and skipped):
            print("\nNothing to apply.")
            return

        if not apply_changes:
            print("\nDRY RUN only - nothing written. Re-run with --apply to commit.")
            if skipped and not drop_unfixable:
                print("Add --drop-unfixable to also delete the unfixable YTD rows.")
            return

        print("\n" + "=" * 100)
        print("STEP 3  APPLY")
        print("=" * 100)
        apply(connection, updates, skipped, drop_unfixable)
        verify(connection, ytd_positions)


if __name__ == "__main__":
    main()
