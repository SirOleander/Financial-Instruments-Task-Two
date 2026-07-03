"""
F_scores.py — analytical phase, step 2: sector-percentile scoring layer.

Turns the RAW per-company KPIs in `kpi_values` into CROSS-SECTIONAL percentile
scores → six sub-scores → financial_score, written to a NEW table `scores`.
Purely additive: never touches financial_facts / daily_prices / target_63d / kpi_values.

METHOD (see task brief + PROJECT_SPEC §2.1/§2.2/§2.5):
- Peer group = (sector, frequency, period). frequency = annual (10-K/annual) vs
  quarterly (10-Q/quarterly). period = calendar YEAR of fiscal_period_end_date for
  annual reports, calendar QUARTER (YYYYQn) for quarterly. Only same-group reports
  are ranked together; frequencies never mixed, periods never crossed. US + non-US
  names co-occur in the annual pools.
- Orient higher = better BEFORE ranking: INVERSE KPIs (debt_to_assets,
  net_debt_to_assets) are sign-flipped so lower raw ranks higher. (assets_to_equity /
  cost_to_income / efficiency_ratio / std-dev metrics aren't in kpi_values.)
- Percentile in [0,1], within group, over computable values only:
      pct(v) = (#values < v + 0.5*#values == v) / n     (mid-rank empirical CDF)
  n==1 -> 0.5. Not-computable KPIs are EXCLUDED from the ranking population.
- Sub-score = MEAN of its computable, oriented, percentile-ranked KPIs (sector-specific
  set, §2.5). Drop-and-renormalize: not-computable KPIs are dropped, never 0/mean-filled.
  All KPIs of a sub-score not-computable -> sub-score NOT computable (flag, NULL, no NaN).
- financial_score = MEAN of the computable six sub-scores.
- NO strategic_score / competitive_advantage_score here (separate later step).

USAGE (run from inside src/):
    python F_scores.py            # STEP 1 DRY-RUN: compute + preview, write NOTHING
    python F_scores.py --write    # STEP 2: create table + idempotent upsert + verify
"""
from __future__ import annotations

import bisect
import sys
from contextlib import closing

import B_database

ANNUAL_FORMS = {"10-K", "annual"}
INVERSE_KPIS = {"debt_to_assets", "net_debt_to_assets"}

SUBSCORES = ("profitability", "growth", "cash_flow", "leverage", "efficiency", "investment")

# per-sector KPI sets feeding each sub-score (PROJECT_SPEC §2.5). Only KPIs that exist
# in kpi_values are listed; spec KPIs we cannot compute are recorded here by name where
# useful (banks cash_flow) so the drop-and-renormalize / NC behaviour is explicit.
_GROWTH_FULL = ["revenue_growth_yoy", "operating_income_growth_yoy",
                "net_income_growth_yoy", "operating_cash_flow_growth_yoy"]
_CF_STD = ["operating_cash_flow_margin", "free_cash_flow_margin", "cash_conversion"]
_LEV_STD = ["debt_to_assets", "net_debt_to_assets", "cash_to_assets", "equity_ratio"]

