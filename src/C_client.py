from __future__ import annotations

import logging
import re
import time
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup, Tag

import A_config

REQUEST_SLEEP_SECONDS = 0.15
REQUEST_TIMEOUT_SECONDS = 30
MAX_RETRIES = 3
COMPANYFACTS_URL_TEMPLATE = A_config.SEC_DATA_BASE_URL + "/api/xbrl/companyfacts/CIK{cik_10}.json"

logger = logging.getLogger(__name__)


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(A_config.SEC_HEADERS)
    return session


def request_json(session: requests.Session, url: str) -> dict[str, Any]:
    """GET JSON from the SEC with light throttling and retries."""
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            time.sleep(REQUEST_SLEEP_SECONDS)
            response = session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            logger.warning("Request failed %s/%s: %s (%s)", attempt, MAX_RETRIES, url, exc)
            time.sleep(REQUEST_SLEEP_SECONDS * attempt * 4)

    raise RuntimeError(f"Failed after {MAX_RETRIES} attempts: {url}") from last_error


def get_positions_for_ticker(ticker: str) -> tuple[str, ...]:
    return A_config.get_flat_financial_positions_for_ticker(ticker)


def get_position_statement_map(ticker: str) -> dict[str, str]:
    return {
        position: statement_type
        for statement_type, positions in A_config.get_financial_positions_for_ticker(ticker).items()
        for position in positions
    }


def fetch_submissions(session: requests.Session, ticker: str, cik: str) -> dict[str, Any]:
    """Fetch recent and paginated historical SEC submission metadata."""
    cik_10 = A_config.cik_10(cik)
    url = A_config.SEC_SUBMISSIONS_URL_TEMPLATE.format(cik_10=cik_10)
    submissions = request_json(session, url)
    older_submission_files = []

    for file_info in submissions.get("filings", {}).get("files", []):
        file_name = file_info.get("name")
        if not file_name:
            continue

        file_url = f"{A_config.SEC_DATA_BASE_URL}/submissions/{file_name}"
        try:
            older_submission_files.append(request_json(session, file_url))
        except RuntimeError as exc:
            logger.warning("Skipping older submissions file for %s (%s): %s", ticker, file_name, exc)

    submissions["_older_submission_files"] = older_submission_files
    return submissions


def submissions_to_dataframe(submissions: dict[str, Any]) -> pd.DataFrame:
    frames = []
    recent = submissions.get("filings", {}).get("recent", {})

    if recent:
        frames.append(pd.DataFrame(recent))

    frames.extend(pd.DataFrame(file_data) for file_data in submissions.get("_older_submission_files", []) if file_data)

    if not frames:
        return pd.DataFrame()

    filings = pd.concat(frames, ignore_index=True).drop_duplicates(
        subset=["accessionNumber"],
        keep="first",
    )

    for column in ("filingDate", "reportDate", "acceptanceDateTime"):
        if column in filings.columns:
            filings[column] = pd.to_datetime(filings[column], errors="coerce")

    return filings


# ============================================================================
# PATCH for C_client.py
#
# This is NOT the whole file. In your existing C_client.py:
#   1. ADD the two helper functions below (_infer_fiscal_year_end_month and
#      _assign_fiscal_year) directly ABOVE the current select_target_accessions.
#   2. REPLACE your existing select_target_accessions with the version below.
# Leave everything else in C_client.py exactly as it is.
#
# It also expects one optional config value (with a safe fallback if absent):
#   A_config.FISCAL_YEARS_TO_FETCH   (e.g. 7)  -- number of fiscal years to keep.
# If you don't add it, it defaults to A_config.ANNUAL_REPORTS_TO_FETCH + 1.
# ============================================================================


def _infer_fiscal_year_end_month(annual_filings: pd.DataFrame) -> int:
    """Infer the fiscal-year-end month from annual filings' report dates.

    Calendar-year filers (the banks) -> 12. Non-calendar filers (AAPL ~Sep,
    MSFT ~Jun, NVDA ~Jan) -> their own FYE month. This makes fiscal-year
    grouping correct for both, instead of using the calendar year, which would
    split a non-calendar fiscal year across two calendar years. Falls back to
    12 (calendar) when no annual report dates are available.
    """
    if annual_filings.empty or "reportDate" not in annual_filings.columns:
        return 12
    months = annual_filings["reportDate"].dropna().dt.month
    if months.empty:
        return 12
    return int(months.mode().iloc[0])


