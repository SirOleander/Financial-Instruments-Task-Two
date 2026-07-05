"""
yf_ingest.py — SEPARATE Yahoo-Finance ingest for 20 non-US companies.

This is a self-contained SECOND data source. It is PURELY ADDITIVE: it only
INSERT-OR-REPLACEs the 20 non-US tickers into the existing `financial_facts`
table, every row tagged source='yfinance'. It NEVER touches EDGAR rows, never
rebuilds the table, and NEVER runs de-cumulation (yfinance quarterly statements
are already discrete single quarters, not YTD).

It reuses B_database.insert_financial_facts / the exact EDGAR row shape. The only
schema change is the additive `source` column (see B_database.migrate_schema).

Idempotency: each row's key is the existing unique index
(ticker, accession_number, position, extraction_method) where accession_number is
a synthetic deterministic id "YF-<ticker>-<A|Q>-<period_end>" and
extraction_method='yfinance'. So ticker+period+position+source is unique and a
re-run replaces rather than duplicates.

USAGE (run from inside src/):
    python yf_ingest.py            # DRY-RUN: read-only, prints what it WOULD insert
    python yf_ingest.py --write    # migrate schema + idempotent upsert of 20 tickers
"""
from __future__ import annotations

import sys
import time
import warnings
from datetime import date, timedelta

import pandas as pd

import B_database

try:
    import yfinance as yf
except ImportError:  # pragma: no cover
    raise SystemExit("Install yfinance first:  pip install yfinance pandas")

warnings.simplefilter("ignore")

# --------------------------------------------------------------------------- #
# Label maps: internal_name <- any of these yfinance labels (case/space-insens)
# --------------------------------------------------------------------------- #
LABEL_CANDIDATES: dict[str, list[str]] = {
    "revenue": ["Total Revenue", "Operating Revenue"],
    "cost_of_revenue": ["Cost Of Revenue", "Reconciled Cost Of Revenue"],
    "gross_profit": ["Gross Profit"],
    "research_and_development": ["Research And Development"],
    "operating_income": ["Operating Income", "Total Operating Income As Reported"],
    "income_before_tax": ["Pretax Income"],
    "income_tax": ["Tax Provision", "Income Tax Expense Benefit"],
    "net_income": ["Net Income"],
    "net_interest_income": ["Net Interest Income"],
    "cash_and_cash_equivalents": ["Cash And Cash Equivalents"],
    "total_assets": ["Total Assets"],
    "total_equity": ["Total Equity Gross Minority Interest"],
    "total_debt": ["Total Debt"],
    "short_term_debt": ["Current Debt And Capital Lease Obligation"],
    "long_term_debt": ["Long Term Debt And Capital Lease Obligation"],
    "inventory": ["Inventory"],
    "retained_earnings": ["Retained Earnings"],
    "operating_cash_flow": ["Operating Cash Flow",
                            "Cash Flow From Continuing Operating Activities"],
    "capital_expenditure": ["Capital Expenditure"],
    "cash_dividends_paid": ["Cash Dividends Paid"],
}

# Which statement each internal position belongs to (matches EDGAR statement_type).
POSITION_STATEMENT: dict[str, str] = {
    "revenue": "income_statement",
    "cost_of_revenue": "income_statement",
    "gross_profit": "income_statement",
    "research_and_development": "income_statement",
    "operating_income": "income_statement",
    "income_before_tax": "income_statement",
    "income_tax": "income_statement",
    "net_income": "income_statement",
    "net_interest_income": "income_statement",
    "cash_and_cash_equivalents": "balance_sheet",
    "total_assets": "balance_sheet",
    "total_equity": "balance_sheet",
    "total_debt": "balance_sheet",
    "short_term_debt": "balance_sheet",
    "long_term_debt": "balance_sheet",
    "inventory": "balance_sheet",
    "retained_earnings": "balance_sheet",
    "operating_cash_flow": "cash_flow_statement",
    "capital_expenditure": "cash_flow_statement",
    "cash_dividends_paid": "cash_flow_statement",
}