SECTOR_SUBSCORES: dict[str, dict[str, list[str]]] = {
    "Technology": {
        "profitability": ["gross_margin", "operating_margin", "net_margin", "return_on_assets"],
        "growth": _GROWTH_FULL,
        "cash_flow": _CF_STD,
        "leverage": _LEV_STD,
        "efficiency": ["asset_turnover", "operating_income_to_assets", "return_on_assets"],
        "investment": ["r_and_d_intensity", "capex_intensity", "reinvestment_rate"],
    },
    "Communication": {
        "profitability": ["gross_margin", "operating_margin", "net_margin", "return_on_assets"],
        "growth": _GROWTH_FULL,
        "cash_flow": _CF_STD,
        "leverage": _LEV_STD,
        "efficiency": ["asset_turnover", "operating_income_to_assets", "return_on_assets"],
        "investment": ["capex_intensity", "reinvestment_rate"],  # content/network n/a
    },
    "Consumer Discretionary": {
        "profitability": ["gross_margin", "operating_margin", "net_margin", "return_on_assets"],
        "growth": _GROWTH_FULL,
        "cash_flow": _CF_STD,
        "leverage": _LEV_STD,
        "efficiency": ["asset_turnover", "inventory_turnover", "operating_income_to_assets"],
        "investment": ["capex_intensity", "reinvestment_rate"],
    },
    "Consumer Staples": {
        "profitability": ["gross_margin", "operating_margin", "net_margin", "return_on_assets"],
        "growth": _GROWTH_FULL,
        "cash_flow": _CF_STD,
        "leverage": _LEV_STD,
        "efficiency": ["asset_turnover", "inventory_turnover", "operating_income_to_assets"],
        "investment": ["capex_intensity", "reinvestment_rate"],
    },
    "Healthcare": {
        "profitability": ["gross_margin", "operating_margin", "net_margin", "return_on_assets"],
        "growth": _GROWTH_FULL,
        "cash_flow": _CF_STD,
        "leverage": _LEV_STD,
        "efficiency": ["asset_turnover", "operating_income_to_assets", "return_on_assets"],
        "investment": ["r_and_d_intensity", "capex_intensity", "reinvestment_rate"],
    },
    "Banks": {
        "profitability": ["return_on_assets", "return_on_equity", "net_interest_margin"],
        "growth": ["revenue_growth_yoy", "net_income_growth_yoy"],  # loan/deposit growth n/a
        # spec bank cash_flow proxies (net_income_stability, provision_coverage) are absent;
        # per §2.5 "operating_cash_flow (only if meaningful)" we opt in the computable
        # OCF-based ratios so banks get a real cash_flow_score.
        "cash_flow": ["operating_cash_flow_margin", "cash_conversion"],
        "leverage": ["equity_ratio"],  # assets_to_equity / CET1 / tier1 n/a
        "efficiency": ["asset_turnover"],  # efficiency_ratio / noninterest n/a
        "investment": ["capital_retention"],  # loan/deposit growth n/a
    },
    "Financial Services": {
        "profitability": ["operating_margin", "net_margin", "return_on_assets", "return_on_equity"],
        "growth": ["revenue_growth_yoy", "operating_income_growth_yoy", "net_income_growth_yoy"],
        "cash_flow": _CF_STD,
        "leverage": ["debt_to_assets", "net_debt_to_assets", "equity_ratio"],
        "efficiency": ["asset_turnover", "operating_income_to_assets"],  # cost_to_income n/a
        "investment": ["capex_intensity", "reinvestment_rate"],  # acquisition_intensity n/a
    },
    "Industrials": {
        "profitability": ["gross_margin", "operating_margin", "net_margin", "return_on_assets"],
        "growth": _GROWTH_FULL,
        "cash_flow": _CF_STD,
        "leverage": _LEV_STD,
        "efficiency": ["asset_turnover", "inventory_turnover", "operating_income_to_assets"],
        "investment": ["capex_intensity", "reinvestment_rate"],
    },
    "Energy, Materials & Utilities": {
        "profitability": ["operating_margin", "net_margin", "return_on_assets", "return_on_equity"],
        "growth": _GROWTH_FULL,
        "cash_flow": _CF_STD,
        "leverage": _LEV_STD,
        "efficiency": ["asset_turnover", "operating_income_to_assets", "return_on_assets"],
        "investment": ["capex_intensity", "reinvestment_rate"],  # fcf_after_capex undefined
    },
}


def _freq(form: str) -> str:
    return "annual" if form in ANNUAL_FORMS else "quarterly"


def _period(freq: str, period_end: str) -> str:
    y = int(period_end[:4])
    if freq == "annual":
        return str(y)
    m = int(period_end[5:7])
    return f"{y}Q{(m - 1) // 3 + 1}"


def load_kpis() -> list[dict]:
    with closing(B_database.get_connection()) as con:
        rows = con.execute(
            """
            SELECT ticker, report_release_date, fiscal_period_end_date, source, form,
                   sector, kpi_name, value, computable
            FROM kpi_values
            """
        ).fetchall()
    return [dict(r) for r in rows]


def _mean(xs: list[float]):
    return sum(xs) / len(xs) if xs else None


