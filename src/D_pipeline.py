"""EDGAR extraction orchestrator (module `D`) — writes the US portion of `financial_facts`.

`main()` rebuilds the whole table (`create_tables(drop_existing=True)`) for the groups in
`TARGET_GROUPS`, fetching via C_client and standardizing per ticker. Includes YTD-flow
de-cumulation (FYE-aware; runs AFTER calculated items and BEFORE the zero-fill of missing
values — an ordering invariant, see CLAUDE.md). DESTRUCTIVE + network: every run drops and
refetches the table. Reads A_config + C_client; writes `financial_facts` (source='edgar').
"""
from __future__ import annotations

import logging
from contextlib import closing

import pandas as pd
import requests

import A_config
import B_database
import C_client

TARGET_GROUPS = ("EnergyA","EnergyB","BankA","FinA","IndA","HealthA","StapA","DiscA", "CommA","TechA","TechB","TechC","TechD")
logger = logging.getLogger(__name__)


def get_target_tickers() -> list[str]:
    unknown_groups = sorted(set(TARGET_GROUPS) - set(A_config.COMPANY_GROUPS))
    if unknown_groups:
        raise ValueError(f"Unknown target groups: {unknown_groups}")

    return sorted(
        {
            ticker
            for group in TARGET_GROUPS
            for ticker in A_config.COMPANY_GROUPS[group]
            if ticker in A_config.ACTIVE_TICKERS and A_config.get_sector(ticker) in A_config.ACTIVE_SECTORS
        }
    )


def _combine_candidate_facts(*frames: pd.DataFrame) -> pd.DataFrame:
    non_empty_frames = [frame for frame in frames if not frame.empty]

    if not non_empty_frames:
        return pd.DataFrame()

    return pd.concat(non_empty_frames, ignore_index=True)


def process_ticker(session: requests.Session, ticker: str) -> int:
    """Retrieve, standardize, calculate, and store one ticker."""
    ciks = A_config.get_ciks(ticker)

    filing_frames: list[pd.DataFrame] = []

    for cik in ciks:
        submissions = C_client.fetch_submissions(
            session=session,
            ticker=ticker,
            cik=cik,
        )
        filings = C_client.submissions_to_dataframe(submissions)

        if filings.empty:
            continue

        filings["filing_cik"] = A_config.cik_10(cik)
        filing_frames.append(filings)

    if not filing_frames:
        logger.info("No SEC filings found for %s", ticker)
        return 0

    filings = (
        pd.concat(filing_frames, ignore_index=True)
        .drop_duplicates(subset=["accessionNumber"], keep="first")
    )

    selected_filings = C_client.select_target_accessions(filings)

    if selected_filings.empty:
        logger.info("No 10-K / 10-Q filings found for %s", ticker)
        return 0

    candidate_frames: list[pd.DataFrame] = []

    for cik in ciks:
        cik_10 = A_config.cik_10(cik)
        selected_for_cik = selected_filings[
            selected_filings["filing_cik"] == cik_10
        ].copy()

        if selected_for_cik.empty:
            continue

        companyfacts = C_client.fetch_companyfacts(
            session=session,
            ticker=ticker,
            cik=cik_10,
        )

        companyfacts_rows = C_client.extract_candidate_rows_for_ticker(
            ticker=ticker,
            companyfacts=companyfacts,
            selected_filings=selected_for_cik,
        )
        candidate_frames.append(companyfacts_rows)

        ixbrl_rows = C_client.extract_inline_candidate_rows_for_ticker(
            session=session,
            ticker=ticker,
            cik=cik_10,
            selected_filings=selected_for_cik,
        )
        candidate_frames.append(ixbrl_rows)

    standardized = C_client.build_standardized_rows(
        ticker=ticker,
        selected_filings=selected_filings,
        candidate_facts=_combine_candidate_facts(*candidate_frames),
    )

    standardized = C_client.apply_calculated_financial_items(
        ticker=ticker,
        standardized=standardized,
    )

    standardized = decumulate_ytd_flows(standardized, ticker)

    calculated_count = int(
        standardized["selection_status"].eq("calculated_from_components").sum()
    )
    missing_count = int(standardized["value"].isna().sum())

    standardized["value"] = standardized["value"].fillna(0)

    rows = standardized.to_dict("records")
    B_database.insert_financial_facts(rows)

    logger.info(
        "%s: %s filings selected across %s CIK(s), %s rows inserted "
        "(%s calculated, %s still missing)",
        ticker,
        len(selected_filings),
        len(ciks),
        len(rows),
        calculated_count,
        missing_count,
    )

    return len(rows)


