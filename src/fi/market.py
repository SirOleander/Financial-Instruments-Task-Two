"""market.py — market-data ingest: yfinance fundamentals + daily adjusted prices.

Merges the old `yf_ingest` (non-US fundamentals into `financial_facts`, source='yfinance')
and `price_ingest` (daily adjusted close into `daily_prices`). One external source, one
module.

NAME CLASH RESOLVED ON MERGE: both files defined `main(write=False)`. Renamed to
`main_yf_facts` and `main_prices`; bodies and CLI semantics unchanged.

RULES THAT DO NOT MOVE (see CLAUDE.md):
  * No FX conversion anywhere — KPIs are ratios and the target is a return, so each row
    keeps its native reporting/listing currency.
  * No de-cumulation on yfinance rows: yfinance quarterly is already discrete, unlike
    EDGAR 10-Qs. Capex is normalized POSITIVE to match the EDGAR convention.
  * Missing positions are marked `selection_status='missing'`, never fabricated as 0.
  * `daily_prices` holds ADJUSTED close and is the ONLY price source for the target. It is
    not, and must never become, the unadjusted `ohlc_display.db` chart cache.
"""
from __future__ import annotations

import sys
import time
import warnings
from contextlib import closing
from datetime import date, timedelta

import pandas as pd

from fi import db

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
def main_yf_facts(write: bool = False) -> None:
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
    db.migrate_schema()
    print(f"Upserting {len(all_rows)} yfinance rows ...")
    db.insert_financial_facts(all_rows)
    print("Done. Run the Step-3 verification script next.")




POLITE_SLEEP = 1.0


def create_prices_table() -> None:
    """Create daily_prices (additive; does not touch financial_facts)."""
    with closing(db.get_connection()) as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_prices (
                ticker         TEXT NOT NULL,
                date           TEXT NOT NULL,
                adjusted_close REAL NOT NULL,
                currency       TEXT,
                source         TEXT,
                created_at     TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (ticker, date)
            )
            """
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_daily_prices_ticker ON daily_prices (ticker)"
        )
        con.commit()


def universe() -> list[dict]:
    """Distinct (ticker, source) + uniform start, from financial_facts.

    The earliest-release anchor uses COALESCE(report_release_date, fiscal_period_end_date).
    Four names (CBA.AX, MC.PA, NESN.SW, RHHBY) have NO usable yfinance release date at all, and
    the old `WHERE report_release_date IS NOT NULL` acted as a TICKER FILTER as well as a NULL
    filter — silently dropping them from the price fetch entirely, so a from-scratch build gave
    them no daily_prices rows (93 tickers instead of 97). The surrogate key mirrors what
    fi.features already does for these same names.

    `fiscal_period_end_date` is a KEY SURROGATE ONLY here — it merely anchors how far back to
    fetch prices. It is never a target t=0: price_target still requires a real
    report_release_date, so these four names still get NO forward target. See FINDINGS.md #9.
    """
    with closing(db.get_connection()) as con:
        rows = con.execute(
            """
            SELECT ticker,
                   MAX(source) AS source,
                   MIN(COALESCE(report_release_date, fiscal_period_end_date))
                       AS earliest_release
            FROM financial_facts
            GROUP BY ticker
            ORDER BY source, ticker
            """
        ).fetchall()
    return [dict(r) for r in rows]


def fetch_prices(ticker: str, start: str):
    """Return (close_series indexed by date-string, price_currency)."""
    t = yf.Ticker(ticker)
    hist = t.history(start=start, auto_adjust=True)
    currency = None
    try:
        currency = (t.history_metadata or {}).get("currency")
    except Exception:
        currency = None
    if hist is None or hist.empty or "Close" not in hist.columns:
        return pd.Series(dtype="float64"), currency
    close = hist["Close"].dropna()
    close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
    return close, currency


def upsert_prices(rows: list[tuple]) -> None:
    """INSERT OR REPLACE keyed on (ticker, date) — never duplicates."""
    if not rows:
        return
    with closing(db.get_connection()) as con:
        con.executemany(
            """
            INSERT OR REPLACE INTO daily_prices
                (ticker, date, adjusted_close, currency, source)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )
        con.commit()


def _ff_row_count() -> int:
    with closing(db.get_connection()) as con:
        return con.execute("SELECT COUNT(*) FROM financial_facts").fetchone()[0]


def main_prices(write: bool = False) -> None:
    mode = "WRITE (create table + idempotent upsert)" if write else "DRY-RUN (read-only, no DB writes)"
    print(f"price_ingest — STAGE 2 — {mode}\n" + "=" * 78)

    uni = universe()
    earliest = min(u["earliest_release"] for u in uni)
    start = f"{earliest[:4]}-01-01"
    print(f"tickers: {len(uni)} | earliest release {earliest} | uniform start {start} | end today")

    ff_before = _ff_row_count()
    print(f"financial_facts rows BEFORE: {ff_before}  (must be unchanged after)\n")

    if write:
        create_prices_table()

    per_ticker: list[tuple[str, int, str]] = []
    total = 0
    for u in uni:
        ticker, source = u["ticker"], u["source"]
        close, ccy = fetch_prices(ticker, start)
        n = len(close)
        rows = [
            (ticker, d.date().isoformat(), float(v), ccy, source)
            for d, v in close.items()
        ]
        if write:
            upsert_prices(rows)
        per_ticker.append((ticker, n, ccy or "?"))
        total += n
        print(f"   {ticker:12} {source:9} {ccy or '?':7} {n:>6} rows"
              f"{'' if n else '   <-- EMPTY!'}")
        time.sleep(POLITE_SLEEP)

    print("\n" + "=" * 78)
    print(f"TOTAL price rows {'written' if write else 'that WOULD be written'}: "
          f"{total} across {len(uni)} tickers")

    ff_after = _ff_row_count()
    print(f"\nfinancial_facts rows AFTER: {ff_after}  "
          f"({'UNCHANGED' if ff_after == ff_before else 'CHANGED! investigate'})")

    if write:
        with closing(db.get_connection()) as con:
            dp = con.execute("SELECT COUNT(*) FROM daily_prices").fetchone()[0]
            dt = con.execute("SELECT COUNT(DISTINCT ticker) FROM daily_prices").fetchone()[0]
        print(f"daily_prices now holds {dp} rows across {dt} tickers.")
        print("\nSTAGE 2 complete. Review, then run price_target.py for STAGE 3.")
    else:
        print("\nDRY-RUN complete. Nothing written. Re-run with --write to ingest.")