def build_scores(kpis: list[dict]):
    """Return (score_rows, diagnostics)."""
    # index reports and group members
    reports: dict[tuple, dict] = {}
    groups: dict[tuple, set] = {}          # (sector,freq,period) -> set of report keys
    # per (sector,freq,period,kpi): list of (report_key, oriented_value)
    kpi_groups: dict[tuple, list] = {}

    for r in kpis:
        rk = (r["ticker"], r["report_release_date"])
        freq = _freq(r["form"])
        period = _period(freq, r["fiscal_period_end_date"])
        if rk not in reports:
            reports[rk] = {
                "ticker": r["ticker"],
                "report_release_date": r["report_release_date"],
                "fiscal_period_end_date": r["fiscal_period_end_date"],
                "source": r["source"],
                "form": r["form"],
                "sector": r["sector"],
                "frequency": freq,
                "period": period,
            }
        gk = (r["sector"], freq, period)
        groups.setdefault(gk, set()).add(rk)
        if r["computable"] and r["value"] is not None:
            oriented = -r["value"] if r["kpi_name"] in INVERSE_KPIS else r["value"]
            kpi_groups.setdefault((*gk, r["kpi_name"]), []).append((rk, oriented))

    # percentile each (group, kpi)
    pct: dict[tuple, float] = {}           # (report_key, kpi_name) -> percentile
    for (sector, freq, period, kpi), pairs in kpi_groups.items():
        vals = sorted(v for _, v in pairs)
        n = len(vals)
        for rk, v in pairs:
            below = bisect.bisect_left(vals, v)
            equal = bisect.bisect_right(vals, v) - below
            pct[(rk, kpi)] = (below + 0.5 * equal) / n

    # assemble score rows
    score_rows: list[dict] = []
    nc_by_sector_sub: dict[tuple, int] = {}
    for rk, meta in reports.items():
        sector = meta["sector"]
        gk = (sector, meta["frequency"], meta["period"])
        peer_size = len(groups[gk])
        sub_vals: dict[str, float | None] = {}
        for sub in SUBSCORES:
            kpi_list = SECTOR_SUBSCORES[sector][sub]
            ps = [pct[(rk, k)] for k in kpi_list if (rk, k) in pct]
            sub_vals[sub] = _mean(ps)
            if sub_vals[sub] is None:
                nc_by_sector_sub[(sector, sub)] = nc_by_sector_sub.get((sector, sub), 0) + 1
        computable_subs = [v for v in sub_vals.values() if v is not None]
        fin = _mean(computable_subs)
        row = {**meta, "peer_group_size": peer_size,
               "financial_score": fin, "financial_computable": 1 if fin is not None else 0}
        for sub in SUBSCORES:
            row[f"{sub}_score"] = sub_vals[sub]
            row[f"{sub}_computable"] = 1 if sub_vals[sub] is not None else 0
        score_rows.append(row)

    diagnostics = {
        "groups": groups,
        "nc_by_sector_sub": nc_by_sector_sub,
        "reports": reports,
    }
    return score_rows, diagnostics


# --------------------------------------------------------------------------- #
# preview
# --------------------------------------------------------------------------- #
def _fmt(v):
    return f"{v:.4f}" if v is not None else "  NC  "


def preview(score_rows: list[dict], diag: dict) -> None:
    by_key = {(r["ticker"], r["report_release_date"]): r for r in score_rows}

    def show(ticker, freq=None, note=""):
        cands = [r for r in score_rows if r["ticker"] == ticker
                 and (freq is None or r["frequency"] == freq)]
        if not cands:
            print(f"\n### {ticker} ({freq}): NONE"); return
        r = max(cands, key=lambda x: x["report_release_date"])
        print(f"\n### {r['ticker']} [{r['sector']}] {r['form']} {r['frequency']} "
              f"period={r['period']} release={r['report_release_date']} "
              f"peers={r['peer_group_size']}  {note}")
        parts = " ".join(f"{s[:4]}={_fmt(r[s + '_score'])}" for s in SUBSCORES)
        print(f"    {parts}")
        print(f"    financial_score = {_fmt(r['financial_score'])}")

    print("=" * 92)
    print("STEP 1 PREVIEW — sector-percentile scores. Nothing written.")
    print("=" * 92)
    show("AAPL", "quarterly", "tech quarterly")
    show("AAPL", "annual", "tech annual")
    show("SAP.DE", "annual", "non-US tech annual (US+non-US pool)")
    show("PM", None, "neg equity — profitability still computes (ROE dropped, others kept)")
    show("GE", None, "operating KPIs dropped — sub-scores renormalize, not zeroed")
    show("TD.TO", None, "bank — leverage=equity_ratio, cash_flow NC (spec proxies n/a)")

    # range + NaN check
    vals = []
    for r in score_rows:
        for s in SUBSCORES:
            vals.append(r[f"{s}_score"])
        vals.append(r["financial_score"])
    nums = [v for v in vals if v is not None]
    nan = [v for v in nums if v != v]
    oob = [v for v in nums if v < 0 or v > 1]
    print("\n" + "=" * 92)
    print(f"RANGE/NaN CHECK: {len(nums)} numeric score values | NaNs={len(nan)} | "
          f"out-of-[0,1]={len(oob)} | min={min(nums):.4f} max={max(nums):.4f}")

    # NC sub-scores by sector
    print("\nNOT-COMPUTABLE sub-scores (sector, sub-score -> count of reports):")
    for (sector, sub), c in sorted(diag["nc_by_sector_sub"].items()):
        print(f"    {sector:32} {sub:14} {c}")

    # peer-group size distribution
    sizes = sorted(len(v) for v in diag["groups"].values())
    print(f"\nPEER-GROUP (sector,freq,period) COUNT: {len(sizes)} groups | "
          f"size min={sizes[0]} median={sizes[len(sizes)//2]} max={sizes[-1]}")
    small_groups = [g for g, v in diag["groups"].items() if len(v) < 5]
    rows_small = sum(r["peer_group_size"] < 5 for r in score_rows)
    print(f"  groups with <5 peers: {len(small_groups)}  |  score rows ranked in <5-peer "
          f"groups: {rows_small} of {len(score_rows)}")
    import collections
    hist = collections.Counter(min(s, 10) for s in sizes)
    print("  size histogram (10 = 10+):  " +
          "  ".join(f"{k}:{hist[k]}" for k in sorted(hist)))

    # co-occurrence proof: one annual Technology group's members
    tech_annual = {g: v for g, v in diag["groups"].items()
                   if g[0] == "Technology" and g[1] == "annual"}
    if tech_annual:
        gk = max(tech_annual, key=lambda g: len(tech_annual[g]))
        members = sorted(tech_annual[gk])
        srcs = {diag["reports"][rk]["source"] for rk in members}
        print(f"\nANNUAL POOL PROOF — Technology {gk[2]} ({len(members)} members, "
              f"sources={sorted(srcs)}):")
        print("    " + ", ".join(rk[0] for rk in members))

    print(f"\nTOTAL score rows: {len(score_rows)} across "
          f"{len({r['ticker'] for r in score_rows})} tickers")


