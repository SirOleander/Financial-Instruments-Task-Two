"""
price_ingest.py — STAGE 2 daily-price ingest.

Purely additive. Creates a NEW table `daily_prices` and stores adjusted daily
closes for every distinct ticker in `financial_facts`. It NEVER touches
`financial_facts` (no reads that write, no schema change there). Idempotent:
the primary key is (ticker, date), so a re-run REPLACEs rather than duplicates.

Prices: yfinance history(auto_adjust=True)['Close'] only — already split/dividend
adjusted; no further adjustment. Each series is stored in its OWN native/listing
currency (from history_metadata), never converted, never mixed. `source` mirrors
the fundamentals source ('edgar'/'yfinance') for that ticker.

Universe + uniform start date come straight from financial_facts (no hardcoded
ticker list, no EXCLUDE list). Start = Jan 1 of the earliest report_release_date
year across all companies; end = today.

USAGE (run from inside src/):
    python price_ingest.py            # DRY-RUN: read-only, prints what it WOULD write
    python price_ingest.py --write    # create table + idempotent upsert
"""
from __future__ import annotations

import sys
import time
import warnings
from contextlib import closing

import pandas as pd

import B_database

try:
    import yfinance as yf
except ImportError:  # pragma: no cover
    raise SystemExit("Install yfinance first:  pip install yfinance pandas")

warnings.simplefilter("ignore")

POLITE_SLEEP = 1.0


def create_prices_table() -> None:
    """Create daily_prices (additive; does not touch financial_facts)."""
    with closing(B_database.get_connection()) as con:
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
    """Distinct (ticker, source) + uniform start, from financial_facts."""
    with closing(B_database.get_connection()) as con:
        rows = con.execute(
            """
            SELECT ticker,
                   MAX(source)              AS source,
                   MIN(report_release_date) AS earliest_release
            FROM financial_facts
            WHERE report_release_date IS NOT NULL
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
    with closing(B_database.get_connection()) as con:
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
    with closing(B_database.get_connection()) as con:
        return con.execute("SELECT COUNT(*) FROM financial_facts").fetchone()[0]


def main(write: bool = False) -> None:
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
        with closing(B_database.get_connection()) as con:
            dp = con.execute("SELECT COUNT(*) FROM daily_prices").fetchone()[0]
            dt = con.execute("SELECT COUNT(DISTINCT ticker) FROM daily_prices").fetchone()[0]
        print(f"daily_prices now holds {dp} rows across {dt} tickers.")
        print("\nSTAGE 2 complete. Review, then run price_target.py for STAGE 3.")
    else:
        print("\nDRY-RUN complete. Nothing written. Re-run with --write to ingest.")


if __name__ == "__main__":
    main(write="--write" in sys.argv)