def _assign_fiscal_year(report_dates: pd.Series, fiscal_year_end_month: int) -> pd.Series:
    """Map each period-end date to its reported fiscal year.

    A period ending after the fiscal-year-end month rolls into the next fiscal
    year, so all four periods of one fiscal cycle share a label and consecutive
    cycles differ by 1. For a December FYE this reduces to the calendar year.
    """
    years = report_dates.dt.year
    return years.where(report_dates.dt.month <= fiscal_year_end_month, years + 1)


def select_target_accessions(filings: pd.DataFrame) -> pd.DataFrame:
    """Select 10-K / 10-Q filings for the most recent N fiscal years.

    Year-based (not count-based). The oldest retained fiscal year is always
    COMPLETE, which:
      - guarantees Q1 is present so YTD de-cumulation always has its baseline
        (no more orphaned Q2), and
      - provides a full prior year for YoY features (the oldest year is the
        buffer/base; exclude it from training at the modelling stage).

    Selection is by reported fiscal year (FYE-aware), so it ends on a clean
    fiscal-year boundary regardless of where in the calendar 'now' falls, and is
    correct for both calendar-FY and non-calendar-FY filers. The newest fiscal
    year may be partially filed (current year in progress) - that is expected.

    N = A_config.FISCAL_YEARS_TO_FETCH (fallback: ANNUAL_REPORTS_TO_FETCH + 1).
    """
    if filings.empty:
        return filings

    target = filings[
        filings["form"].isin(A_config.TARGET_FORM_TYPES)
        & filings["accessionNumber"].notna()
        & filings["filingDate"].notna()
        & filings["reportDate"].notna()
    ].copy()

    if target.empty:
        return target

    fiscal_year_end_month = _infer_fiscal_year_end_month(
        target[target["form"].isin(A_config.ANNUAL_FORM_TYPES)]
    )
    target["fiscal_year"] = _assign_fiscal_year(target["reportDate"], fiscal_year_end_month)

    years_to_fetch = getattr(
        A_config, "FISCAL_YEARS_TO_FETCH", A_config.ANNUAL_REPORTS_TO_FETCH + 1
    )
    available_years = sorted(target["fiscal_year"].dropna().unique())
    keep_years = set(available_years[-years_to_fetch:])

    selected = target[target["fiscal_year"].isin(keep_years)].copy()

    # One filing per (form, reportDate): if a period was amended/refiled, keep
    # the most recently filed accession so a period is never duplicated.
    selected = (
        selected.sort_values("filingDate", ascending=False)
        .drop_duplicates(subset=["form", "reportDate"], keep="first")
        .sort_values("filingDate", ascending=False)
    )

    keep_columns = [
        column
        for column in (
            "accessionNumber",
            "form",
            "filingDate",
            "reportDate",
            "primaryDocument",
            "acceptanceDateTime",
            "filing_cik",
        )
        if column in selected.columns
    ]

    return selected[keep_columns].copy()


def fetch_companyfacts(session: requests.Session, ticker: str, cik: str) -> dict[str, Any]:
    """Fetch SEC XBRL companyfacts data for a ticker."""
    url = COMPANYFACTS_URL_TEMPLATE.format(cik_10=A_config.cik_10(cik))
    return request_json(session, url)


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
            row.update(
                taxonomy=taxonomy,
                concept=clean_concept,
                unit=unit,
                label=concept_block.get("label"),
            )
            rows.append(row)

    return rows


