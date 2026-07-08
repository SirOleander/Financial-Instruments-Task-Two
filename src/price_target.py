"""
price_target.py — STAGE 3: forward 63-trading-day target.

For each distinct (ticker, report_release_date) in financial_facts, using that
ticker's OWN daily_prices series (its own exchange calendar):
  - t+1 = first trading day with date STRICTLY > release_date; window = t+1..t+63
    (63 rows). If fewer than 63 trading days exist after release, target = NULL
    and the pair is FLAGGED (recent report, no full forward window).
  - daily_returns   = adjusted_close.pct_change() within the window (62 returns)
  - future_63d_return     = close[t+63] / close[t+1] - 1   (RAW price return, never excess)
  - future_63d_volatility = std(daily_returns)              (sample std, ddof=1)
  - future_63d_sharpe     = mean(daily_returns - rf_daily) / std(daily_returns) * sqrt(252)
    EXCESS Sharpe over a CONSTANT risk-free rate. Sharpe is the modelling target.

RISK-FREE RATE (A_config.RISK_FREE_RATE_ANNUAL = 0.02, the single definition; see the
rationale + FRED TB3MS source there). FREQUENCY CONVERSION — the rate is ANNUALIZED, the
returns are DAILY, so the raw 2% is NEVER subtracted from a daily (or 63-day) return:

    rf_daily = RISK_FREE_RATE_ANNUAL / 252            (simple, matching the arithmetic
                                                       sqrt(252) annualization below)
    excess_d = daily_returns - rf_daily               (subtracted PER DAY, before mean/std)
    sharpe   = mean(excess_d) / std(excess_d) * sqrt(252)

std(excess_d) == std(daily_returns) exactly, because rf_daily is a CONSTANT and subtracting
a constant does not change dispersion. `future_63d_volatility` is therefore unchanged by the
rf, and the whole change collapses to the closed form

    sharpe_rf  =  sharpe_rf0  -  RISK_FREE_RATE_ANNUAL / annualized_vol
    where annualized_vol = future_63d_volatility * sqrt(252)

which is the audit identity used to verify this change. NOTE it is NOT a constant shift: the
penalty is inversely proportional to each name's volatility, so low-vol names are penalized
MORE. Rank ordering therefore changes slightly (it is not a pure monotone transform).

Results go in a NEW table `target_63d` keyed on (ticker, report_release_date),
carrying fiscal_period_end_date + source for later joins. NEVER touches
financial_facts. Idempotent: INSERT OR REPLACE on the key. `future_63d_sharpe_rf0` (the
pre-rf value) and `risk_free_annual` are persisted alongside as an audit trail.

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

import A_config
import B_database

TRADING_DAYS_PER_YEAR = A_config.TRADING_DAYS_PER_YEAR
WINDOW = 63  # forward trading-day window length (rows t+1 .. t+63)

RISK_FREE_ANNUAL = A_config.RISK_FREE_RATE_ANNUAL
RF_DAILY = A_config.risk_free_per_period(TRADING_DAYS_PER_YEAR)  # 0.02 / 252


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
                future_63d_sharpe_rf0   REAL,
                risk_free_annual        REAL,
                status                  TEXT,
                created_at              TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (ticker, report_release_date)
            )
            """
        )
        # additive migration for a table created before the rf change (CREATE IF NOT EXISTS
        # no-ops on an existing table, so the two audit columns must be ALTERed in)
        have = {r["name"] for r in con.execute("PRAGMA table_info(target_63d)")}
        for col in ("future_63d_sharpe_rf0", "risk_free_annual"):
            if col not in have:
                con.execute(f"ALTER TABLE target_63d ADD COLUMN {col} REAL")
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
            "future_63d_sharpe_rf0": None,
            "risk_free_annual": RISK_FREE_ANNUAL,
            "status": "insufficient_window",
        }

    window = closes[i0:i0 + WINDOW]              # 63 prices
    daily_returns = [window[k] / window[k - 1] - 1 for k in range(1, WINDOW)]  # 62 returns
    # EXCESS daily returns: the annualized rf is frequency-converted to DAILY first, then
    # subtracted from EACH day. Never subtract the annual 2% from a daily/63-day return.
    excess_returns = [r - RF_DAILY for r in daily_returns]
    mean_excess = statistics.fmean(excess_returns)
    # std(excess) == std(raw): subtracting a constant does not change dispersion. Volatility
    # is reported on the RAW returns (it is a property of the price series, not of the rf).
    vol = statistics.stdev(daily_returns)         # sample std (ddof=1)
    ann = math.sqrt(TRADING_DAYS_PER_YEAR)
    sharpe = (mean_excess / vol) * ann if vol > 0 else None
    sharpe_rf0 = (statistics.fmean(daily_returns) / vol) * ann if vol > 0 else None
    return {
        "t1_date": dates[i0],
        "t63_date": dates[i0 + WINDOW - 1],
        "n_forward_days": WINDOW,
        "future_63d_return": window[-1] / window[0] - 1,   # RAW price return (not excess)
        "future_63d_volatility": vol,
        "future_63d_sharpe": sharpe,
        "future_63d_sharpe_rf0": sharpe_rf0,
        "risk_free_annual": RISK_FREE_ANNUAL,
        "status": "ok" if sharpe is not None else "zero_volatility",
    }


def main(write: bool = False) -> None:
    mode = "WRITE (create table + upsert)" if write else "DRY-RUN (compute + report, no writes)"
    print(f"price_target — STAGE 3 — {mode}\n" + "=" * 84)
    print(f"risk-free = {RISK_FREE_ANNUAL:.2%} annualized (3-month T-bill proxy, FRED TB3MS) "
          f"-> rf_daily = {RISK_FREE_ANNUAL:.4f}/{TRADING_DAYS_PER_YEAR} = {RF_DAILY:.9f}")

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
        print(f"\n--- future_63d_sharpe distribution (real targets, rf={RISK_FREE_ANNUAL:.0%}) ---")
        print(f"  n={len(sharpes)}  min={sharpes[0]:+.3f}  "
              f"median={statistics.median(sharpes):+.3f}  max={sharpes[-1]:+.3f}  "
              f"mean={statistics.fmean(sharpes):+.3f}")
        s0 = sorted(r["future_63d_sharpe_rf0"] for r in ok)
        print(f"  (rf=0 reference: median={statistics.median(s0):+.3f}  "
              f"mean={statistics.fmean(s0):+.3f})")

    # ---- AUDIT IDENTITY: sharpe_rf == sharpe_rf0 - rf_annual / annualized_vol, exactly ----
    worst = 0.0
    for r in ok:
        ann_vol = r["future_63d_volatility"] * math.sqrt(TRADING_DAYS_PER_YEAR)
        worst = max(worst, abs(r["future_63d_sharpe"]
                               - (r["future_63d_sharpe_rf0"] - RISK_FREE_ANNUAL / ann_vol)))
    print(f"\n--- AUDIT: max |sharpe_rf - (sharpe_rf0 - rf/ann_vol)| over {len(ok)} rows "
          f"= {worst:.2e}  ({'PASS' if worst < 1e-9 else 'FAIL'})")

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
               future_63d_return, future_63d_volatility, future_63d_sharpe,
               future_63d_sharpe_rf0, risk_free_annual, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (r["ticker"], r["report_release_date"], r["fiscal_period_end_date"],
                 r["source"], r["t1_date"], r["t63_date"], r["n_forward_days"],
                 r["future_63d_return"], r["future_63d_volatility"],
                 r["future_63d_sharpe"], r["future_63d_sharpe_rf0"],
                 r["risk_free_annual"], r["status"])
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
