"""
fetch_ohlc.py — DISPLAY-ONLY OHLC cache for the Company Detail price chart.

================================================================================
FIREWALL — READ THIS BEFORE CHANGING ANYTHING
================================================================================
This OHLC data exists for ONE purpose: drawing the Company Detail price chart.
It MUST NEVER reach the modelling pipeline.

  * It is written to a SEPARATE DATABASE FILE, `data/ohlc_display.db` — not to
    `data/financials.db`. That is deliberate and stronger than a separate table:
    the modelling database is never even opened for writing, so its file hash is
    provably unchanged.
  * `daily_prices` is the TARGET's price source (src/price_target.py builds
    future_63d_sharpe from it). It is NOT touched here, and this table is not a
    substitute for it. Adjusted vs unadjusted close differ; mixing them would
    silently corrupt the target.
  * Nothing in src/ reads `ohlc_display.db`. Nothing ever should. If a future
    feature needs prices for modelling, it uses `daily_prices` in financials.db.
  * These are RAW OHLC (auto_adjust=False): real open/high/low/close as traded,
    which is what a price chart should show. `daily_prices` stores ADJUSTED close
    (auto_adjust=True) because returns/targets need split & dividend adjustment.
    The two are numerically different ON PURPOSE. Do not reconcile them.

Each series is in its OWN listing currency, never converted (same convention as
daily_prices). London names are in GBp (pence).

Fetch: yfinance, 2020-01-01 -> today, per ticker, with graceful failure — a ticker
that returns nothing is skipped and simply has no chart (the UI falls back).

USAGE (from repo root or dashboard/):
    python dashboard/fetch_ohlc.py             # fetch missing tickers
    python dashboard/fetch_ohlc.py --force     # re-fetch all
    python dashboard/fetch_ohlc.py --only AAPL,SHEL.L
    python dashboard/fetch_ohlc.py --report    # coverage only, writes nothing
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FINANCIALS_DB = ROOT / "data" / "financials.db"      # READ-ONLY here. Never written.
OHLC_DB = ROOT / "data" / "ohlc_display.db"          # the only file this script writes
START = "2020-01-01"

SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_ohlc (
    ticker  TEXT NOT NULL,
    date    TEXT NOT NULL,
    open    REAL,
    high    REAL,
    low     REAL,
    close   REAL,
    PRIMARY KEY (ticker, date)
);
CREATE INDEX IF NOT EXISTS idx_daily_ohlc_ticker ON daily_ohlc (ticker);
"""


def universe() -> list[str]:
    """Tickers from the modelling DB — opened READ-ONLY via a file: URI so this script
    cannot write to it even by accident."""
    uri = f"file:{FINANCIALS_DB.as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as con:
        return [r[0] for r in con.execute(
            "SELECT DISTINCT ticker FROM financial_facts ORDER BY ticker")]


def fetch_one(ticker: str):
    """Raw (unadjusted) OHLC for one ticker, or None. Never raises."""
    import yfinance as yf
    try:
        df = yf.download(ticker, start=START, end=date.today().isoformat(),
                         auto_adjust=False, progress=False, threads=False,
                         actions=False)
    except Exception:
        return None
    if df is None or df.empty:
        return None
    if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
        df = df.droplevel(1, axis=1)          # yfinance returns a MultiIndex for one ticker
    need = ["Open", "High", "Low", "Close"]
    if any(c not in df.columns for c in need):
        return None
    out = df[need].dropna(how="all")
    return out if len(out) else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    tickers = universe()
    if args.only:
        want = {t.strip().upper() for t in args.only.split(",")}
        tickers = [t for t in tickers if t.upper() in want]

    OHLC_DB.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(OHLC_DB)
    con.executescript(SCHEMA)

    have = {r[0] for r in con.execute(
        "SELECT ticker FROM daily_ohlc GROUP BY ticker HAVING COUNT(*) > 0")}

    if args.report:
        for t in tickers:
            n = con.execute("SELECT COUNT(*) FROM daily_ohlc WHERE ticker=?", (t,)).fetchone()[0]
            print(f"  {t:11s} {n:6d} rows" if n else f"  {t:11s}      - MISSING")
        print(f"\n=== {len(have & set(tickers))}/{len(tickers)} tickers cached ===")
        con.close()
        return

    ok, failed, skipped = [], [], []
    for t in tickers:
        if t in have and not args.force:
            skipped.append(t)
            continue
        df = fetch_one(t)
        if df is None:
            failed.append(t)
            print(f"  {t:11s} FAILED -> no chart (UI falls back gracefully)")
            continue
        rows = [(t, d.strftime("%Y-%m-%d"), float(o), float(h), float(l), float(c))
                for d, o, h, l, c in df.itertuples(index=True, name=None)]
        con.executemany("INSERT OR REPLACE INTO daily_ohlc "
                        "(ticker,date,open,high,low,close) VALUES (?,?,?,?,?,?)", rows)
        con.commit()
        ok.append(t)
        print(f"  {t:11s} {len(rows):6d} rows  {rows[0][1]} -> {rows[-1][1]}")

    total = con.execute("SELECT COUNT(*) FROM daily_ohlc").fetchone()[0]
    ntk = con.execute("SELECT COUNT(DISTINCT ticker) FROM daily_ohlc").fetchone()[0]
    con.close()

    print(f"\n=== fetched {len(ok)} · cached-skip {len(skipped)} · failed {len(failed)} ===")
    if failed:
        print("failed (fallback to no chart):", ", ".join(failed))
    print(f"{OHLC_DB} now holds {total:,} rows across {ntk} tickers")
    print("financials.db was NEVER opened for writing.")


if __name__ == "__main__":
    main()
