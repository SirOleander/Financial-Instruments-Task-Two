import A_config as config
import B_database as database
import C_client as sec_client


def main():
    database.create_tables(drop_existing=True)

    session = sec_client.make_session()

    tickers = sorted(config.COMPANY_GROUPS["TechA"])

    for ticker in tickers:
        print(f"Processing {ticker}...")

        cik = config.get_cik(ticker)

        submissions = sec_client.fetch_submissions(
            session=session,
            ticker=ticker,
            cik=cik,
        )

        filings = sec_client.submissions_to_dataframe(submissions)

        selected_filings = sec_client.select_target_accessions(filings)

        if selected_filings.empty:
            print(f"No 10-K / 10-Q filings found for {ticker}")
            continue

        companyfacts = sec_client.fetch_companyfacts(
            session=session,
            ticker=ticker,
            cik=cik,
        )

        candidate_facts = sec_client.extract_candidate_rows_for_ticker(
            ticker=ticker,
            companyfacts=companyfacts,
            selected_filings=selected_filings,
        )

        standardized = sec_client.build_standardized_rows(
            ticker=ticker,
            selected_filings=selected_filings,
            candidate_facts=candidate_facts,
        )

        rows = standardized.to_dict("records")

        database.insert_financial_facts(rows)

        print(f"Inserted {len(rows)} rows for {ticker}")

    print("Done. TechA financial data inserted into database.")


if __name__ == "__main__":
    main()