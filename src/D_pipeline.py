import pandas as pd

import A_config as config
import B_database as database
import C_client as sec_client


# Accounting groups to retrieve in this run. Add groups here (e.g. "TechB")
# once they have been validated. Every name must exist in config.COMPANY_GROUPS.
TARGET_GROUPS = (
    "TechD",
)


def get_target_tickers() -> list[str]:
    unknown_groups = [g for g in TARGET_GROUPS if g not in config.COMPANY_GROUPS]
    if unknown_groups:
        raise ValueError(f"Unknown target groups: {unknown_groups}")

    tickers: list[str] = []
    for group in TARGET_GROUPS:
        tickers.extend(config.COMPANY_GROUPS[group])

    tickers = [
        ticker
        for ticker in tickers
        if ticker in config.ACTIVE_TICKERS
        and config.get_sector(ticker) in config.ACTIVE_SECTORS
    ]

    return sorted(set(tickers))


def process_ticker(session, ticker: str) -> int:
    """Retrieve, standardize, calculate, and store one ticker. Returns rows inserted."""
    cik = config.get_cik(ticker)

    submissions = sec_client.fetch_submissions(session=session, ticker=ticker, cik=cik)
    filings = sec_client.submissions_to_dataframe(submissions)
    selected_filings = sec_client.select_target_accessions(filings)

    if selected_filings.empty:
        print(f"  No 10-K / 10-Q filings found for {ticker}")
        return 0

    companyfacts = sec_client.fetch_companyfacts(session=session, ticker=ticker, cik=cik)

    candidate_facts = sec_client.extract_candidate_rows_for_ticker(
        ticker=ticker,
        companyfacts=companyfacts,
        selected_filings=selected_filings,
    )

    inline_candidate_facts = sec_client.extract_inline_candidate_rows_for_ticker(
        session=session,
        ticker=ticker,
        cik=cik,
        selected_filings=selected_filings,
    )

    if not inline_candidate_facts.empty:
        candidate_facts = pd.concat(
            [candidate_facts, inline_candidate_facts],
            ignore_index=True,
        )

    standardized = sec_client.build_standardized_rows(
        ticker=ticker,
        selected_filings=selected_filings,
        candidate_facts=candidate_facts,
    )

    standardized = sec_client.apply_calculated_financial_items(
        ticker=ticker,
        standardized=standardized,
    )

    rows = standardized.to_dict("records")
    database.insert_financial_facts(rows)

    calculated_count = int(
        standardized["selection_status"].eq("calculated_from_components").sum()
    )
    missing_count = int(standardized["value"].isna().sum())

    print(
        f"  {ticker}: {len(selected_filings)} filings selected, "
        f"{len(rows)} rows inserted "
        f"({calculated_count} calculated, {missing_count} still missing)"
    )

    return len(rows)



def print_validation_summary() -> None:
    """Print compact database checks after a retrieval run."""
    connection = database.get_connection()
    facts = pd.read_sql_query("SELECT * FROM financial_facts", connection)
    connection.close()

    if facts.empty:
        print("\nValidation summary skipped: database table is empty.")
        return

    print("\nValidation summary by ticker:")
    by_ticker = (
        facts.assign(
            is_missing=facts["value"].isna(),
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
    print(by_ticker.to_string(index=False))

    missing = (
        facts[facts["value"].isna()]
        .groupby(["ticker", "position"], as_index=False)
        .size()
        .rename(columns={"size": "missing_count"})
        .sort_values(["ticker", "missing_count", "position"], ascending=[True, False, True])
    )
    if not missing.empty:
        print("\nMissing values by ticker/position:")
        print(missing.to_string(index=False))

    suspicious_repeats = (
        facts[facts["value"].notna()]
        .groupby(["ticker", "position", "value"], as_index=False)
        .agg(repeated_in_filings=("accession_number", "nunique"))
        .query("repeated_in_filings >= 4")
        .sort_values(["ticker", "position", "repeated_in_filings"], ascending=[True, True, False])
    )
    if not suspicious_repeats.empty:
        print("\nRepeated same value in at least 4 filings; review, not automatic failure:")
        print(suspicious_repeats.to_string(index=False))


def main():
    database.create_tables(drop_existing=True)

    session = sec_client.make_session()
    tickers = get_target_tickers()

    print(f"Target groups: {TARGET_GROUPS}")
    print(f"Tickers ({len(tickers)}): {tickers}\n")

    total_rows = 0
    failed: list[str] = []

    for ticker in tickers:
        print(f"Processing {ticker}...")
        try:
            total_rows += process_ticker(session, ticker)
        except Exception as exc:
            failed.append(ticker)
            print(f"  FAILED {ticker}: {exc}")

    print(f"\nDone. Inserted {total_rows} rows for {len(tickers) - len(failed)} ticker(s).")
    if total_rows:
        print_validation_summary()
    if failed:
        print(f"Failed tickers: {failed}")


if __name__ == "__main__":
    main()