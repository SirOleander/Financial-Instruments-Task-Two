import json
import re
import time
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup

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

    older_submission_files = []

    for file_info in submissions.get("filings", {}).get("files", []):
        file_name = file_info.get("name")

        if not file_name:
            continue

        file_url = f"{config.SEC_DATA_BASE_URL}/submissions/{file_name}"

        try:
            older_file = request_json(session, file_url)
            older_submission_files.append(older_file)

            older_out_path = config.SEC_SUBMISSIONS_DIR / f"{ticker}_{file_name}"
            older_out_path.write_text(
                json.dumps(older_file, indent=2),
                encoding="utf-8",
            )

        except Exception as exc:
            print(f"Could not fetch older submissions file for {ticker}: {file_name}")
            print(exc)

    submissions["_older_submission_files"] = older_submission_files

    return submissions


def submissions_to_dataframe(submissions: dict[str, Any]) -> pd.DataFrame:
    frames = []

    recent = submissions.get("filings", {}).get("recent", {})

    if recent:
        frames.append(pd.DataFrame(recent))

    for older_file in submissions.get("_older_submission_files", []):
        if older_file:
            frames.append(pd.DataFrame(older_file))

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)

    df = df.drop_duplicates(
        subset=["accessionNumber"],
        keep="first",
    )

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
                    # Explicit provenance so that, once companyfacts and iXBRL
                    # candidates are combined, companyfacts keeps priority over
                    # iXBRL in select_best_fact (companyfacts is the primary
                    # source; iXBRL is a targeted fallback).
                    "source": "companyfacts",
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
    report_date=None,
) -> tuple[pd.Series | None, str]:
    if candidates.empty:
        return None, "missing"

    df = candidates.copy()

    df["end"] = pd.to_datetime(df["end"], errors="coerce")
    df["start"] = pd.to_datetime(df["start"], errors="coerce")
    df["filed"] = pd.to_datetime(df["filed"], errors="coerce")

    if "source" not in df.columns:
        df["source"] = "companyfacts"

    df["source_priority"] = df["source"].map({
        "companyfacts": 1,
        "ixbrl": 2,
    }).fillna(9)

    df = df.sort_values(
        ["concept_priority", "source_priority", "filed"],
        ascending=[True, True, False],
    )

    if statement_type == "balance_sheet":
        if report_date is not None and pd.notna(report_date):
            report_date = pd.to_datetime(report_date, errors="coerce").normalize()

            exact_date_match = df[
                df["end"].dt.normalize() == report_date
            ].copy()

            if not exact_date_match.empty:
                exact_date_match = exact_date_match.sort_values(
                    ["concept_priority", "source_priority", "filed"],
                    ascending=[True, True, False],
                )

                selected = exact_date_match.iloc[0]
                source = selected.get("source", "companyfacts")

                if source == "ixbrl":
                    return selected, "selected_ixbrl_balance_sheet_exact_report_date"

                return selected, "selected_companyfacts_balance_sheet_exact_report_date"

        instant_like = df[
            df["start"].isna()
            | (df["duration_days"].fillna(0) == 0)
        ].copy()

        if not instant_like.empty:
            instant_like = instant_like.sort_values(
                ["concept_priority", "source_priority", "end", "filed"],
                ascending=[True, True, False, False],
            )
            return instant_like.iloc[0], "selected_balance_sheet_fallback_latest_instant_check"

        return df.iloc[0], "selected_balance_sheet_fallback_check"

    valid_duration = df[
        df["duration_days"].notna()
        & (df["duration_days"] > 0)
    ].copy()

    if valid_duration.empty:
        return df.iloc[0], "selected_no_duration_available_check"

    exact_end = pd.DataFrame()

    if report_date is not None and pd.notna(report_date):
        report_date = pd.to_datetime(report_date, errors="coerce").normalize()

        exact_end = valid_duration[
            valid_duration["end"].dt.normalize() == report_date
        ].copy()

    # For income statement and cash-flow facts, prefer facts that end exactly
    # on the filing fiscal period end date. This avoids selecting comparative
    # prior-year quarter facts from the same 10-Q accession.
    if not exact_end.empty:
        exact_end = exact_end.sort_values(
            ["concept_priority", "source_priority", "filed"],
            ascending=[True, True, False],
        )

        if form == "10-K":
            annual = exact_end[
                exact_end["duration_days"].between(300, 450)
            ]

            if not annual.empty:
                return annual.iloc[0], "selected_annual_duration_exact_end_date"

            return (
                exact_end.sort_values("duration_days", ascending=False).iloc[0],
                "selected_annual_exact_end_date_duration_fallback_check",
            )

        if form == "10-Q":
            quarter = exact_end[
                exact_end["duration_days"].between(70, 120)
            ]

            if not quarter.empty:
                return quarter.iloc[0], "selected_quarter_duration_exact_end_date"

            return (
                exact_end.sort_values("duration_days", ascending=True).iloc[0],
                "selected_quarter_exact_end_date_duration_fallback_check",
            )

        return exact_end.iloc[0], "selected_default_exact_end_date"

    # Fallback only if no fact ends on reportDate.
    # Keep this visible because these rows need validation.
    if form == "10-K":
        annual = valid_duration[
            valid_duration["duration_days"].between(300, 450)
        ]

        if not annual.empty:
            return annual.iloc[0], "selected_annual_duration_without_exact_end_date_check"

        return (
            valid_duration.sort_values("duration_days", ascending=False).iloc[0],
            "selected_longest_duration_annual_without_exact_end_date_check",
        )

    if form == "10-Q":
        quarter = valid_duration[
            valid_duration["duration_days"].between(70, 120)
        ]

        if not quarter.empty:
            return quarter.iloc[0], "selected_quarter_duration_without_exact_end_date_check"

        shortest = valid_duration.sort_values("duration_days", ascending=True).iloc[0]

        return shortest, "selected_shortest_duration_quarter_without_exact_end_date_check"

    return valid_duration.iloc[0], "selected_default_duration_without_exact_end_date_check"

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
                df.loc[target_mask, "extraction_method"] = "calculated"

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
    positions = list(get_positions_for_ticker(ticker))

    # Some calculation rules use components that are not standard group
    # positions and are only produced by the iXBRL fallback (e.g. ORCL's
    # cloud_services / hardware / services costs feeding cost_of_revenue).
    # We build helper rows for them too, so the calculator can find them and so
    # the intermediate table keeps a transparent record of the inputs.
    # This is a no-op for groups whose calculation components are all standard
    # positions already (TechA, TechB).
    inline_items = config.get_inline_financial_items_for_ticker(ticker)
    for inline_position, rule in inline_items.items():
        position_statement.setdefault(inline_position, rule.get("statement_type"))

    calculation_rules = config.get_calculated_financial_items_for_ticker(ticker)
    for rule in calculation_rules.values():
        for component_position, _weight in rule["components"]:
            if component_position not in positions:
                positions.append(component_position)
                position_statement.setdefault(component_position, None)

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

            selected, selection_status = select_best_fact(
                candidates=candidates,
                statement_type=statement_type,
                form=form,
                report_date=filing.get("reportDate"),
            )

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
                    "extraction_method": "sec_companyfacts",
                })
            else:
                value = selected["value"]
                sign_rule = config.FINANCIAL_POSITION_SIGN_RULES.get(position)
                if sign_rule == "store_positive_absolute_value" and pd.notna(value):
                    value = abs(value)

                base_row.update({
                    "value": value,
                    "unit": selected["unit"],
                    "reporting_currency": selected["unit"],
                    "taxonomy": selected["taxonomy"],
                    "concept": selected["concept"],
                    "fact_start_date": selected["start"],
                    "fact_end_date": selected["end"],
                    "duration_days": selected["duration_days"],
                    "frame": selected.get("frame"),
                    "extraction_method": (
                        "ixbrl_dimensional"
                        if selected.get("source", "companyfacts") == "ixbrl"
                        else "sec_companyfacts"
                    ),
                })
            rows.append(base_row)

    result = pd.DataFrame(rows)
    for col in ("report_release_date", "fiscal_period_end_date", "fact_start_date", "fact_end_date"):
        if col in result.columns:
            formatted = pd.to_datetime(result[col], errors="coerce").dt.strftime("%Y-%m-%d")
            # strftime yields NaN for missing dates; store an explicit None so
            # the column is a clean str-or-None for SQLite.
            result[col] = formatted.where(formatted.notna(), None)
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

