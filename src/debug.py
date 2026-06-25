"""
validate_data.py

One validator for the financial_facts table. Run after a pipeline run:

    python validate_data.py

Four layers, all offline:

  1. COVERAGE        - which (ticker, position) came back missing.
  2. IDENTITIES      - accounting relationships that must hold within a filing
                       (a break usually means a WRONG fact was selected).
  3. ANOMALIES       - scale jumps, bad durations, values frozen across filings.
  4. CONCEPT AUDIT   - which us-gaap/iXBRL concept each position actually resolved
                       to; flags concept DRIFT (a company using >1 concept for the
                       same position) and heavy FALLBACK selection (the clean
                       exact-period match failed). Also writes concept_map.csv:
                       a per-(ticker, position) concept + sample value table,
                       grouped so peers line up - paste a sector slice of this
                       into an AI and ask "do these position->concept mappings
                       look right for these companies?". (An AI without the
                       filings can judge PLAUSIBILITY, not correctness - it
                       catches gross mis-mappings, not subtle wrong-period picks.)

Outputs:
  - console summary
  - validation_flags.csv : one row per FAIL/REVIEW flag (the suspect rows)
  - concept_map.csv      : the concept audit / AI hand-off artifact

Real vs missing is distinguished by selection_status (not value == 0), because
missing values are stored as 0.
"""

from __future__ import annotations

from contextlib import closing

import pandas as pd

import B_database

REL_TOL = 0.01
ABS_TOL = 100_000
SCALE_JUMP_FACTOR = 50
FROZEN_MIN_FILINGS = 4
FALLBACK_SHARE_FLAG = 0.5           # >50% of a series resolved via a fallback branch
ANNUAL_DURATION = (300, 450)
QUARTERLY_DURATION = (70, 120)
RETRIEVED_METHODS = ("sec_companyfacts", "ixbrl_dimensional")
FILING_KEYS = ["ticker", "company_group", "form", "fiscal_period_end_date", "accession_number"]


def load_facts() -> pd.DataFrame:
    with closing(B_database.get_connection()) as connection:
        df = pd.read_sql_query("SELECT * FROM financial_facts", connection)
    if not df.empty:
        df["is_real"] = df["selection_status"].ne("missing")
    return df


def fmt(v) -> str:
    return "n/a" if v is None or pd.isna(v) else f"{v:,.0f}"


# ---------------------------------------------------------------- coverage ----
def coverage_report(df: pd.DataFrame) -> pd.DataFrame:
    missing = df[df["selection_status"].eq("missing")]
    if missing.empty:
        return pd.DataFrame(columns=["ticker", "position", "missing_filings"])
    return (
        missing.groupby(["ticker", "position"])["accession_number"].nunique()
        .reset_index(name="missing_filings")
        .sort_values(["ticker", "missing_filings"], ascending=[True, False])
    )


# -------------------------------------------------------------- identities ----
def to_wide(df: pd.DataFrame):
    values = df.pivot_table(index=FILING_KEYS, columns="position", values="value", aggfunc="first")
    real = (
        df.assign(is_real=df["is_real"].astype(float))
        .pivot_table(index=FILING_KEYS, columns="position", values="is_real", aggfunc="first")
        .fillna(0.0).astype(bool)
    )
    return values, real


def _cell(vrow, rrow, pos):
    if pos not in vrow.index or not bool(rrow.get(pos, False)):
        return None
    v = vrow[pos]
    return None if pd.isna(v) else float(v)


def _approx(a, b, scale):
    return abs(a - b) <= max(REL_TOL * abs(scale), ABS_TOL)


