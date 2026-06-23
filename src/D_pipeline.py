from __future__ import annotations

import logging
from contextlib import closing

import pandas as pd
import requests

import A_config
import B_database
import C_client

TARGET_GROUPS = ("BankA",)
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