def fetch_filing_document(
    session: requests.Session,
    ticker: str,
    cik: str,
    accession_number: str,
    primary_document: str,
) -> str:
    """Download the original SEC filing HTML document."""
    url = config.SEC_ARCHIVES_URL_TEMPLATE.format(
        cik_int=config.cik_int(cik),
        accession_no_dashes=config.accession_no_dashes(accession_number),
        filename=primary_document,
    )

    time.sleep(REQUEST_SLEEP_SECONDS)
    response = session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()

    html = response.text

    config.SEC_FILINGS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = (
        config.SEC_FILINGS_DIR
        / f"{ticker}_{accession_number.replace('-', '')}_{primary_document}"
    )
    out_path.write_text(html, encoding="utf-8")

    return html


def _clean_ixbrl_name(value: str | None) -> str | None:
    """Remove namespace prefix from an iXBRL name."""
    if value is None:
        return None

    return str(value).split(":")[-1]


def _parse_ixbrl_number(raw_value: str, scale: str | None = None, sign: str | None = None) -> float | None:
    """Parse an inline XBRL numeric value."""
    if raw_value is None:
        return None

    text = str(raw_value)
    text = text.replace("\xa0", " ")
    text = text.strip()

    if not text:
        return None

    is_negative = False

    if "(" in text and ")" in text:
        is_negative = True

    text = text.replace("(", "").replace(")", "")
    text = text.replace(",", "")
    text = text.replace("$", "")
    text = text.replace("−", "-")
    text = re.sub(r"[^0-9.\-]", "", text)

    if text in {"", "-", "."}:
        return None

    try:
        value = float(text)
    except ValueError:
        return None

    if scale not in (None, ""):
        try:
            value = value * (10 ** int(scale))
        except ValueError:
            pass

    if sign == "-" or is_negative:
        value = -abs(value)

    return value


