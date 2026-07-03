"""
price_target.py — STAGE 3: forward 63-trading-day target.

For each distinct (ticker, report_release_date) in financial_facts, using that
ticker's OWN daily_prices series (its own exchange calendar):
  - t+1 = first trading day with date STRICTLY > release_date; window = t+1..t+63
    (63 rows). If fewer than 63 trading days exist after release, target = NULL
    and the pair is FLAGGED (recent report, no full forward window).
  - daily_returns   = adjusted_close.pct_change() within the window (62 returns)
  - future_63d_return     = close[t+63] / close[t+1] - 1
  - future_63d_volatility = std(daily_returns)              (sample std, ddof=1)
  - future_63d_sharpe     = mean(daily_returns) / std(daily_returns) * sqrt(252)
    RISK-FREE = 0 (stated). Sharpe is the modelling target.

Results go in a NEW table `target_63d` keyed on (ticker, report_release_date),
carrying fiscal_period_end_date + source for later joins. NEVER touches
financial_facts. Idempotent: INSERT OR REPLACE on the key.

USAGE (run from inside src/):
    python price_target.py            # DRY-RUN: compute + report + self-check, no writes
    python price_target.py --write    # also create table + upsert targets
"""
from __future__ import annotations

import bisect
import math
import statistics
import sys
from contextlib import closing

import B_database

TRADING_DAYS_PER_YEAR = 252
WINDOW = 63  # forward trading-day window length (rows t+1 .. t+63)