def check_identities(values, real) -> list[dict]:
    flags: list[dict] = []
    for key in values.index:
        vrow, rrow = values.loc[key], real.loc[key]
        ticker, _group, form, period_end, accession = key

        def g(p):
            return _cell(vrow, rrow, p)

        def flag(check, sev, detail):
            flags.append({"ticker": ticker, "fiscal_period_end_date": period_end, "form": form,
                          "accession_number": accession, "check": check, "severity": sev, "detail": detail})

        revenue, cost, gross = g("revenue"), g("cost_of_revenue"), g("gross_profit")
        operating, pretax, tax, net = g("operating_income"), g("income_before_tax"), g("income_tax"), g("net_income")
        assets, equity, cash = g("total_assets"), g("total_equity"), g("cash_and_cash_equivalents")
        std, ltd = g("short_term_debt"), g("long_term_debt")

        if None not in (gross, revenue, cost) and not _approx(gross, revenue - cost, revenue):
            flag("gross_profit = revenue - cost", "FAIL",
                 f"gp={fmt(gross)} vs rev-cost={fmt(revenue - cost)}")
        if None not in (net, pretax, tax) and not _approx(net, pretax - tax, pretax):
            flag("net_income ~ pretax - tax", "REVIEW",
                 f"ni={fmt(net)} vs pretax-tax={fmt(pretax - tax)} (NCI/preferred/discontinued)")
        if None not in (operating, gross) and operating > gross + max(REL_TOL * abs(gross), ABS_TOL):
            flag("operating_income <= gross_profit", "FAIL", f"op={fmt(operating)} > gp={fmt(gross)}")
        if revenue not in (None, 0):
            if gross is not None:
                gm = gross / revenue
                if gm < -0.05 or gm > 1.05:
                    flag("gross_margin in [0,1]", "FAIL", f"gross_margin={gm:.2%}")
                if operating is not None and operating / revenue > gm + REL_TOL:
                    flag("operating_margin <= gross_margin", "FAIL",
                         f"op_margin={operating / revenue:.2%} > gm={gm:.2%}")
        if assets is not None and assets <= 0:
            flag("total_assets > 0", "FAIL", f"total_assets={fmt(assets)}")
        if None not in (std, ltd, assets) and (std + ltd) > assets * (1 + REL_TOL):
            flag("total_debt <= total_assets", "FAIL", f"debt={fmt(std + ltd)} > assets={fmt(assets)}")
        if None not in (equity, assets) and assets > 0 and equity / assets > 1.05:
            flag("equity_ratio <= 1", "REVIEW", f"equity_ratio={equity / assets:.2%}")
        if None not in (cash, assets) and cash > assets * (1 + REL_TOL):
            flag("cash <= total_assets", "FAIL", f"cash={fmt(cash)} > assets={fmt(assets)}")

        loans = g("total_loans")
        parts = [g(p) for p in ("card_member_loans", "card_member_loans_held_for_sale", "other_loans")]
        if loans is not None and all(p is not None for p in parts) and not _approx(loans, sum(parts), loans):
            flag("total_loans = sum(components)", "FAIL", f"total={fmt(loans)} vs sum={fmt(sum(parts))}")
    return flags


# --------------------------------------------------------------- anomalies ----
def check_anomalies(df: pd.DataFrame) -> list[dict]:
    flags: list[dict] = []
    real = df[df["is_real"]].copy()

    flow = real[real["statement_type"].isin(["income_statement", "cash_flow_statement"])]
    for _, r in flow.iterrows():
        d = r.get("duration_days")
        if pd.isna(d) or r.get("value") in (0, None):
            continue
        band = ANNUAL_DURATION if r["form"] == "10-K" else QUARTERLY_DURATION
        if not (band[0] <= d <= band[1]):
            flags.append({"ticker": r["ticker"], "fiscal_period_end_date": r["fiscal_period_end_date"],
                          "form": r["form"], "accession_number": r["accession_number"],
                          "check": "duration within form band", "severity": "REVIEW",
                          "detail": f"{r['position']} duration={d:.0f}d, expected {band[0]}-{band[1]}d"})

    nonzero = real[real["value"].abs() > 0]
    for (ticker, position, form), grp in nonzero.groupby(["ticker", "position", "form"]):
        med = grp["value"].abs().median()
        if med <= 0:
            continue
        for _, r in grp.iterrows():
            ratio = max(abs(r["value"]) / med, med / abs(r["value"]))
            if ratio > SCALE_JUMP_FACTOR:
                flags.append({"ticker": ticker, "fiscal_period_end_date": r["fiscal_period_end_date"],
                              "form": form, "accession_number": r["accession_number"],
                              "check": "scale jump vs peers", "severity": "FAIL",
                              "detail": f"{position}={fmt(r['value'])} is {ratio:.0f}x off median {fmt(med)}"})

    frozen = nonzero.groupby(["ticker", "position", "value"])["accession_number"].nunique().reset_index(name="n")
    for _, r in frozen[frozen["n"] >= FROZEN_MIN_FILINGS].iterrows():
        flags.append({"ticker": r["ticker"], "fiscal_period_end_date": "(multiple)", "form": "(multiple)",
                      "accession_number": "(multiple)", "check": "value frozen across filings",
                      "severity": "REVIEW", "detail": f"{r['position']}={fmt(r['value'])} in {int(r['n'])} filings"})
    return flags