# --------------------------------------------------------------------------- #
# write
# --------------------------------------------------------------------------- #
SCORE_COLUMNS = (
    ["ticker", "report_release_date", "fiscal_period_end_date", "source", "form",
     "sector", "frequency", "period", "peer_group_size"]
    + [f"{s}_score" for s in SUBSCORES] + [f"{s}_computable" for s in SUBSCORES]
    + ["financial_score", "financial_computable"]
)


def create_table() -> None:
    cols = [
        "ticker TEXT NOT NULL", "report_release_date TEXT NOT NULL",
        "fiscal_period_end_date TEXT", "source TEXT", "form TEXT", "sector TEXT",
        "frequency TEXT", "period TEXT", "peer_group_size INTEGER",
    ]
    for s in SUBSCORES:
        cols.append(f"{s}_score REAL")
        cols.append(f"{s}_computable INTEGER NOT NULL")
    cols += ["financial_score REAL", "financial_computable INTEGER NOT NULL",
             "created_at TEXT DEFAULT CURRENT_TIMESTAMP"]
    ddl = ("CREATE TABLE IF NOT EXISTS scores (\n  " + ",\n  ".join(cols)
           + ",\n  PRIMARY KEY (ticker, report_release_date)\n)")
    with closing(B_database.get_connection()) as con:
        con.execute(ddl)
        con.execute("CREATE INDEX IF NOT EXISTS idx_scores_grp ON scores (sector, frequency, period)")
        con.commit()


def _counts(con) -> dict:
    return {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("financial_facts", "daily_prices", "target_63d", "kpi_values")}


def write(score_rows: list[dict]) -> None:
    create_table()
    placeholders = ", ".join(f":{c}" for c in SCORE_COLUMNS)
    collist = ", ".join(SCORE_COLUMNS)
    with closing(B_database.get_connection()) as con:
        before = _counts(con)
        con.executemany(
            f"INSERT OR REPLACE INTO scores ({collist}) VALUES ({placeholders})",
            [{c: r[c] for c in SCORE_COLUMNS} for r in score_rows],
        )
        con.commit()
        after = _counts(con)
        n = con.execute("SELECT COUNT(*) FROM scores").fetchone()[0]
        nt = con.execute("SELECT COUNT(DISTINCT ticker) FROM scores").fetchone()[0]
        # written-data NaN/range check
        bad = con.execute(
            "SELECT COUNT(*) FROM scores WHERE financial_score IS NOT NULL AND "
            "(financial_score < 0 OR financial_score > 1)"
        ).fetchone()[0]
    print(f"\nWrote {n} rows to scores — {nt} distinct tickers. "
          f"financial_score out-of-[0,1]: {bad}")
    print("Untouched-table row counts:")
    for t in before:
        flag = "UNCHANGED" if before[t] == after[t] else "CHANGED! investigate"
        print(f"   {t:16} {before[t]} -> {after[t]}  ({flag})")


def main(do_write: bool = False) -> None:
    kpis = load_kpis()
    score_rows, diag = build_scores(kpis)
    preview(score_rows, diag)
    if not do_write:
        print("\nSTEP 1 DRY-RUN complete. Nothing written. Re-run with --write after review.")
        return
    write(score_rows)
    print("\nSTEP 2 complete.")


if __name__ == "__main__":
    main(do_write="--write" in sys.argv)