def create_target_table() -> None:
    with closing(B_database.get_connection()) as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS target_63d (
                ticker                  TEXT NOT NULL,
                report_release_date     TEXT NOT NULL,
                fiscal_period_end_date  TEXT,
                source                  TEXT,
                t1_date                 TEXT,
                t63_date                TEXT,
                n_forward_days          INTEGER,
                future_63d_return       REAL,
                future_63d_volatility   REAL,
                future_63d_sharpe       REAL,
                status                  TEXT,
                created_at              TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (ticker, report_release_date)
            )
            """
        )
        con.commit()


def load_price_series() -> dict[str, tuple[list[str], list[float]]]:
    """ticker -> (dates ascending, adjusted_close aligned). Its own calendar."""
    with closing(B_database.get_connection()) as con:
        rows = con.execute(
            "SELECT ticker, date, adjusted_close FROM daily_prices ORDER BY ticker, date"
        ).fetchall()
    series: dict[str, tuple[list[str], list[float]]] = {}
    for r in rows:
        d, c = series.setdefault(r["ticker"], ([], []))
        d.append(r["date"])
        c.append(r["adjusted_close"])
    return series


def load_reports() -> list[dict]:
    """Distinct (ticker, report_release_date) with period-end + source."""
    with closing(B_database.get_connection()) as con:
        rows = con.execute(
            """
            SELECT ticker,
                   report_release_date,
                   MAX(fiscal_period_end_date) AS fiscal_period_end_date,
                   MAX(source)                 AS source
            FROM financial_facts
            WHERE report_release_date IS NOT NULL
            GROUP BY ticker, report_release_date
            ORDER BY ticker, report_release_date
            """
        ).fetchall()
    return [dict(r) for r in rows]


def compute_one(release: str, dates: list[str], closes: list[float]) -> dict:
    """t+1 = first row strictly after release; window = t+1..t+63 (63 rows)."""
    # first index whose date > release (strictly after — look-ahead safe)
    i0 = bisect.bisect_right(dates, release)
    available = len(dates) - i0
    if available < WINDOW:
        return {
            "t1_date": dates[i0] if i0 < len(dates) else None,
            "t63_date": None,
            "n_forward_days": max(available, 0),
            "future_63d_return": None,
            "future_63d_volatility": None,
            "future_63d_sharpe": None,
            "status": "insufficient_window",
        }

    window = closes[i0:i0 + WINDOW]              # 63 prices
    daily_returns = [window[k] / window[k - 1] - 1 for k in range(1, WINDOW)]  # 62 returns
    mean_r = statistics.fmean(daily_returns)
    vol = statistics.stdev(daily_returns)         # sample std (ddof=1)
    sharpe = (mean_r / vol) * math.sqrt(TRADING_DAYS_PER_YEAR) if vol > 0 else None
    return {
        "t1_date": dates[i0],
        "t63_date": dates[i0 + WINDOW - 1],
        "n_forward_days": WINDOW,
        "future_63d_return": window[-1] / window[0] - 1,
        "future_63d_volatility": vol,
        "future_63d_sharpe": sharpe,
        "status": "ok" if sharpe is not None else "zero_volatility",
    }


def main(write: bool = False) -> None:
    mode = "WRITE (create table + upsert)" if write else "DRY-RUN (compute + report, no writes)"
    print(f"price_target — STAGE 3 — {mode}   [risk-free = 0]\n" + "=" * 84)

    series = load_price_series()
    reports = load_reports()
    print(f"reports (distinct ticker x release_date): {len(reports)} | "
          f"tickers with prices: {len(series)}")

    results: list[dict] = []
    missing_price_ticker: list[str] = []
    for rep in reports:
        tk = rep["ticker"]
        if tk not in series:
            missing_price_ticker.append(tk)
            continue
        dates, closes = series[tk]
        out = compute_one(rep["report_release_date"], dates, closes)
        results.append({**rep, **out})

    ok = [r for r in results if r["status"] == "ok"]
    insuff = [r for r in results if r["status"] == "insufficient_window"]
    zerovol = [r for r in results if r["status"] == "zero_volatility"]

    # ---- look-ahead self-check: sample edgar + yfinance triples ----
    def sample(source: str, n: int) -> list[dict]:
        picks = [r for r in ok if r["source"] == source]
        # spread across time: take a few evenly
        if len(picks) <= n:
            return picks
        step = len(picks) // n
        return [picks[i * step] for i in range(n)]

    print("\n--- LOOK-AHEAD SELF-CHECK: (release_date -> t+1 -> t+63), own calendar ---")
    print(f"{'ticker':12} {'src':9} {'release':12} {'t+1':12} {'t+63':12} "
          f"{'strictly_after':14} {'ret':>8} {'sharpe':>8}")
    for r in sample("edgar", 4) + sample("yfinance", 4):
        strict = "YES" if r["t1_date"] > r["report_release_date"] else "NO!!"
        print(f"{r['ticker']:12} {r['source']:9} {r['report_release_date']:12} "
              f"{r['t1_date']:12} {r['t63_date']:12} {strict:14} "
              f"{r['future_63d_return']:+8.3f} {r['future_63d_sharpe']:+8.2f}")

    # ---- counts ----
    print("\n--- COUNTS ---")
    print(f"  real target (ok):           {len(ok)}")
    if zerovol:
        print(f"  zero-volatility (NULL sharpe, ret kept): {len(zerovol)}")
    print(f"  NULL (insufficient window): {len(insuff)}")
    print(f"  total pairs:                {len(results)}")
    if missing_price_ticker:
        print(f"  !! reports with NO price series: {sorted(set(missing_price_ticker))}")

    if insuff:
        print("\n  insufficient-window pairs (recent reports, <63 fwd days) — FLAGGED:")
        for r in sorted(insuff, key=lambda x: x["report_release_date"]):
            print(f"     {r['ticker']:12} {r['source']:9} release {r['report_release_date']} "
                  f"(only {r['n_forward_days']} fwd rows)")

    # ---- distribution of sharpe ----
    sharpes = sorted(r["future_63d_sharpe"] for r in ok)
    if sharpes:
        print("\n--- future_63d_sharpe distribution (real targets) ---")
        print(f"  n={len(sharpes)}  min={sharpes[0]:+.3f}  "
              f"median={statistics.median(sharpes):+.3f}  max={sharpes[-1]:+.3f}  "
              f"mean={statistics.fmean(sharpes):+.3f}")

    if not write:
        print("\nDRY-RUN complete. Nothing written. Re-run with --write to persist targets.")
        return

    # ---- WRITE ----
    create_target_table()
    ff_before = None
    with closing(B_database.get_connection()) as con:
        ff_before = con.execute("SELECT COUNT(*) FROM financial_facts").fetchone()[0]
        con.executemany(
            """
            INSERT OR REPLACE INTO target_63d
              (ticker, report_release_date, fiscal_period_end_date, source,
               t1_date, t63_date, n_forward_days,
               future_63d_return, future_63d_volatility, future_63d_sharpe, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (r["ticker"], r["report_release_date"], r["fiscal_period_end_date"],
                 r["source"], r["t1_date"], r["t63_date"], r["n_forward_days"],
                 r["future_63d_return"], r["future_63d_volatility"],
                 r["future_63d_sharpe"], r["status"])
                for r in results
            ],
        )
        con.commit()
        ff_after = con.execute("SELECT COUNT(*) FROM financial_facts").fetchone()[0]
        n_tgt = con.execute("SELECT COUNT(*) FROM target_63d").fetchone()[0]
    print(f"\nWrote {n_tgt} rows to target_63d.")
    print(f"financial_facts rows: {ff_before} -> {ff_after} "
          f"({'UNCHANGED' if ff_before == ff_after else 'CHANGED! investigate'})")
    print("STAGE 3 complete.")


if __name__ == "__main__":
    main(write="--write" in sys.argv)
