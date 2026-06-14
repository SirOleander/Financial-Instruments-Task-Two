import json
import time
from typing import Any

import pandas as pd
import requests

import A_config as config


TARGET_COMPANY_GROUP = "TechA"
TARGET_SECTOR = "Technology"
REQUEST_SLEEP_SECONDS = 0.15
REQUEST_TIMEOUT_SECONDS = 30
MAX_RETRIES = 3

COMPANYFACTS_URL_TEMPLATE = (
    config.SEC_DATA_BASE_URL + "/api/xbrl/companyfacts/CIK{cik_10}.json"
)


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(config.SEC_HEADERS)
    return session


def request_json(session: requests.Session, url: str) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            time.sleep(REQUEST_SLEEP_SECONDS)
            response = session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last_error = exc
            print(f"Request failed {attempt}/{MAX_RETRIES}: {url}")
            print(f"Reason: {exc}")
            time.sleep(REQUEST_SLEEP_SECONDS * attempt * 4)
    raise RuntimeError(f"Failed after {MAX_RETRIES} attempts: {url}") from last_error


def get_techa_tickers() -> list[str]:
    tickers = list(config.COMPANY_GROUPS[TARGET_COMPANY_GROUP])
    tickers = [
        ticker for ticker in tickers
        if ticker in config.ACTIVE_TICKERS and config.get_sector(ticker) == TARGET_SECTOR
    ]
    return sorted(tickers)


def get_positions_for_ticker(ticker: str) -> tuple[str, ...]:
    return config.get_flat_financial_positions_for_ticker(ticker)


def get_position_statement_map(ticker: str) -> dict[str, str]:
    grouped = config.get_financial_positions_for_ticker(ticker)

    result = {}

    for statement_type, positions in grouped.items():
        for position in positions:
            result[position] = statement_type

    return result


def fetch_submissions(session: requests.Session, ticker: str, cik: str) -> dict[str, Any]:
    cik_10 = config.cik_10(cik)
    url = config.SEC_SUBMISSIONS_URL_TEMPLATE.format(cik_10=cik_10)
    submissions = request_json(session, url)

    config.SEC_SUBMISSIONS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = config.SEC_SUBMISSIONS_DIR / f"{ticker}_{cik_10}.json"
    out_path.write_text(json.dumps(submissions, indent=2), encoding="utf-8")
    return submissions