def _parse_ixbrl_contexts(soup: BeautifulSoup) -> dict[str, dict[str, Any]]:
    """Parse iXBRL contexts, including instant/end dates and explicit members."""
    contexts: dict[str, dict[str, Any]] = {}

    for context in soup.find_all(lambda tag: tag.name and tag.name.lower().endswith("context")):
        context_id = context.get("id")
        if not context_id:
            continue

        instant = context.find(lambda tag: tag.name and tag.name.lower().endswith("instant"))
        start_date = context.find(lambda tag: tag.name and tag.name.lower().endswith("startdate"))
        end_date = context.find(lambda tag: tag.name and tag.name.lower().endswith("enddate"))

        dimensions: dict[str, str] = {}

        for member in context.find_all(lambda tag: tag.name and tag.name.lower().endswith("explicitmember")):
            axis = _clean_ixbrl_name(member.get("dimension"))
            member_value = _clean_ixbrl_name(member.get_text(strip=True))

            if axis and member_value:
                dimensions[axis] = member_value

        contexts[context_id] = {
            "context_id": context_id,
            "instant": instant.get_text(strip=True) if instant else None,
            "start": start_date.get_text(strip=True) if start_date else None,
            "end": end_date.get_text(strip=True) if end_date else None,
            "dimensions": dimensions,
        }

    return contexts


def _parse_ixbrl_facts(html: str) -> pd.DataFrame:
    """Parse inline XBRL facts from a filing HTML document."""
    soup = BeautifulSoup(html, "html.parser")
    contexts = _parse_ixbrl_contexts(soup)

    fact_rows: list[dict[str, Any]] = []

    ix_fact_tags = soup.find_all(
        lambda tag:
        tag.name
        and (
            tag.name.lower().endswith("nonfraction")
            or tag.name.lower().endswith("nonnumeric")
        )
    )

    for fact in ix_fact_tags:
        raw_name = fact.get("name")
        concept = _clean_ixbrl_name(raw_name)

        if not concept:
            continue

        context_ref = fact.get("contextref") or fact.get("contextRef")
        context = contexts.get(context_ref, {})

        raw_value = fact.get_text(" ", strip=True)
        scale = fact.get("scale")
        sign = fact.get("sign")

        value = _parse_ixbrl_number(raw_value, scale=scale, sign=sign)

        fact_rows.append({
            "concept": concept,
            "raw_concept": raw_name,
            "context_ref": context_ref,
            "unit_ref": fact.get("unitref") or fact.get("unitRef"),
            "unit": config.TARGET_CURRENCY,
            "value": value,
            "raw_value": raw_value,
            "scale": scale,
            "sign": sign,
            "start": context.get("start"),
            "end": context.get("instant") or context.get("end"),
            "dimensions": context.get("dimensions", {}),
        })

    if not fact_rows:
        return pd.DataFrame()

    df = pd.DataFrame(fact_rows)

    for col in ("start", "end"):
        df[col] = pd.to_datetime(df[col], errors="coerce")

    return df

