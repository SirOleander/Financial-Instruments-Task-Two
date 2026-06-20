print("DEBUG SCRIPT STARTED", flush=True)

import pandas as pd

import A_config as config
import C_client as sec_client


TICKER = "INTU"
TARGET_CONCEPT = "CostOfGoodsAndServicesSold"


def main() -> None:
    print("CONFIG FILE:", config.__file__, flush=True)
    print("CLIENT FILE:", sec_client.__file__, flush=True)

    cik = config.get_cik(TICKER)

    print(f"\nTicker: {TICKER}", flush=True)
    print(f"CIK: {cik}", flush=True)

    inline_items = config.get_inline_financial_items_for_ticker(TICKER)

    print("\nInline config loaded for INTU:", flush=True)
    print(inline_items, flush=True)

    if not inline_items:
        print(
            "\nSTOP: No INTU inline config found. "
            "Check INLINE_FINANCIAL_ITEMS_BY_TICKER in A_config.py.",
            flush=True,
        )
        return

    session = sec_client.make_session()

    print("\nFetching submissions...", flush=True)
    submissions = sec_client.fetch_submissions(
        session=session,
        ticker=TICKER,
        cik=cik,
    )

    filings = sec_client.submissions_to_dataframe(submissions)
    selected_filings = sec_client.select_target_accessions(filings)

    print(f"\nSelected filings: {len(selected_filings)}", flush=True)

    if selected_filings.empty:
        print("STOP: No selected 10-K / 10-Q filings.", flush=True)
        return

    keep_cols = [
        "accessionNumber",
        "form",
        "filingDate",
        "reportDate",
        "primaryDocument",
    ]
    keep_cols = [col for col in keep_cols if col in selected_filings.columns]

    print("\nSelected filings table:", flush=True)
    print(selected_filings[keep_cols].to_string(index=False), flush=True)

    print("\nStarting manual iXBRL inspection...", flush=True)

    all_debug_rows = []

    for _, filing in selected_filings.iterrows():
        accession_number = filing.get("accessionNumber")
        primary_document = filing.get("primaryDocument")
        form = filing.get("form")
        report_date = filing.get("reportDate")

        print("\n" + "=" * 100, flush=True)
        print(
            f"Filing: {TICKER} | {form} | accession={accession_number} | "
            f"reportDate={report_date} | document={primary_document}",
            flush=True,
        )

        if not accession_number or not primary_document:
            print("Skipping: missing accession number or primary document.", flush=True)
            continue

        try:
            html = sec_client.fetch_filing_document(
                session=session,
                ticker=TICKER,
                cik=cik,
                accession_number=accession_number,
                primary_document=primary_document,
            )
        except Exception as exc:
            print(f"FAILED to fetch filing document: {exc}", flush=True)
            continue

        print("Fetched filing HTML.", flush=True)

        try:
            ixbrl_facts = sec_client._parse_ixbrl_facts(html)
        except Exception as exc:
            print(f"FAILED to parse iXBRL facts: {exc}", flush=True)
            continue

        print(f"Parsed iXBRL facts: {len(ixbrl_facts)}", flush=True)

        if ixbrl_facts.empty:
            print("No iXBRL facts parsed.", flush=True)
            continue

        ixbrl_facts["duration_days"] = (
            ixbrl_facts["end"] - ixbrl_facts["start"]
        ).dt.days

        concept_debug = ixbrl_facts[
            ixbrl_facts["concept"].eq(TARGET_CONCEPT)
        ].copy()

        print(
            f"Facts with concept {TARGET_CONCEPT}: {len(concept_debug)}",
            flush=True,
        )

        if concept_debug.empty:
            similar = ixbrl_facts[
                ixbrl_facts["concept"].str.contains(
                    "Cost|Revenue|Goods|Services",
                    case=False,
                    na=False,
                )
            ].copy()

            print(
                "No exact concept found. Similar cost/revenue concepts in filing:",
                flush=True,
            )

            if similar.empty:
                print("No similar concepts found.", flush=True)
            else:
                print(
                    similar[
                        [
                            "concept",
                            "value",
                            "start",
                            "end",
                            "duration_days",
                            "dimensions",
                            "raw_value",
                        ]
                    ].to_string(index=False),
                    flush=True,
                )

            continue

        print("\nAll matching concept facts:", flush=True)
        print(
            concept_debug[
                [
                    "concept",
                    "value",
                    "start",
                    "end",
                    "duration_days",
                    "dimensions",
                    "raw_value",
                ]
            ].to_string(index=False),
            flush=True,
        )

        product_service_debug = concept_debug[
            concept_debug["dimensions"].apply(
                lambda d: isinstance(d, dict)
                and any(
                    axis in d
                    for axis in (
                        "ProductOrServiceAxis",
                        "ProductAndServiceAxis",
                    )
                )
            )
        ].copy()

        print(
            "\nMatching concept facts with Product/Service axis:",
            len(product_service_debug),
            flush=True,
        )

        if product_service_debug.empty:
            print(
                "No Product/Service-axis facts found for this concept.",
                flush=True,
            )
        else:
            print(
                product_service_debug[
                    [
                        "concept",
                        "value",
                        "start",
                        "end",
                        "duration_days",
                        "dimensions",
                        "raw_value",
                    ]
                ].to_string(index=False),
                flush=True,
            )

        for _, row in concept_debug.iterrows():
            all_debug_rows.append(
                {
                    "accession_number": accession_number,
                    "form": form,
                    "report_date": report_date,
                    "primary_document": primary_document,
                    "concept": row.get("concept"),
                    "value": row.get("value"),
                    "start": row.get("start"),
                    "end": row.get("end"),
                    "duration_days": row.get("duration_days"),
                    "dimensions": row.get("dimensions"),
                    "raw_value": row.get("raw_value"),
                }
            )

    print("\n" + "=" * 100, flush=True)
    print("SUMMARY", flush=True)

    if not all_debug_rows:
        print(
            f"No {TARGET_CONCEPT} facts found across selected filings.",
            flush=True,
        )
        return

    summary = pd.DataFrame(all_debug_rows)

    print(
        summary[
            [
                "accession_number",
                "form",
                "report_date",
                "concept",
                "value",
                "start",
                "end",
                "duration_days",
                "dimensions",
                "raw_value",
            ]
        ].to_string(index=False),
        flush=True,
    )


if __name__ == "__main__":
    main()