def extract_candidate_rows_for_ticker(
    ticker: str,
    companyfacts: dict[str, Any],
    selected_filings: pd.DataFrame,
) -> pd.DataFrame:
    accession_set = set(selected_filings["accessionNumber"].dropna())
    sector = A_config.get_sector(ticker)
    company_group = A_config.get_company_group(ticker)
    rows: list[dict[str, Any]] = []

    for position in get_positions_for_ticker(ticker):
        for concept_priority, concept in enumerate(
            A_config.get_concepts_for_financial_position(ticker, position),
            start=1,
        ):
            for fact in facts_for_concept(companyfacts, concept):
                if fact.get("accn") not in accession_set:
                    continue
                if fact.get("form") not in A_config.TARGET_FORM_TYPES:
                    continue
                if fact.get("unit") != A_config.TARGET_CURRENCY:
                    continue

                rows.append(
                    {
                        "ticker": ticker,
                        "sector": sector,
                        "company_group": company_group,
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
                        "source": "companyfacts",
                    }
                )

    return _with_duration(pd.DataFrame(rows), date_columns=("start", "end", "filed"))


def _with_duration(df: pd.DataFrame, date_columns: tuple[str, ...]) -> pd.DataFrame:
    if df.empty:
        return df

    for column in date_columns:
        if column in df.columns:
            df[column] = pd.to_datetime(df[column], errors="coerce")

    if {"start", "end"}.issubset(df.columns):
        df["duration_days"] = (df["end"] - df["start"]).dt.days

    return df


def _sort_candidates(df: pd.DataFrame, columns: list[str], ascending: list[bool]) -> pd.DataFrame:
    return df.sort_values(columns, ascending=ascending)


# A 10-K flow value must span roughly a full fiscal year. The annual band is
# (300, 450). When no in-band fact carries the filing's period-end date we must
# NOT silently fall back to the longest sub-annual fact: a Q4 (~91d) or 9-month
# YTD (~273d) value would otherwise be stamped as the year (observed on ABBV /
# KLAC gross_profit and GE cost_of_revenue). Below this floor we return missing
# and let the value be computed downstream (e.g. gross_profit = revenue - cost)
# from the sound full-year rows. 300 excludes single quarters, H1, and 9-month
# YTD while still admitting genuine 52/53-week annuals.
ANNUAL_MIN_DAYS = 300