def print_validation_summary() -> None:
    """Print compact database checks after a retrieval run."""
    with closing(B_database.get_connection()) as connection:
        facts = pd.read_sql_query("SELECT * FROM financial_facts", connection)

    if facts.empty:
        print("\nValidation summary skipped: database table is empty.")
        return

    by_ticker = (
        facts.assign(
            is_missing=facts["selection_status"].eq("missing"),
            is_calculated=facts["extraction_method"].eq("calculated"),
            is_ixbrl=facts["extraction_method"].eq("ixbrl_dimensional"),
        )
        .groupby("ticker", as_index=False)
        .agg(
            filings=("accession_number", "nunique"),
            rows=("position", "size"),
            missing_values=("is_missing", "sum"),
            calculated_rows=("is_calculated", "sum"),
            ixbrl_rows=("is_ixbrl", "sum"),
        )
        .sort_values("ticker")
    )
    print("\nValidation summary by ticker:")
    print(by_ticker.to_string(index=False))

    missing = (
        facts[facts["selection_status"].eq("missing")]
        .groupby(["ticker", "position"], as_index=False)
        .size()
        .rename(columns={"size": "missing_count"})
        .sort_values(
            ["ticker", "missing_count", "position"],
            ascending=[True, False, True],
        )
    )
    if not missing.empty:
        print("\nMissing values by ticker/position:")
        print(missing.to_string(index=False))

    suspicious_repeats = (
        facts[facts["value"].notna()]
        .groupby(["ticker", "position", "value"], as_index=False)
        .agg(repeated_in_filings=("accession_number", "nunique"))
        .query("repeated_in_filings >= 4")
        .sort_values(
            ["ticker", "position", "repeated_in_filings"],
            ascending=[True, True, False],
        )
    )
    if not suspicious_repeats.empty:
        print("\nRepeated same value in at least 4 filings; review, not automatic failure:")
        print(suspicious_repeats.to_string(index=False))


FLOW_STATEMENTS = ("income_statement", "cash_flow_statement")
QUARTER_MAX_DAYS = 130


def _infer_fiscal_year_end_month(df: pd.DataFrame) -> int:
    """Infer this ticker's fiscal-year-end month from its 10-K period-ends.

    Calendar-year filers (the banks, most FinA names) -> 12. Non-calendar
    filers (e.g. V, fiscal year ending ~September) -> their own FYE month.
    Falls back to 12 when no annual rows are present.
    """
    annual_ends = pd.to_datetime(
        df.loc[df["form"].eq("10-K"), "fact_end_date"], errors="coerce"
    ).dropna()
    if annual_ends.empty:
        return 12
    return int(annual_ends.dt.month.mode().iloc[0])