# yfinance attribute names per (frequency, statement_type)
FRAMES = {
    "annual": {
        "income_statement": "income_stmt",
        "balance_sheet": "balance_sheet",
        "cash_flow_statement": "cashflow",
    },
    "quarterly": {
        "income_statement": "quarterly_income_stmt",
        "balance_sheet": "quarterly_balance_sheet",
        "cash_flow_statement": "quarterly_cashflow",
    },
}

# --------------------------------------------------------------------------- #
# Per-sector expected position sets (from the task maps)
# --------------------------------------------------------------------------- #
TECH = ["revenue", "cost_of_revenue", "gross_profit", "research_and_development",
        "operating_income", "income_before_tax", "income_tax", "net_income",
        "cash_and_cash_equivalents", "total_assets", "total_equity", "total_debt",
        "operating_cash_flow", "capital_expenditure"]
COMM = ["revenue", "cost_of_revenue", "gross_profit",
        "operating_income", "income_before_tax", "income_tax", "net_income",
        "cash_and_cash_equivalents", "total_assets", "total_equity",
        "short_term_debt", "long_term_debt",
        "operating_cash_flow", "capital_expenditure"]
DISC = ["revenue", "cost_of_revenue", "gross_profit",
        "operating_income", "income_before_tax", "income_tax", "net_income",
        "cash_and_cash_equivalents", "total_assets", "total_equity", "total_debt",
        "operating_cash_flow", "capital_expenditure", "inventory"]
HEALTH = list(TECH)
IND = TECH + ["inventory"]
ENERGY = [p for p in TECH if p not in ("cost_of_revenue", "gross_profit")]
BANK = ["revenue", "net_interest_income", "net_income", "income_before_tax",
        "income_tax", "total_assets", "total_equity", "retained_earnings",
        "operating_cash_flow", "cash_dividends_paid"]
STAP = list(DISC)                       # staples: same shape as discretionary (has inventory)
# Financial Services (insurer, e.g. Allianz): no clean cost/gross; cash-flow (OCF/capex)
# absent in yfinance -> those KPIs drop-and-renormalize downstream (like banks' efficiency).
FIN = ["revenue", "operating_income", "income_before_tax", "income_tax", "net_income",
       "cash_and_cash_equivalents", "total_assets", "total_equity", "total_debt",
       "operating_cash_flow", "capital_expenditure"]

# (ticker, EDGAR sector string, company_group label, expected positions)
UNIVERSE = [
    ("TSM",        "Technology",                    "TechIntl",   TECH),
    ("005930.KS",  "Technology",                    "TechIntl",   TECH),
    ("000660.KS",  "Technology",                    "TechIntl",   TECH),
    ("ASML.AS",    "Technology",                    "TechIntl",   TECH),
    ("SAP.DE",     "Technology",                    "TechIntl",   TECH),
    ("SHOP.TO",    "Technology",                    "TechIntl",   TECH),
    ("7203.T",     "Consumer Discretionary",        "DiscIntl",   DISC),
    ("6758.T",     "Consumer Discretionary",        "DiscIntl",   DISC),
    ("AZN.L",      "Healthcare",                    "HealthIntl", HEALTH),
    ("NOVN.SW",    "Healthcare",                    "HealthIntl", HEALTH),
    ("NOVO-B.CO",  "Healthcare",                    "HealthIntl", HEALTH),
    ("SIE.DE",     "Industrials",                   "IndIntl",    IND),
    ("SHEL.L",     "Energy, Materials & Utilities", "EnergyIntl", ENERGY),
    ("HSBA.L",     "Banks",                         "BankIntl",   BANK),
    ("RY.TO",      "Banks",                         "BankIntl",   BANK),
    ("8306.T",     "Banks",                         "BankIntl",   BANK),
    ("TD.TO",      "Banks",                         "BankIntl",   BANK),
    ("SAN.MC",     "Banks",                         "BankIntl",   BANK),
    # ---- Task-Two additions: the 7 non-US of the mandated 98 (added additively) ----
    ("TCEHY",      "Communication",                 "CommIntl",   COMM),
    ("9988.HK",    "Consumer Discretionary",        "DiscIntl",   DISC),
    ("RHHBY",      "Healthcare",                    "HealthIntl", HEALTH),
    ("NESN.SW",    "Consumer Staples",              "StapIntl",   STAP),
    ("MC.PA",      "Consumer Discretionary",        "DiscIntl",   DISC),
    ("ALV.DE",     "Financial Services",            "FinIntl",    FIN),
    ("CBA.AX",     "Banks",                         "BankIntl",   BANK),
]