def select_best_fact(
    candidates: pd.DataFrame,
    statement_type: str | None,
    form: str,
    report_date: Any = None,
) -> tuple[pd.Series | None, str]:
    if candidates.empty:
        return None, "missing"

    df = candidates.copy()
    df = _with_duration(df, date_columns=("start", "end", "filed"))

    if "source" not in df.columns:
        df["source"] = "companyfacts"

    df["source_priority"] = df["source"].map({"companyfacts": 1, "ixbrl": 2}).fillna(9)
    df = _sort_candidates(
        df,
        columns=["concept_priority", "source_priority", "filed"],
        ascending=[True, True, False],
    )

    normalized_report_date = None
    if report_date is not None and pd.notna(report_date):
        normalized_report_date = pd.to_datetime(report_date, errors="coerce").normalize()

    if statement_type == "balance_sheet":
        if normalized_report_date is not None:
            exact_date_match = df[df["end"].dt.normalize() == normalized_report_date].copy()
            if not exact_date_match.empty:
                exact_date_match = _sort_candidates(
                    exact_date_match,
                    columns=["concept_priority", "source_priority", "filed"],
                    ascending=[True, True, False],
                )
                selected = exact_date_match.iloc[0]
                if selected.get("source", "companyfacts") == "ixbrl":
                    return selected, "selected_ixbrl_balance_sheet_exact_report_date"
                return selected, "selected_companyfacts_balance_sheet_exact_report_date"

        instant_like = df[df["start"].isna() | (df["duration_days"].fillna(0) == 0)].copy()
        if not instant_like.empty:
            instant_like = _sort_candidates(
                instant_like,
                columns=["concept_priority", "source_priority", "end", "filed"],
                ascending=[True, True, False, False],
            )
            return instant_like.iloc[0], "selected_balance_sheet_fallback_latest_instant_check"

        return df.iloc[0], "selected_balance_sheet_fallback_check"

    valid_duration = df[df["duration_days"].notna() & (df["duration_days"] > 0)].copy()
    if valid_duration.empty:
        return df.iloc[0], "selected_no_duration_available_check"

    exact_end = pd.DataFrame()
    if normalized_report_date is not None:
        exact_end = valid_duration[valid_duration["end"].dt.normalize() == normalized_report_date].copy()

    if not exact_end.empty:
        exact_end = _sort_candidates(
            exact_end,
            columns=["concept_priority", "source_priority", "filed"],
            ascending=[True, True, False],
        )

        if form == "10-K":
            annual = exact_end[exact_end["duration_days"].between(300, 450)]
            if not annual.empty:
                return annual.iloc[0], "selected_annual_duration_exact_end_date"
            longest = exact_end.sort_values("duration_days", ascending=False).iloc[0]
            if longest["duration_days"] >= ANNUAL_MIN_DAYS:
                return longest, "selected_annual_exact_end_date_duration_fallback_check"
            # Longest available is sub-annual (Q4 / YTD); refuse to stamp it as the
            # year. Mark missing -> reads as a coverage gap, computed downstream.
            return None, "missing"

        if form == "10-Q":
            quarter = exact_end[exact_end["duration_days"].between(70, 120)]
            if not quarter.empty:
                return quarter.iloc[0], "selected_quarter_duration_exact_end_date"
            return (
                exact_end.sort_values("duration_days", ascending=True).iloc[0],
                "selected_quarter_exact_end_date_duration_fallback_check",
            )

        return exact_end.iloc[0], "selected_default_exact_end_date"

    if form == "10-K":
        annual = valid_duration[valid_duration["duration_days"].between(300, 450)]
        if not annual.empty:
            return annual.iloc[0], "selected_annual_duration_without_exact_end_date_check"
        longest = valid_duration.sort_values("duration_days", ascending=False).iloc[0]
        if longest["duration_days"] >= ANNUAL_MIN_DAYS:
            return longest, "selected_longest_duration_annual_without_exact_end_date_check"
        return None, "missing"

    if form == "10-Q":
        quarter = valid_duration[valid_duration["duration_days"].between(70, 120)]
        if not quarter.empty:
            return quarter.iloc[0], "selected_quarter_duration_without_exact_end_date_check"
        return (
            valid_duration.sort_values("duration_days", ascending=True).iloc[0],
            "selected_shortest_duration_quarter_without_exact_end_date_check",
        )

    return valid_duration.iloc[0], "selected_default_duration_without_exact_end_date_check"


def apply_calculated_financial_items(ticker: str, standardized: pd.DataFrame) -> pd.DataFrame:
    calculation_rules = A_config.get_calculated_financial_items_for_ticker(ticker)
    if not calculation_rules:
        return standardized

    df = standardized.copy()

    for accession_number in df["accession_number"].dropna().unique():
        filing_mask = df["accession_number"] == accession_number

        for _pass_number in range(5):
            changed_anything = False

            for target_position, rule in calculation_rules.items():
                target_mask = filing_mask & (df["position"] == target_position)
                if not target_mask.any():
                    continue

                current_value = df.loc[target_mask, "value"].iloc[0]
                if pd.notna(current_value) and not rule.get("overwrite_existing", False):
                    continue

                calculated_value = 0
                missing_components = []
                found_component_count = 0
                missing_components_as_zero = rule.get("missing_components_as_zero", False)

                for component_position, weight in rule["components"]:
                    component_mask = filing_mask & (df["position"] == component_position)
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
                if rule.get("require_at_least_one_component", False) and found_component_count == 0:
                    continue

                df.loc[target_mask, "value"] = calculated_value
                df.loc[target_mask, "concept"] = rule["concept"]
                df.loc[target_mask, "taxonomy"] = "calculated"
                df.loc[target_mask, "unit"] = A_config.TARGET_CURRENCY
                df.loc[target_mask, "reporting_currency"] = A_config.TARGET_CURRENCY
                df.loc[target_mask, "selection_status"] = "calculated_from_components"
                df.loc[target_mask, "extraction_method"] = "calculated"
                changed_anything = True

            if not changed_anything:
                break

    return df