def decumulate_ytd_flows(rows: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Convert YTD 10-Q flow values to discrete quarters for gated tickers.

    Runs only for tickers in A_config.DECUMULATE_YTD_TICKERS. Within those,
    detection is by duration (> QUARTER_MAX_DAYS), so only genuinely cumulative
    rows are changed; discrete rows and all non-10-Q rows are left untouched.
    Because the filter is by statement_type (income + cash flow) and duration,
    it covers any cumulative flow position - operating_cash_flow AND
    capital_expenditure alike - without a hard-coded position list.

    Fiscal year and fiscal quarter are derived FYE-aware (from the ticker's own
    10-K period-end month), so this is correct for non-calendar filers like V.
    For calendar-year filers it reduces exactly to calendar-year grouping, so
    previously de-cumulated tickers (the banks, calendar FinA names) are
    unchanged.

    Per (position, fiscal year):
        Q2 discrete = YTD_Q2 - YTD_Q1   (only if same-year Q1 present)
        Q3 discrete = YTD_Q3 - YTD_Q2   (only if same-year Q2 present)
    A cumulative quarter whose same-year baseline is missing (e.g. a first-window
    year with no Q1) is set to missing (value=NaN, selection_status='missing') so
    the existing missing-count / zero-fill handles it uniformly - never
    de-cumulated against an absent baseline.

    MUST run before the zero-fill.
    """
    if rows.empty:
        return rows

    df = rows.copy()
    fiscal_year_end_month = _infer_fiscal_year_end_month(df)

    end = pd.to_datetime(df["fact_end_date"], errors="coerce")
    candidate = (
        df["form"].eq("10-Q")
        & df["statement_type"].isin(FLOW_STATEMENTS)
        & df["selection_status"].ne("missing")
        & df["duration_days"].notna()
        & end.notna()
    )
    if not candidate.any():
        return rows

    work = df.loc[candidate].copy()
    work["_end"] = end[candidate]
    end_month = work["_end"].dt.month
    end_year = work["_end"].dt.year

    # Reported fiscal year (FYE-aware): a period ending after the fiscal-year-end
    # month rolls into the next fiscal year, so all quarters of one fiscal cycle
    # share a label. For a December FYE this is just the calendar year.
    work["_fy"] = end_year.where(end_month <= fiscal_year_end_month, end_year + 1)

    # Fiscal quarter (1..3 for 10-Qs) from months since the fiscal-year start.
    # Correct for any FYE; for a December FYE it equals the calendar quarter.
    work["_q"] = ((end_month - fiscal_year_end_month - 1) % 12) // 3 + 1

    work["_cum"] = work["duration_days"] > QUARTER_MAX_DAYS

    updates: dict = {}   # index -> column updates
    drops: list = []     # indices to mark missing (unfixable)

    # `work` holds ORIGINAL values, so Q3 is computed from the original Q2 YTD,
    # not from a Q2 that was just de-cumulated.
    for (_position, _fy), grp in work.groupby(["position", "_fy"]):
        by_q = {int(r["_q"]): (idx, r) for idx, r in grp.iterrows()}
        for q in (2, 3):
            if q not in by_q:
                continue
            idx, row = by_q[q]
            if not bool(row["_cum"]):
                continue
            if (q - 1) not in by_q:
                drops.append(idx)
                continue
            _, base = by_q[q - 1]
            if pd.isna(base["value"]) or pd.isna(row["value"]):
                drops.append(idx)
                continue
            status = str(row["selection_status"])
            if not status.endswith("+decumulated"):
                status = f"{status}+decumulated"
            updates[idx] = {
                "value": row["value"] - base["value"],
                "duration_days": int((row["_end"] - base["_end"]).days),
                "fact_start_date": base["_end"].date().isoformat(),
                "selection_status": status,
            }

    for idx, cols in updates.items():
        for col, val in cols.items():
            df.at[idx, col] = val
    for idx in drops:
        df.at[idx, "value"] = float("nan")
        df.at[idx, "selection_status"] = "missing"

    return df


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    B_database.create_tables(drop_existing=True)

    tickers = get_target_tickers()
    if not tickers:
        raise RuntimeError(f"No active tickers found for target groups: {TARGET_GROUPS}")

    logger.info("Target groups: %s", TARGET_GROUPS)
    logger.info("Tickers (%s): %s\n", len(tickers), tickers)

    total_rows = 0
    failed: list[str] = []

    with C_client.make_session() as session:
        for ticker in tickers:
            logger.info("Processing %s...", ticker)
            try:
                total_rows += process_ticker(session, ticker)
            except Exception as exc:
                failed.append(ticker)
                logger.exception("FAILED %s: %s", ticker, exc)

    logger.info("\nDone. Inserted %s rows for %s ticker(s).", total_rows, len(tickers) - len(failed))

    if total_rows:
        print_validation_summary()
    if failed:
        logger.warning("Failed tickers: %s", failed)


if __name__ == "__main__":
    main()