# ---------------------------------------------------------- concept audit ----
def audit_concepts(df: pd.DataFrame) -> tuple[list[dict], pd.DataFrame]:
    flags: list[dict] = []
    retrieved = df[df["extraction_method"].isin(RETRIEVED_METHODS) & df["is_real"]].copy()

    # concept drift: a company using more than one concept for the same position
    for (ticker, position), grp in retrieved.groupby(["ticker", "position"]):
        concepts = sorted(grp["concept"].dropna().unique())
        if len(concepts) > 1:
            flags.append({"ticker": ticker, "fiscal_period_end_date": "(multiple)", "form": "(multiple)",
                          "accession_number": "(multiple)", "check": "concept drift", "severity": "REVIEW",
                          "detail": f"{position} resolved to {len(concepts)} concepts: {concepts}"})

    # heavy fallback selection: clean exact-period match repeatedly failed
    real = df[df["is_real"]].copy()
    real["is_fallback"] = real["selection_status"].str.contains("fallback", na=False)
    for (ticker, position), grp in real.groupby(["ticker", "position"]):
        share = grp["is_fallback"].mean()
        if share > FALLBACK_SHARE_FLAG and len(grp) >= 2:
            flags.append({"ticker": ticker, "fiscal_period_end_date": "(multiple)", "form": "(multiple)",
                          "accession_number": "(multiple)", "check": "heavy fallback selection", "severity": "REVIEW",
                          "detail": f"{position}: {share:.0%} of filings used a fallback match (period may be off)"})

    # concept_map.csv: per (ticker, position) concept + latest sample, peers adjacent
    rows: list[dict] = []
    real_sorted = df[df["is_real"]].sort_values("fiscal_period_end_date")
    for (group, ticker, position), grp in real_sorted.groupby(["company_group", "ticker", "position"]):
        retrieved_concepts = sorted(
            grp[grp["extraction_method"].isin(RETRIEVED_METHODS)]["concept"].dropna().unique()
        )
        latest = grp.iloc[-1]
        rows.append({
            "company_group": group, "sector": latest.get("sector"), "ticker": ticker, "position": position,
            "statement_type": latest.get("statement_type"),
            "concepts_used": ", ".join(retrieved_concepts) if retrieved_concepts else "(calculated/none)",
            "extraction_method": latest.get("extraction_method"),
            "n_filings": grp["accession_number"].nunique(),
            "latest_value": latest.get("value"), "latest_period": latest.get("fiscal_period_end_date"),
        })
    concept_map = pd.DataFrame(rows).sort_values(["company_group", "position", "ticker"])
    return flags, concept_map


# -------------------------------------------------------------------- main ----
def main() -> None:
    df = load_facts()
    if df.empty:
        print("financial_facts is empty - run the pipeline first.")
        return

    values, real = to_wide(df)
    flags = check_identities(values, real) + check_anomalies(df)
    concept_flags, concept_map = audit_concepts(df)
    flags += concept_flags
    flags_df = pd.DataFrame(flags)

    print("=" * 80 + "\nCOVERAGE - missing positions\n" + "=" * 80)
    cov = coverage_report(df)
    print("No missing positions." if cov.empty else cov.to_string(index=False))

    print("\n" + "=" * 80 + "\nFLAGS\n" + "=" * 80)
    if flags_df.empty:
        print("No flags raised.")
    else:
        summary = flags_df.groupby(["ticker", "severity"]).size().unstack(fill_value=0).sort_index()
        print("Counts by ticker:\n" + summary.to_string())
        fails = flags_df[flags_df["severity"] == "FAIL"]
        print("\nFAIL flags (most likely wrong-fact selection):")
        print("None." if fails.empty else fails.to_string(index=False))

    flags_df.to_csv("validation_flags.csv", index=False)
    concept_map.to_csv("concept_map.csv", index=False)
    print(f"\nWrote {len(flags_df)} flag(s) to validation_flags.csv")
    print("Wrote concept_map.csv - paste a sector slice into an AI and ask whether the")
    print("position -> concept mappings look right for those companies (plausibility check).")


if __name__ == "__main__":
    main()