def _positions_needed_for_ticker(ticker: str) -> tuple[list[str], dict[str, str | None]]:
    position_statement = get_position_statement_map(ticker)
    positions = list(get_positions_for_ticker(ticker))

    for inline_position, rule in A_config.get_inline_financial_items_for_ticker(ticker).items():
        position_statement.setdefault(inline_position, rule.get("statement_type"))

    for rule in A_config.get_calculated_financial_items_for_ticker(ticker).values():
        for component_position, _weight in rule["components"]:
            if component_position not in positions:
                positions.append(component_position)
                position_statement.setdefault(component_position, None)

    return positions, position_statement


def build_standardized_rows(
    ticker: str,
    selected_filings: pd.DataFrame,
    candidate_facts: pd.DataFrame,
) -> pd.DataFrame:
    positions, position_statement = _positions_needed_for_ticker(ticker)
    candidate_groups = {
        key: group
        for key, group in candidate_facts.groupby(["accession_number", "position"])
    } if not candidate_facts.empty else {}

    company_metadata = {
        "ticker": ticker,
        "company_name": A_config.get_company_name(ticker),
        "sector": A_config.get_sector(ticker),
        "company_group": A_config.get_company_group(ticker),
    }
    rows: list[dict[str, Any]] = []

    for filing in selected_filings.to_dict("records"):
        accession = filing["accessionNumber"]
        form = filing["form"]

        for position in positions:
            statement_type = position_statement.get(position)
            candidates = candidate_groups.get((accession, position), pd.DataFrame())
            selected, selection_status = select_best_fact(
                candidates=candidates,
                statement_type=statement_type,
                form=form,
                report_date=filing.get("reportDate"),
            )

            row = {
                **company_metadata,
                "cik": filing.get("filing_cik") or A_config.get_cik(ticker),
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
                row.update(
                    value=pd.NA,
                    unit=pd.NA,
                    taxonomy=pd.NA,
                    concept=pd.NA,
                    fact_start_date=pd.NaT,
                    fact_end_date=pd.NaT,
                    duration_days=pd.NA,
                    frame=pd.NA,
                    extraction_method="sec_companyfacts",
                )
            else:
                value = selected["value"]
                if A_config.FINANCIAL_POSITION_SIGN_RULES.get(position) == "store_positive_absolute_value" and pd.notna(value):
                    value = abs(value)

                row.update(
                    value=value,
                    unit=selected["unit"],
                    reporting_currency=selected["unit"],
                    taxonomy=selected["taxonomy"],
                    concept=selected["concept"],
                    fact_start_date=selected["start"],
                    fact_end_date=selected["end"],
                    duration_days=selected["duration_days"],
                    frame=selected.get("frame"),
                    extraction_method=(
                        "ixbrl_dimensional"
                        if selected.get("source", "companyfacts") == "ixbrl"
                        else "sec_companyfacts"
                    ),
                )

            rows.append(row)

    result = pd.DataFrame(rows)
    for column in ("report_release_date", "fiscal_period_end_date", "fact_start_date", "fact_end_date"):
        if column in result.columns:
            formatted = pd.to_datetime(result[column], errors="coerce").dt.strftime("%Y-%m-%d")
            result[column] = formatted.where(formatted.notna(), None)

    return result


def fetch_filing_document(
    session: requests.Session,
    cik: str,
    accession_number: str,
    primary_document: str,
) -> str:
    """Download an SEC filing HTML document without writing it to disk."""
    url = A_config.SEC_ARCHIVES_URL_TEMPLATE.format(
        cik_int=A_config.cik_int(cik),
        accession_no_dashes=A_config.accession_no_dashes(accession_number),
        filename=primary_document,
    )

    time.sleep(REQUEST_SLEEP_SECONDS)
    response = session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.text


def list_filing_inline_documents(
    session: requests.Session,
    cik: str,
    accession_number: str,
) -> list[str]:
    """Return candidate inline-XBRL HTML documents in a filing accession."""
    url = A_config.SEC_ARCHIVES_URL_TEMPLATE.format(
        cik_int=A_config.cik_int(cik),
        accession_no_dashes=A_config.accession_no_dashes(accession_number),
        filename="index.json",
    )

    try:
        listing = request_json(session, url)
    except RuntimeError as exc:
        logger.warning("Could not list documents for %s: %s", accession_number, exc)
        return []

    documents: list[str] = []
    for item in listing.get("directory", {}).get("item", []):
        name = item.get("name", "")
        lower_name = name.lower()

        if not lower_name.endswith((".htm", ".html")):
            continue
        if "-index" in lower_name:
            continue
        if re.fullmatch(r"r\d+\.htm", lower_name):
            continue

        documents.append(name)

    return documents


def _clean_ixbrl_name(value: str | None) -> str | None:
    if value is None:
        return None
    return str(value).split(":")[-1]


def _parse_ixbrl_number(
    raw_value: Any,
    scale: str | None = None,
    sign: str | None = None,
) -> float | None:
    if raw_value is None:
        return None

    text = str(raw_value).replace("\xa0", " ").strip()
    if not text:
        return None

    is_negative = "(" in text and ")" in text
    text = text.replace("(", "").replace(")", "")
    text = text.replace(",", "").replace("$", "").replace("−", "-")
    text = re.sub(r"[^0-9.\-]", "", text)

    if text in {"", "-", "."}:
        return None

    try:
        value = float(text)
    except ValueError:
        return None

    if scale not in (None, ""):
        try:
            value *= 10 ** int(scale)
        except ValueError:
            pass

    if sign == "-" or is_negative:
        value = -abs(value)

    return value


def _tag_name_endswith(tag: Tag, suffix: str) -> bool:
    return bool(tag.name and tag.name.lower().endswith(suffix))


def _parse_ixbrl_contexts(soup: BeautifulSoup) -> dict[str, dict[str, Any]]:
    contexts: dict[str, dict[str, Any]] = {}

    for context in soup.find_all(lambda tag: _tag_name_endswith(tag, "context")):
        context_id = context.get("id")
        if not context_id:
            continue

        instant = context.find(lambda tag: _tag_name_endswith(tag, "instant"))
        start_date = context.find(lambda tag: _tag_name_endswith(tag, "startdate"))
        end_date = context.find(lambda tag: _tag_name_endswith(tag, "enddate"))
        dimensions: dict[str, str] = {}

        for member in context.find_all(lambda tag: _tag_name_endswith(tag, "explicitmember")):
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


def _is_ixbrl_fact_tag(tag: Tag) -> bool:
    if not tag.name or tag.get("name") is None:
        return False

    lower_name = tag.name.lower()
    return "nonfraction" in lower_name or "nonnumeric" in lower_name


def _parse_ixbrl_facts(html: str) -> pd.DataFrame:
    soup = BeautifulSoup(html, "html.parser")
    contexts = _parse_ixbrl_contexts(soup)
    fact_rows: list[dict[str, Any]] = []

    for fact in soup.find_all(_is_ixbrl_fact_tag):
        raw_name = fact.get("name")
        concept = _clean_ixbrl_name(raw_name)
        if not concept:
            continue

        context_ref = fact.get("contextref") or fact.get("contextRef")
        context = contexts.get(context_ref, {})
        raw_value = fact.get_text(" ", strip=True)

        fact_rows.append(
            {
                "concept": concept,
                "raw_concept": raw_name,
                "context_ref": context_ref,
                "unit_ref": fact.get("unitref") or fact.get("unitRef"),
                "unit": A_config.TARGET_CURRENCY,
                "value": _parse_ixbrl_number(
                    raw_value,
                    scale=fact.get("scale"),
                    sign=fact.get("sign"),
                ),
                "raw_value": raw_value,
                "scale": fact.get("scale"),
                "sign": fact.get("sign"),
                "start": context.get("start"),
                "end": context.get("instant") or context.get("end"),
                "dimensions": context.get("dimensions", {}),
            }
        )

    return _with_duration(pd.DataFrame(fact_rows), date_columns=("start", "end"))


def _fact_matches_required_axis_member(
    dimensions: dict[str, str],
    required_axis_member: dict[Any, Any] | None,
) -> bool:
    if not required_axis_member:
        return True
    if not isinstance(dimensions, dict):
        return False

    for required_axis, required_member in required_axis_member.items():
        possible_axes = required_axis if isinstance(required_axis, (tuple, list, set)) else (required_axis,)
        actual_member = next((dimensions[axis] for axis in possible_axes if axis in dimensions), None)
        if actual_member is None:
            return False

        possible_members = required_member if isinstance(required_member, (tuple, list, set)) else (required_member,)
        if actual_member not in possible_members:
            return False

    return True


def _filter_inline_candidates(
    ixbrl_facts: pd.DataFrame,
    concept: str,
    required_axis_member: dict[Any, Any] | None,
) -> pd.DataFrame:
    candidates = ixbrl_facts[ixbrl_facts["concept"] == concept].copy()
    if candidates.empty:
        return candidates

    if required_axis_member:
        return candidates[
            candidates["dimensions"].apply(
                lambda dimensions: _fact_matches_required_axis_member(dimensions, required_axis_member)
            )
        ].copy()

    return candidates[
        candidates["dimensions"].apply(lambda dimensions: isinstance(dimensions, dict) and not dimensions)
    ].copy()


def extract_inline_candidate_rows_for_ticker(
    session: requests.Session,
    ticker: str,
    cik: str,
    selected_filings: pd.DataFrame,
) -> pd.DataFrame:
    """Extract ticker-specific iXBRL facts used as targeted fallbacks."""
    inline_items = A_config.get_inline_financial_items_for_ticker(ticker)
    if not inline_items:
        return pd.DataFrame()

    sector = A_config.get_sector(ticker)
    company_group = A_config.get_company_group(ticker)
    rows: list[dict[str, Any]] = []

    for filing in selected_filings.to_dict("records"):
        accession_number = filing.get("accessionNumber")
        primary_document = filing.get("primaryDocument")
        form = filing.get("form")

        if not accession_number or not primary_document:
            continue

        document_names = list_filing_inline_documents(session, cik, accession_number)
        if primary_document not in document_names:
            document_names.insert(0, primary_document)

        per_document_facts: list[pd.DataFrame] = []
        for document_name in document_names:
            try:
                html = fetch_filing_document(
                    session=session,
                    cik=cik,
                    accession_number=accession_number,
                    primary_document=document_name,
                )
            except requests.RequestException as exc:
                logger.warning(
                    "Skipping %s for %s %s: %s",
                    document_name,
                    ticker,
                    accession_number,
                    exc,
                )
                continue

            facts = _parse_ixbrl_facts(html)
            if not facts.empty:
                per_document_facts.append(facts)

        if not per_document_facts:
            continue

        ixbrl_facts = pd.concat(per_document_facts, ignore_index=True)
        ixbrl_facts["_dim_sig"] = ixbrl_facts["dimensions"].apply(
            lambda dimensions: tuple(sorted(dimensions.items())) if isinstance(dimensions, dict) else ()
        )
        ixbrl_facts = ixbrl_facts.drop_duplicates(
            subset=["concept", "start", "end", "value", "_dim_sig"],
            keep="first",
        ).drop(columns="_dim_sig")
        ixbrl_facts = _with_duration(ixbrl_facts, date_columns=("start", "end"))

        for position, rule in inline_items.items():
            required_axis_member = rule.get("required_axis_member")
            statement_type = rule.get("statement_type")

            for concept_priority, concept in enumerate(tuple(rule.get("concepts", ())), start=1):
                clean_concept = _clean_ixbrl_name(concept)
                if not clean_concept:
                    continue

                candidates = _filter_inline_candidates(
                    ixbrl_facts=ixbrl_facts,
                    concept=clean_concept,
                    required_axis_member=required_axis_member,
                )
                if candidates.empty:
                    continue

                for fact in candidates.to_dict("records"):
                    raw_concept = str(fact.get("raw_concept") or "")
                    taxonomy = "us-gaap" if raw_concept.lower().startswith("us-gaap:") else "company_extension_ixbrl"

                    rows.append(
                        {
                            "ticker": ticker,
                            "sector": sector,
                            "company_group": company_group,
                            "position": position,
                            "concept": clean_concept,
                            "concept_priority": concept_priority,
                            "taxonomy": taxonomy,
                            "unit": A_config.TARGET_CURRENCY,
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
                        }
                    )

    return _with_duration(pd.DataFrame(rows), date_columns=("start", "end", "filed"))