# The 4 blocked names have NO usable report_release_date (yfinance returns none matching
# their period-ends). They are ingested prediction/ranking-only: fundamentals + prices, but
# their rows carry report_release_date=NULL, so downstream they get NO target
# (target_missing=1), train_eligible=0, and must be keyed on fiscal_period_end_date.
NO_RELEASE_DATE_NAMES = frozenset({"RHHBY", "NESN.SW", "MC.PA", "CBA.AX"})

# release-date matching windows (days after period-end)
QUARTERLY_MAX_LAG = 120
ANNUAL_MAX_LAG = 150
# lag beyond which a matched annual release is "long" and worth an eyeball
ANNUAL_LONG_LAG = 110
NOMINAL_DURATION = {"annual": 365, "quarterly": 92}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _norm(label: object) -> str:
    return "".join(str(label).lower().split())


def _get_df(ticker_obj: "yf.Ticker", attr: str) -> pd.DataFrame:
    try:
        df = getattr(ticker_obj, attr)
        return df if df is not None else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _date_column_map(df: pd.DataFrame) -> dict[date, object]:
    """Map period-end date -> original column label for a statement frame."""
    out: dict[date, object] = {}
    if df is None or df.empty:
        return out
    for col in df.columns:
        try:
            out[pd.to_datetime(col).date()] = col
        except Exception:
            continue
    return out


def _lookup_value(df: pd.DataFrame, col, position: str):
    """First non-NaN value among the position's candidate labels, in order."""
    if df is None or df.empty or col is None:
        return None
    norm_index = {_norm(idx): idx for idx in df.index}
    for candidate in LABEL_CANDIDATES[position]:
        idx = norm_index.get(_norm(candidate))
        if idx is None:
            continue
        try:
            val = df.at[idx, col]
        except Exception:
            continue
        if val is None or (isinstance(val, float) and pd.isna(val)):
            continue
        return float(val), candidate
    return None


def _release_dates(ticker_obj: "yf.Ticker") -> list[date]:
    """Past (already-announced) earnings/release dates, sorted ascending."""
    try:
        ed = ticker_obj.get_earnings_dates(limit=60)
    except Exception:
        return []
    if ed is None or ed.empty:
        return []
    today = pd.Timestamp.now(tz="UTC")
    out: set[date] = set()
    for ts in ed.index:
        t = pd.Timestamp(ts)
        if t.tzinfo is None:
            t = t.tz_localize("UTC")
        if t <= today:
            out.add(t.date())
    return sorted(out)


def _match_release(period_end: date, releases: list[date], freq: str):
    """Earliest release strictly AFTER period_end, within the frequency window.

    Returns (release_date, lag_days) or (None, None) if no safe match. A release
    is only ever accepted if it falls after the period it reports (look-ahead
    safe); the upper bound prevents grabbing the *next* period's announcement.
    """
    max_lag = QUARTERLY_MAX_LAG if freq == "quarterly" else ANNUAL_MAX_LAG
    candidates = [r for r in releases if period_end < r <= period_end + timedelta(days=max_lag)]
    if not candidates:
        return None, None
    chosen = min(candidates)
    return chosen, (chosen - period_end).days


def _quarterly_yoy_count(period_ends: list[date]) -> int:
    """Quarters with a true same-quarter year-ago partner (350-380 days prior)."""
    ds = sorted(period_ends)
    count = 0
    for d in ds:
        if any(350 <= (d - e).days <= 380 for e in ds):
            count += 1
    return count