def submissions_to_dataframe(submissions: dict[str, Any]) -> pd.DataFrame:
    recent = submissions.get("filings", {}).get("recent", {})
    if not recent:
        return pd.DataFrame()
    df = pd.DataFrame(recent)
    for col in ("filingDate", "reportDate", "acceptanceDateTime"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def select_target_accessions(filings: pd.DataFrame) -> pd.DataFrame:
    if filings.empty:
        return filings
    target_forms = tuple(config.ANNUAL_FORM_TYPES) + tuple(config.QUARTERLY_FORM_TYPES)
    target = filings[
        filings["form"].isin(target_forms)
        & filings["accessionNumber"].notna()
        & filings["filingDate"].notna()
    ].copy()
    annual = (
        target[target["form"].isin(config.ANNUAL_FORM_TYPES)]
        .sort_values("filingDate", ascending=False)
        .head(config.ANNUAL_REPORTS_TO_FETCH)
    )
    quarterly = (
        target[target["form"].isin(config.QUARTERLY_FORM_TYPES)]
        .sort_values("filingDate", ascending=False)
        .head(config.QUARTERLY_REPORTS_TO_FETCH)
    )
    selected = pd.concat([annual, quarterly], ignore_index=True)
    selected = selected.sort_values("filingDate", ascending=False)
    keep_cols = [
        "accessionNumber", "form", "filingDate", "reportDate",
        "primaryDocument", "acceptanceDateTime",
    ]
    keep_cols = [col for col in keep_cols if col in selected.columns]
    return selected[keep_cols].copy()


def fetch_companyfacts(session: requests.Session, ticker: str, cik: str) -> dict[str, Any]:
    cik_10 = config.cik_10(cik)
    url = COMPANYFACTS_URL_TEMPLATE.format(cik_10=cik_10)
    facts = request_json(session, url)

    out_dir = config.SEC_RAW_DIR / "companyfacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{ticker}_{cik_10}.json"
    out_path.write_text(json.dumps(facts, indent=2), encoding="utf-8")
    return facts


def facts_for_concept(
    companyfacts: dict[str, Any],
    concept: str,
    taxonomy: str = "us-gaap",
) -> list[dict[str, Any]]:
    clean_concept = concept.split(":")[-1]
    concept_block = companyfacts.get("facts", {}).get(taxonomy, {}).get(clean_concept)
    if not concept_block:
        return []

    rows: list[dict[str, Any]] = []
    for unit, facts in concept_block.get("units", {}).items():
        for fact in facts:
            row = dict(fact)
            row["taxonomy"] = taxonomy
            row["concept"] = clean_concept
            row["unit"] = unit
            row["label"] = concept_block.get("label")
            rows.append(row)
    return rows


def extract_candidate_rows_for_ticker(
    ticker: str,
    companyfacts: dict[str, Any],
    selected_filings: pd.DataFrame,
) -> pd.DataFrame:
    accession_set = set(selected_filings["accessionNumber"].dropna())
    positions = get_positions_for_ticker(ticker)
    rows: list[dict[str, Any]] = []

    for position in positions:
        concepts = config.get_concepts_for_financial_position(ticker, position)
        for concept_priority, concept in enumerate(concepts, start=1):
            for fact in facts_for_concept(companyfacts, concept):
                if fact.get("accn") not in accession_set:
                    continue
                if fact.get("form") not in tuple(config.ANNUAL_FORM_TYPES) + tuple(config.QUARTERLY_FORM_TYPES):
                    continue
                if fact.get("unit") != config.TARGET_CURRENCY:
                    continue
                rows.append({
                    "ticker": ticker,
                    "sector": config.get_sector(ticker),
                    "company_group": config.get_company_group(ticker),
                    "position": position,
                    "concept": fact.get("concept"),
                    "concept_priority": concept_priority,
                    "taxonomy": fact.get("taxonomy"),
                    "unit": fact.get("unit"),
                    "value": fact.get("val"),
                    "start": fact.get("start"),
                    "end": fact.get("end"),
                    "fy": fact.get("fy"),
                    "fp": fact.get("fp"),
                    "form": fact.get("form"),
                    "filed": fact.get("filed"),
                    "frame": fact.get("frame"),
                    "accession_number": fact.get("accn"),
                    "label": fact.get("label"),
                })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    for col in ("start", "end", "filed"):
        df[col] = pd.to_datetime(df[col], errors="coerce")
    df["duration_days"] = (df["end"] - df["start"]).dt.days
    return df


def select_best_fact(
    candidates: pd.DataFrame,
    statement_type: str,
    form: str,
) -> tuple[pd.Series | None, str]:
    if candidates.empty:
        return None, "missing"

    df = candidates.copy().sort_values(
        ["concept_priority", "filed"],
        ascending=[True, False],
    )

    if statement_type == "balance_sheet":
        instant_like = df[df["start"].isna() | (df["duration_days"].fillna(0) == 0)]
        if not instant_like.empty:
            return instant_like.iloc[0], "selected_instant_balance_sheet_fact"
        return df.iloc[0], "selected_balance_sheet_fallback_check"

    valid_duration = df[df["duration_days"].notna() & (df["duration_days"] > 0)].copy()
    if valid_duration.empty:
        return df.iloc[0], "selected_no_duration_available_check"

    if form == "10-K":
        annual = valid_duration[valid_duration["duration_days"].between(300, 450)]
        if not annual.empty:
            return annual.iloc[0], "selected_annual_duration_fact"
        return valid_duration.sort_values("duration_days", ascending=False).iloc[0], (
            "selected_longest_duration_annual_fallback_check"
        )

    if form == "10-Q":
        quarter = valid_duration[valid_duration["duration_days"].between(70, 120)]
        if not quarter.empty:
            return quarter.iloc[0], "selected_quarter_duration_fact"
        shortest = valid_duration.sort_values("duration_days", ascending=True).iloc[0]
        return shortest, "selected_shortest_duration_quarter_fallback_check_ytd"

    return valid_duration.iloc[0], "selected_default_duration_fact"

def apply_calculated_financial_items(
    ticker: str,
    standardized: pd.DataFrame,
) -> pd.DataFrame:
    """
    Apply calculated financial item rules from A_config.py.

    Works per filing/accession number.
    Supports:
    - missing components as zero
    - overwrite existing values
    - multi-pass calculations where one calculated item depends on another
    """
    calculation_rules = config.get_calculated_financial_items_for_ticker(ticker)

    if not calculation_rules:
        return standardized

    df = standardized.copy()

    for accession_number in df["accession_number"].dropna().unique():
        filing_mask = df["accession_number"] == accession_number

        for _ in range(5):
            changed_anything = False

            for target_position, rule in calculation_rules.items():
                target_mask = filing_mask & (df["position"] == target_position)

                if not target_mask.any():
                    continue

                current_value = df.loc[target_mask, "value"].iloc[0]
                overwrite_existing = rule.get("overwrite_existing", False)

                if pd.notna(current_value) and not overwrite_existing:
                    continue

                calculated_value = 0
                missing_components = []
                found_component_count = 0

                missing_components_as_zero = rule.get(
                    "missing_components_as_zero",
                    False,
                )
                require_at_least_one_component = rule.get(
                    "require_at_least_one_component",
                    False,
                )

                for component_position, weight in rule["components"]:
                    component_mask = filing_mask & (
                        df["position"] == component_position
                    )

                    if not component_mask.any():
                        if missing_components_as_zero:
                            continue
                        missing_components.append(component_position)
                        continue

                    component_value = df.loc[component_mask, "value"].iloc[0]

                    if pd.isna(component_value):
                        if missing_components_as_zero:
                            continue
                        missing_components.append(component_position)
                        continue

                    calculated_value += weight * component_value
                    found_component_count += 1

                if missing_components:
                    continue

                if require_at_least_one_component and found_component_count == 0:
                    continue

                df.loc[target_mask, "value"] = calculated_value
                df.loc[target_mask, "concept"] = rule["concept"]
                df.loc[target_mask, "taxonomy"] = "calculated"
                df.loc[target_mask, "unit"] = config.TARGET_CURRENCY
                df.loc[target_mask, "reporting_currency"] = config.TARGET_CURRENCY
                df.loc[target_mask, "selection_status"] = "calculated_from_components"

                changed_anything = True

            if not changed_anything:
                break

    return df

def build_standardized_rows(
    ticker: str,
    selected_filings: pd.DataFrame,
    candidate_facts: pd.DataFrame,
) -> pd.DataFrame:
    position_statement = get_position_statement_map(ticker)
    positions = get_positions_for_ticker(ticker)
    rows: list[dict[str, Any]] = []

    for _, filing in selected_filings.iterrows():
        accession = filing["accessionNumber"]
        form = filing["form"]

        for position in positions:
            statement_type = position_statement.get(position)
            if candidate_facts.empty:
                candidates = pd.DataFrame()
            else:
                candidates = candidate_facts[
                    (candidate_facts["accession_number"] == accession)
                    & (candidate_facts["position"] == position)
                ]

            selected, selection_status = select_best_fact(candidates, statement_type, form)

            base_row = {
                "ticker": ticker,
                "cik": config.get_cik(ticker),
                "company_name": config.get_company_name(ticker),
                "sector": config.get_sector(ticker),
                "company_group": config.get_company_group(ticker),
                "form": form,
                "accession_number": accession,
                "report_release_date": filing.get("filingDate"),
                "fiscal_period_end_date": filing.get("reportDate"),
                "primary_document": filing.get("primaryDocument"),
                "position": position,
                "statement_type": statement_type,
                "selection_status": selection_status,
            }

            if selected is None:
                base_row.update({
                    "value": pd.NA,
                    "unit": pd.NA,
                    "taxonomy": pd.NA,
                    "concept": pd.NA,
                    "fact_start_date": pd.NaT,
                    "fact_end_date": pd.NaT,
                    "duration_days": pd.NA,
                    "frame": pd.NA,
                })
            else:
                value = selected["value"]
                sign_rule = config.FINANCIAL_POSITION_SIGN_RULES.get(position)
                if sign_rule == "store_positive_absolute_value" and pd.notna(value):
                    value = abs(value)

                base_row.update({
                    "value": value,
                    "unit": selected["unit"],
                    "taxonomy": selected["taxonomy"],
                    "concept": selected["concept"],
                    "fact_start_date": selected["start"],
                    "fact_end_date": selected["end"],
                    "duration_days": selected["duration_days"],
                    "frame": selected["frame"],
                })
            rows.append(base_row)

    result = pd.DataFrame(rows)
    for col in ("report_release_date", "fiscal_period_end_date", "fact_start_date", "fact_end_date"):
        if col in result.columns:
            result[col] = pd.to_datetime(result[col], errors="coerce").dt.strftime("%Y-%m-%d")
    return result


def save_outputs(long_df: pd.DataFrame) -> None:
    config.INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    long_csv = config.INTERIM_DIR / "techa_financial_values_long.csv"
    wide_csv = config.INTERIM_DIR / "techa_financial_values_wide.csv"
    long_df.to_csv(long_csv, index=False)

    index_cols = [
        "ticker", "company_name", "sector", "company_group", "form",
        "accession_number", "report_release_date", "fiscal_period_end_date",
        "primary_document",
    ]
    wide_df = (
        long_df.pivot_table(
            index=index_cols,
            columns="position",
            values="value",
            aggfunc="first",
        )
        .reset_index()
    )
    wide_df.columns.name = None
    wide_df.to_csv(wide_csv, index=False)

    try:
        long_df.to_parquet(config.INTERIM_DIR / "techa_financial_values_long.parquet", index=False)
        wide_df.to_parquet(config.INTERIM_DIR / "techa_financial_values_wide.parquet", index=False)
    except Exception as exc:
        print(f"Parquet output skipped: {exc}")

    print(f"\nSaved long output: {long_csv}")
    print(f"Saved wide output: {wide_csv}")


def main() -> None:
    session = make_session()
    target_tickers = get_techa_tickers()

    print(f"Retrieving financial values for group: {TARGET_COMPANY_GROUP}")
    print(f"Tickers: {target_tickers}")

    all_rows: list[pd.DataFrame] = []

    for ticker in target_tickers:
        print(f"\n=== {ticker} ===")
        cik = config.get_cik(ticker)
        submissions = fetch_submissions(session, ticker, cik)
        filings = submissions_to_dataframe(submissions)
        selected_filings = select_target_accessions(filings)

        if selected_filings.empty:
            print(f"No selected 10-K / 10-Q filings for {ticker}")
            continue

        companyfacts = fetch_companyfacts(session, ticker, cik)
        candidate_facts = extract_candidate_rows_for_ticker(
            ticker=ticker,
            companyfacts=companyfacts,
            selected_filings=selected_filings,
        )
        standardized = build_standardized_rows(
            ticker=ticker,
            selected_filings=selected_filings,
            candidate_facts=candidate_facts,
        )

        n_missing = standardized["value"].isna().sum()
        n_total = len(standardized)
        print(f"Rows: {n_total}, missing values: {n_missing}")
        all_rows.append(standardized)

    if not all_rows:
        raise RuntimeError("No financial data retrieved.")

    long_df = pd.concat(all_rows, ignore_index=True)
    save_outputs(long_df)

    missing_summary = (
        long_df.assign(is_missing=long_df["value"].isna())
        .groupby(["ticker", "position"], as_index=False)["is_missing"]
        .sum()
        .query("is_missing > 0")
        .sort_values(["ticker", "is_missing"], ascending=[True, False])
    )
    if not missing_summary.empty:
        print("\nMissing value summary:")
        print(missing_summary.to_string(index=False))


if __name__ == "__main__":
    main()