def _fact_matches_required_axis_member(
    dimensions: dict[str, str],
    required_axis_member: dict[str, str | tuple[str, ...] | list[str] | set[str]] | None,
) -> bool:
    """Return True if a parsed iXBRL fact matches required axis/member filters.

    Supports either a single required member:

        {"ProductOrServiceAxis": "ProductMember"}

    or several acceptable members:

        {"ProductOrServiceAxis": ("ProductMember", "ProductsMember")}
    """
    if not required_axis_member:
        return True

    if not isinstance(dimensions, dict):
        return False

    for required_axis, required_member in required_axis_member.items():
        actual_member = dimensions.get(required_axis)

        if isinstance(required_member, (tuple, list, set)):
            if actual_member not in required_member:
                return False
        else:
            if actual_member != required_member:
                return False

    return True


def extract_inline_candidate_rows_for_ticker(
    session: requests.Session,
    ticker: str,
    cik: str,
    selected_filings: pd.DataFrame,
) -> pd.DataFrame:
    """
    Extract ticker-specific iXBRL facts from filing HTML documents.

    Used as fallback for facts that are missing or dimensioned in companyfacts.
    Example:
    AAPL commercial_paper where
    ShortTermDebtTypeAxis = CommercialPaperMember.
    """
    inline_items = config.get_inline_financial_items_for_ticker(ticker)

    if not inline_items:
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []

    for _, filing in selected_filings.iterrows():
        accession_number = filing.get("accessionNumber")
        primary_document = filing.get("primaryDocument")
        form = filing.get("form")

        if not accession_number or not primary_document:
            continue

        try:
            html = fetch_filing_document(
                session=session,
                ticker=ticker,
                cik=cik,
                accession_number=accession_number,
                primary_document=primary_document,
            )
        except Exception as exc:
            print(f"Could not fetch filing document for {ticker} {accession_number}: {exc}")
            continue

        ixbrl_facts = _parse_ixbrl_facts(html)

        if ixbrl_facts.empty:
            continue

        for position, rule in inline_items.items():
            concepts = tuple(rule.get("concepts", ()))
            required_axis_member = rule.get("required_axis_member")
            statement_type = rule.get("statement_type")

            for concept_priority, concept in enumerate(concepts, start=1):
                clean_concept = _clean_ixbrl_name(concept)

                candidates = ixbrl_facts[
                    ixbrl_facts["concept"] == clean_concept
                ].copy()

                if candidates.empty:
                    continue

                candidates = candidates[
                    candidates["dimensions"].apply(
                        lambda dimensions: _fact_matches_required_axis_member(
                            dimensions=dimensions,
                            required_axis_member=required_axis_member,
                        )
                    )
                ].copy()

                if candidates.empty:
                    continue

                for _, fact in candidates.iterrows():
                    raw_concept = str(fact.get("raw_concept") or "")
                    taxonomy = (
                        "us-gaap"
                        if raw_concept.lower().startswith("us-gaap:")
                        else "company_extension_ixbrl"
                    )

                    rows.append({
                        "ticker": ticker,
                        "sector": config.get_sector(ticker),
                        "company_group": config.get_company_group(ticker),
                        "position": position,
                        "concept": clean_concept,
                        "concept_priority": concept_priority,
                        "taxonomy": taxonomy,
                        "unit": config.TARGET_CURRENCY,
                        "value": fact.get("value"),
                        "start": fact.get("start"),
                        "end": fact.get("end"),
                        "fy": None,
                        "fp": None,
                        "form": form,
                        "filed": filing.get("filingDate"),
                        "frame": None,
                        "accession_number": accession_number,
                        "label": None,
                        "source": "ixbrl",
                        "statement_type": statement_type,
                    })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    for col in ("start", "end", "filed"):
        df[col] = pd.to_datetime(df[col], errors="coerce")

    df["duration_days"] = (df["end"] - df["start"]).dt.days

    config.SEC_IXBRL_FACTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = config.SEC_IXBRL_FACTS_DIR / f"{ticker}_inline_facts.csv"
    df.to_csv(out_path, index=False)

    return df

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