# --------------------------------------------------------------------------- #
# per-ticker build
# --------------------------------------------------------------------------- #
def build_ticker_rows(ticker: str, sector: str, group: str, expected: list[str]):
    """Fetch one ticker and build EDGAR-shaped rows. Returns (rows, meta)."""
    t = yf.Ticker(ticker)

    # currency + name
    currency, company_name = None, ticker
    try:
        info = t.get_info()
        currency = info.get("financialCurrency") or info.get("currency")
        company_name = info.get("longName") or info.get("shortName") or ticker
    except Exception:
        pass
    currency = currency or "UNKNOWN"

    releases = _release_dates(t)

    rows: list[dict] = []
    meta = {
        "ticker": ticker, "currency": currency, "company_name": company_name,
        "n_release_dates": len(releases),
        "annual_periods": [], "quarterly_periods": [],
        "release_pairs": [], "release_missing": [], "release_flags": [],
        "missing_positions": {},  # period_key -> [positions]
        "row_count": 0,
    }

    for freq, form_code in (("annual", "A"), ("quarterly", "Q")):
        frames = {st: _get_df(t, attr) for st, attr in FRAMES[freq].items()}
        date_maps = {st: _date_column_map(df) for st, df in frames.items()}

        # union of all period-end dates across the three statements
        union_ends = sorted({d for dm in date_maps.values() for d in dm})

        kept_ends: list[date] = []
        prev_kept: date | None = None
        for pend in union_ends:
            period_key = f"{freq[:1].upper()}:{pend}"
            release, lag = _match_release(pend, releases, freq)
            # duration for flow statements (gap to prior KEPT same-freq period-end)
            duration = (pend - prev_kept).days if prev_kept else NOMINAL_DURATION[freq]

            period_rows: list[dict] = []
            missing_here: list[str] = []
            present_count = 0
            for position in expected:
                st = POSITION_STATEMENT[position]
                df = frames[st]
                col = date_maps[st].get(pend)
                found = _lookup_value(df, col, position)

                if found is None:
                    value, status, concept_label = 0.0, "missing", None
                    missing_here.append(position)
                else:
                    value, concept_label = found
                    if position == "capital_expenditure":
                        value = abs(value)  # EDGAR convention: positive magnitude
                    status = "selected_yfinance"
                    present_count += 1

                is_flow = st in ("income_statement", "cash_flow_statement")
                period_rows.append({
                    "ticker": ticker,
                    "cik": "",  # yfinance has no CIK; NOT NULL satisfied by empty string
                    "company_name": company_name,
                    "sector": sector,
                    "company_group": group,
                    "statement_type": st,
                    "position": position,
                    "value": value,
                    "unit": currency,
                    "reporting_currency": currency,
                    "taxonomy": "yfinance",
                    "concept": concept_label,
                    "label": concept_label,
                    "form": freq,  # 'annual' / 'quarterly' (NOT a US SEC form)
                    "accession_number": f"YF-{ticker}-{form_code}-{pend.isoformat()}",
                    "primary_document": None,
                    "report_release_date": release.isoformat() if release else None,
                    "fiscal_period_end_date": pend.isoformat(),
                    "fact_start_date": (pend - timedelta(days=duration)).isoformat() if is_flow else None,
                    "fact_end_date": pend.isoformat(),
                    "duration_days": duration if is_flow else None,
                    "fiscal_year": pend.year,
                    "fiscal_period": "FY" if freq == "annual" else "Q",
                    "selection_status": status,
                    "extraction_method": "yfinance",
                    "provider": "yfinance",
                    "source": "yfinance",
                })

            # Skip pure yfinance NaN-padding columns (every position missing): these
            # are not real report periods. Any period with >=1 real value is kept
            # (e.g. the banks' quarterly rows: income/balance present, cashflow missing).
            if present_count == 0:
                continue

            rows.extend(period_rows)
            kept_ends.append(pend)
            prev_kept = pend

            if release is None:
                meta["release_missing"].append(period_key)
            else:
                meta["release_pairs"].append((period_key, str(release), lag))
                if freq == "annual" and lag > ANNUAL_LONG_LAG:
                    meta["release_flags"].append(
                        f"{ticker} {period_key} -> {release} (lag {lag}d: long annual lag, eyeball)")
                if release <= pend:  # must never happen given the filter; guard anyway
                    meta["release_flags"].append(
                        f"{ticker} {period_key} -> {release} (RELEASE NOT AFTER PERIOD-END)")
            if missing_here:
                meta["missing_positions"][period_key] = missing_here

        if freq == "annual":
            meta["annual_periods"] = kept_ends
        else:
            meta["quarterly_periods"] = kept_ends

    meta["row_count"] = len(rows)
    return rows, meta


