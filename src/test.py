"""Diagnose why decumulate_ytd_flows isn't transforming cumulative rows.

Run from the same folder as B_database.py (your src/), or adjust the import.
It inspects AAPL operating_cash_flow (a known-cumulative case flagged at 279d)
and reports the exact field values the de-cumulation filter checks against.
"""

from contextlib import closing

import pandas as pd

import B_database


def main() -> None:
    with closing(B_database.get_connection()) as conn:
        df = pd.read_sql_query(
            "SELECT * FROM financial_facts WHERE ticker = 'AAPL' "
            "AND position = 'operating_cash_flow'",
            conn,
        )

    if df.empty:
        print("No AAPL operating_cash_flow rows found. Is the table populated?")
        return

    # Show the columns the de-cumulation filter actually reads.
    cols = [c for c in (
        "fact_end_date", "form", "statement_type",
        "duration_days", "selection_status", "value",
    ) if c in df.columns]

    missing_cols = {"form", "statement_type", "duration_days",
                    "selection_status", "fact_end_date"} - set(df.columns)
    if missing_cols:
        print(f"!! Columns the filter needs are MISSING from the table: {missing_cols}")
        print(f"   Actual columns present: {list(df.columns)}\n")

    df = df.sort_values("fact_end_date", ascending=False)
    print("AAPL operating_cash_flow rows (newest first):\n")
    print(df[cols].to_string(index=False))

    print("\n--- distinct values the filter keys on ---")
    if "form" in df.columns:
        print("form        :", sorted(df["form"].dropna().unique().tolist()))
    if "statement_type" in df.columns:
        print("statement_type:", sorted(df["statement_type"].dropna().unique().tolist()))
    if "selection_status" in df.columns:
        print("selection_status:", sorted(df["selection_status"].dropna().unique().tolist()))
    if "duration_days" in df.columns:
        print("duration_days dtype:", df["duration_days"].dtype)
        print("duration_days >130 count:", int((pd.to_numeric(
            df["duration_days"], errors="coerce") > 130).sum()))

    # Replicate the EXACT candidate filter from decumulate_ytd_flows.
    print("\n--- replicating the de-cumulation candidate filter ---")
    FLOW_STATEMENTS = ("income_statement", "cash_flow_statement")
    end = pd.to_datetime(df.get("fact_end_date"), errors="coerce")
    try:
        candidate = (
            df["form"].eq("10-Q")
            & df["statement_type"].isin(FLOW_STATEMENTS)
            & df["selection_status"].ne("missing")
            & pd.to_numeric(df["duration_days"], errors="coerce").notna()
            & end.notna()
        )
        print("rows matching the candidate filter:", int(candidate.sum()),
              "of", len(df))
        if candidate.sum() == 0:
            print(">> Filter matches NOTHING -> this is why de-cumulation "
                  "left the rows untouched.")
            print(">> Compare the distinct values above against what the "
                  "filter expects:")
            print("   form must be exactly '10-Q'")
            print("   statement_type must be 'income_statement' or "
                  "'cash_flow_statement'")
    except KeyError as exc:
        print(f">> Filter crashed on missing column: {exc}")


if __name__ == "__main__":
    main()