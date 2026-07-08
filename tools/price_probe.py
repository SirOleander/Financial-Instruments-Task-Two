"""
price_probe.py — STAGE 1 read-only probe for the daily-price ingest.

Purely diagnostic. Fetches daily adjusted-close history from Yahoo for every
distinct ticker in `financial_facts` and reports, per ticker:
  - resolved Yahoo symbol + price-series currency (from history_metadata),
  - first/last available price date and total trading-day row count,
  - bad signs: empty result, price currency != fundamentals reporting_currency,
    large internal gaps (>10 consecutive missing trading days, proxied by a
    >14 calendar-day gap between consecutive rows), or a series that starts
    LATER than that company's earliest report release date.
Also reports the single earliest release date across all companies (to fix the
uniform start year).

Writes NOTHING to the DB. Prices use history(auto_adjust=True)['Close'] only.

USAGE (from the repo root):
    python tools/price_probe.py
"""
from __future__ import annotations

import sys
import time
import warnings
from contextlib import closing
from pathlib import Path

import pandas as pd

# this diagnostic lives in tools/; make the flat pipeline modules in src/ importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from fi import db

try:
    import yfinance as yf
except ImportError:  # pragma: no cover
    raise SystemExit("Install yfinance first:  pip install yfinance pandas")

warnings.simplefilter("ignore")

# A >14 calendar-day gap between two consecutive trading rows implies roughly
# >10 missing trading days (2+ trading weeks) — the task's "large internal gap".
GAP_CALENDAR_DAYS = 14
POLITE_SLEEP = 1.0


def universe() -> list[dict]:
    """Distinct tickers with their source, fundamentals currency, and earliest
    report release date — straight from financial_facts. Never hardcoded."""
    with closing(db.get_connection()) as con:
        rows = con.execute(
            """
            SELECT ticker,
                   source,
                   MAX(reporting_currency)       AS reporting_currency,
                   MIN(report_release_date)      AS earliest_release
            FROM financial_facts
            WHERE report_release_date IS NOT NULL
            GROUP BY ticker
            ORDER BY source, ticker
            """
        ).fetchall()
    return [dict(r) for r in rows]


def fetch_prices(ticker: str, start: str):
    """Return (close_series, price_currency). Adjusted close only, own calendar."""
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
    # index -> naive date
    close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
    return close, currency


def largest_gap(close: pd.Series) -> tuple[int, str]:
    """Largest calendar-day gap between consecutive trading rows, and where."""
    if len(close) < 2:
        return 0, ""
    dates = close.index
    diffs = (dates[1:] - dates[:-1]).days
    idx = int(diffs.argmax())
    return int(diffs[idx]), f"{dates[idx].date()} -> {dates[idx + 1].date()}"


def main() -> None:
    uni = universe()
    earliest_release = min(u["earliest_release"] for u in uni)
    start_year = earliest_release[:4]
    start = f"{start_year}-01-01"

    print("price_probe — STAGE 1 (read-only, no DB writes)")
    print("=" * 90)
    print(f"tickers in financial_facts: {len(uni)} "
          f"({sum(u['source'] == 'edgar' for u in uni)} edgar / "
          f"{sum(u['source'] == 'yfinance' for u in uni)} yfinance)")
    print(f"earliest report_release_date across ALL companies: {earliest_release}")
    print(f"=> proposed UNIFORM start date for the ingest: {start}  (end = today)")
    print("=" * 90)

    header = (f"{'ticker':12} {'src':9} {'fund_ccy':8} {'px_ccy':7} "
              f"{'first_px':11} {'last_px':11} {'rows':>6}  flags")
    print(header)
    print("-" * 90)

    flagged: list[str] = []
    for u in uni:
        ticker = u["ticker"]
        fund_ccy = u["reporting_currency"]
        earliest = u["earliest_release"]
        try:
            close, px_ccy = fetch_prices(ticker, start)
        except Exception as exc:
            line = f"{ticker:12} {u['source']:9} {fund_ccy:8} {'?':7} {'ERROR':11} {'':11} {'':>6}  FETCH-FAIL: {exc}"
            print(line)
            flagged.append(f"{ticker}: fetch error {exc}")
            time.sleep(POLITE_SLEEP)
            continue

        flags: list[str] = []
        if close.empty:
            flags.append("EMPTY")
            first_px = last_px = "-"
            nrows = 0
        else:
            first_px = str(close.index[0].date())
            last_px = str(close.index[-1].date())
            nrows = len(close)
            # currency mismatch (returns still unitless, but user wants to know)
            if px_ccy and fund_ccy and px_ccy.upper() != fund_ccy.upper():
                flags.append(f"CCY {px_ccy}!={fund_ccy}")
            # series starts after this company's earliest release => early
            # reports would have no forward window
            if first_px > earliest:
                flags.append(f"STARTS-LATE(px {first_px} > rel {earliest})")
            gap_days, gap_where = largest_gap(close)
            if gap_days > GAP_CALENDAR_DAYS:
                flags.append(f"GAP {gap_days}d @ {gap_where}")

        px_ccy_s = px_ccy or "?"
        line = (f"{ticker:12} {u['source']:9} {str(fund_ccy):8} {px_ccy_s:7} "
                f"{first_px:11} {last_px:11} {nrows:>6}  {'; '.join(flags)}")
        print(line)
        if flags:
            flagged.append(f"{ticker} ({u['source']}, fund={fund_ccy}): {'; '.join(flags)}")
        time.sleep(POLITE_SLEEP)

    print("=" * 90)
    print(f"earliest release across all companies: {earliest_release} "
          f"=> uniform start {start}")
    print(f"\nFLAGGED tickers ({len(flagged)}):")
    if not flagged:
        print("   (none)")
    for f in flagged:
        print(f"   - {f}")
    print("\nSTAGE 1 complete. Nothing written. Review flags + confirm start year "
          "before STAGE 2.")


if __name__ == "__main__":
    main()