# --------------------------------------------------------------------------- #
# reporting
# --------------------------------------------------------------------------- #
def print_meta(meta: dict, expected: list[str]) -> None:
    tk = meta["ticker"]
    qe = meta["quarterly_periods"]
    print(f"\n{'#'*78}\n### {tk}  [{meta['company_name']}]  ccy={meta['currency']}")
    print(f"  rows: {meta['row_count']}  | annual periods: {len(meta['annual_periods'])}"
          f"  quarterly periods: {len(qe)}"
          f"  | change-eligible quarters (YoY partner): {_quarterly_yoy_count(qe)}")
    print(f"  expected positions: {len(expected)}")
    # release coverage
    n_pairs = len(meta["release_pairs"])
    n_miss = len(meta["release_missing"])
    print(f"  release-date coverage: {n_pairs} matched / {n_miss} missing")
    # sample release pairs (up to 6)
    print("  sample (period_end -> release, lag days):")
    for key, rel, lag in meta["release_pairs"][:6]:
        print(f"     {key:16} -> {rel}  (+{lag}d)")
    if meta["release_missing"]:
        print(f"  release MISSING for: {meta['release_missing']}")
    if meta["release_flags"]:
        for f in meta["release_flags"]:
            print(f"  >>> FLAG: {f}")
    # positions missing
    if meta["missing_positions"]:
        agg: dict[str, int] = {}
        for plist in meta["missing_positions"].values():
            for p in plist:
                agg[p] = agg.get(p, 0) + 1
        print(f"  positions missing (position: #periods): {agg}")


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main(write: bool = False) -> None:
    mode = "WRITE (idempotent upsert)" if write else "DRY-RUN (read-only, no DB writes)"
    print(f"yfinance ingest — {mode}\n" + "=" * 78)

    all_rows: list[dict] = []
    per_ticker_counts: list[tuple[str, int]] = []
    global_flags: list[str] = []

    for ticker, sector, group, expected in UNIVERSE:
        rows, meta = build_ticker_rows(ticker, sector, group, expected)
        print_meta(meta, expected)
        all_rows.extend(rows)
        per_ticker_counts.append((ticker, len(rows)))
        global_flags.extend(meta["release_flags"])
        global_flags.extend(f"{ticker} no release date for {k}" for k in meta["release_missing"])
        time.sleep(1.0)  # polite to Yahoo

    print("\n" + "=" * 78)
    print(f"TOTAL rows that WOULD be {'written' if write else 'inserted (dry-run)'}: "
          f"{len(all_rows)} across {len(UNIVERSE)} tickers")
    for tk, n in per_ticker_counts:
        print(f"   {tk:12} {n} rows")

    if global_flags:
        print("\n--- RELEASE-DATE FLAGS / MISSING (eyeball before write) ---")
        for f in global_flags:
            print(f"   {f}")
    else:
        print("\nNo release-date flags: every matched release is safely after its period-end.")

    if not write:
        print("\nDRY-RUN complete. Nothing was written. Re-run with --write to upsert.")
        return

    # ---- WRITE PATH ----
    print("\nMigrating schema (idempotent) ...")
    B_database.migrate_schema()
    print(f"Upserting {len(all_rows)} yfinance rows ...")
    B_database.insert_financial_facts(all_rows)
    print("Done. Run the Step-3 verification script next.")


if __name__ == "__main__":
    main(write="--write" in sys.argv)
