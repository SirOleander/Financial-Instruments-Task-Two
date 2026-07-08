"""features.py — the feature pipeline: KPIs, sector scores, target, modelling table.

Merges four sequential DB->DB stages that were always run in order:
  kpis   (was E_kpis)        raw KPIs from financial_facts        -> kpi_values
  scores (was F_scores)      sector-percentile sub-scores         -> scores
  target (was price_target)  forward 63-day EXCESS Sharpe         -> target_63d
  table  (was H_modelling)   join features + target               -> modelling_data

NAME CLASHES RESOLVED ON MERGE (all module-local; the four never imported one another).
Each stage's colliding helpers keep their behaviour and internal call sites, renamed by a
per-stage prefix: main -> main_kpis/main_scores/main_target/main_modelling;
create_table -> kpis_/scores_/table_create_table; write -> kpis_/scores_/table_write;
_counts -> _kpis_/_scores_/_table_counts; preview -> kpis_/scores_preview;
load_reports -> kpis_load_reports / target_load_reports.

Two module constants were byte-IDENTICAL across stages and are defined ONCE here (the
in-body copies were removed; E_kpis's ANNUAL_FORMS was in fact dead there — defined, never
used): ANNUAL_FORMS and SUBSCORES.

The target stage keeps the rf=2% excess-Sharpe maths verbatim (rf_daily = 0.02/252,
subtracted per day; std unchanged; see config.RISK_FREE_RATE_ANNUAL).
"""
from __future__ import annotations

import bisect
import math
import statistics
import sys
from contextlib import closing

import numpy as np

from fi import config, db

# shared across stages — byte-identical in the source modules, defined once here.
ANNUAL_FORMS = {"10-K", "annual"}
SUBSCORES = ("profitability", "growth", "cash_flow", "leverage", "efficiency", "investment")




# ============================================================================
# STAGE: kpis (was E_kpis)
# ============================================================================

QUARTERLY_FORMS = {"10-Q", "quarterly"}
YOY_WINDOW = {"quarterly": (350, 381), "annual": (330, 400)}  # (min,max) days prior

# positions we need
NEEDED = [
    "revenue", "cost_of_revenue", "gross_profit", "operating_income", "net_income",
    "income_before_tax", "income_tax", "research_and_development",
    "total_assets", "total_equity", "cash_and_cash_equivalents",
    "short_term_debt", "long_term_debt", "total_debt", "inventory",
    "operating_cash_flow", "capital_expenditure",
    "net_interest_income", "retained_earnings",
]


# --------------------------------------------------------------------------- #
# load + assemble reports
# --------------------------------------------------------------------------- #
def _days(a: str, b: str) -> int:
    """calendar days a - b for ISO date strings (a,b like YYYY-MM-DD)."""
    from datetime import date
    ya, ma, da = map(int, a[:10].split("-"))
    yb, mb, db = map(int, b[:10].split("-"))
    return (date(ya, ma, da) - date(yb, mb, db)).days


def kpis_load_reports() -> list[dict]:
    """One record per (ticker, EFFECTIVE report date). On a same-day annual+quarterly
    collision, keep the quarterly form. positions = {pos: (value, missing_bool)}.

    EFFECTIVE report date = report_release_date, or fiscal_period_end_date when the release
    date is NULL. The blocked non-US names (MC.PA/CBA.AX/NESN.SW/RHHBY, and ALV.DE's one
    unmatched period) have NO usable release date, so they are keyed on their period-end
    here (a KEY surrogate only — never a target t=0; price_target still skips them, so they
    get target_missing downstream). Existing names all have real release dates, so their
    effective key == release date and their kpi_values are unchanged."""
    with closing(db.get_connection()) as con:
        rows = con.execute(
            """
            SELECT ticker, report_release_date, form, fiscal_period_end_date,
                   sector, company_group, source, position, value, selection_status
            FROM financial_facts
            """
        ).fetchall()

    grouped: dict[tuple, dict] = {}
    for r in rows:
        effective = r["report_release_date"] or r["fiscal_period_end_date"]
        key = (r["ticker"], effective)
        g = grouped.setdefault(key, {"forms": {}})
        form = r["form"]
        fm = g["forms"].setdefault(form, {
            "form": form,
            "fiscal_period_end_date": r["fiscal_period_end_date"],
            "sector": r["sector"],
            "company_group": r["company_group"],
            "source": r["source"],
            "positions": {},
        })
        fm["positions"][r["position"]] = (r["value"], r["selection_status"] == "missing")

    reports: list[dict] = []
    for (ticker, release), g in grouped.items():
        forms = g["forms"]
        quarterly = [f for f in forms if f in QUARTERLY_FORMS]
        chosen_key = quarterly[0] if quarterly else next(iter(forms))
        fm = forms[chosen_key]
        grain = "quarterly" if chosen_key in QUARTERLY_FORMS else "annual"
        reports.append({
            "ticker": ticker,
            "report_release_date": release,
            "form": fm["form"],
            "grain": grain,
            "fiscal_period_end_date": fm["fiscal_period_end_date"],
            "sector": fm["sector"],
            "company_group": fm["company_group"],
            "source": fm["source"],
            "positions": fm["positions"],
        })
    return reports


def attach_priors(reports: list[dict]) -> None:
    """For each report set report['prior'] = the same-grain YoY-prior report."""
    by_tg: dict[tuple, list[dict]] = {}
    for rep in reports:
        by_tg.setdefault((rep["ticker"], rep["grain"]), []).append(rep)
    for (_, grain), lst in by_tg.items():
        lst.sort(key=lambda r: r["fiscal_period_end_date"])
        lo, hi = YOY_WINDOW[grain]
        for rep in lst:
            pe = rep["fiscal_period_end_date"]
            match = None
            for cand in lst:
                gap = _days(pe, cand["fiscal_period_end_date"])
                if lo <= gap <= hi:
                    match = cand  # nearest within window (list is sorted ascending)
            rep["prior"] = match


# --------------------------------------------------------------------------- #
# value accessors honoring the missing rule
# --------------------------------------------------------------------------- #
def _avail(rep: dict | None, pos: str):
    """Return the value if present AND not missing, else None."""
    if rep is None:
        return None
    entry = rep["positions"].get(pos)
    if entry is None:
        return None
    value, missing = entry
    return None if missing else value


def _denom(rep: dict | None, pos: str):
    """Value usable as a denominator: present, non-missing, and non-zero."""
    v = _avail(rep, pos)
    return v if (v is not None and v != 0) else None


def _debt_sum(rep: dict):
    """short_term_debt + long_term_debt (each missing/absent -> 0). If both absent,
    fall back to total_debt. Always returns a number."""
    st = _avail(rep, "short_term_debt")
    lt = _avail(rep, "long_term_debt")
    if st is None and lt is None:
        td = _avail(rep, "total_debt")
        if td is not None:
            return td
    return (st or 0.0) + (lt or 0.0)


# --------------------------------------------------------------------------- #
# KPI computation for one report
# --------------------------------------------------------------------------- #
def compute_kpis(rep: dict) -> list[tuple[str, float | None]]:
    """Return [(kpi_name, value_or_None)] for the applicable KPIs of this report.
    None => not computable. KPIs that do not apply to the sector are omitted."""
    prior = rep.get("prior")
    sector = rep["sector"]
    is_energy = sector.startswith("Energy")
    is_bank = sector == "Banks"

    rev = _avail(rep, "revenue")
    rev_d = _denom(rep, "revenue")
    ta_d = _denom(rep, "total_assets")
    ni = _avail(rep, "net_income")
    ni_d = _denom(rep, "net_income")
    eq = _avail(rep, "total_equity")
    eq_pos = eq if (eq is not None and eq > 0) else None       # positive equity only
    cash = _avail(rep, "cash_and_cash_equivalents")
    gp = _avail(rep, "gross_profit")
    oi = _avail(rep, "operating_income")
    ocf = _avail(rep, "operating_cash_flow")
    capex = _avail(rep, "capital_expenditure")
    rnd = _avail(rep, "research_and_development")
    inv_d = _denom(rep, "inventory")
    cor = _avail(rep, "cost_of_revenue")
    itax = _avail(rep, "income_tax")
    ibt_d = _denom(rep, "income_before_tax")
    nii = _avail(rep, "net_interest_income")
    debt = _debt_sum(rep)

    out: list[tuple[str, float | None]] = []
    add = lambda name, v: out.append((name, v))

    def growth(pos: str, use_abs: bool):
        cur = _avail(rep, pos)
        prv = _avail(prior, pos) if prior else None
        if cur is None or prv is None or prv == 0:
            return None
        base = abs(prv) if use_abs else prv
        return (cur - prv) / base

    # profitability
    if not is_energy:
        add("gross_margin", gp / rev_d if (gp is not None and rev_d) else None)
    add("operating_margin", oi / rev_d if (oi is not None and rev_d) else None)
    add("net_margin", ni / rev_d if (ni is not None and rev_d) else None)
    add("return_on_assets", ni / ta_d if (ni is not None and ta_d) else None)
    add("return_on_equity", ni / eq_pos if (ni is not None and eq_pos) else None)

    # growth (YoY, true prior)
    add("revenue_growth_yoy", growth("revenue", use_abs=False))
    add("operating_income_growth_yoy", growth("operating_income", use_abs=True))
    add("net_income_growth_yoy", growth("net_income", use_abs=True))
    add("operating_cash_flow_growth_yoy", growth("operating_cash_flow", use_abs=True))

    # cash flow
    add("operating_cash_flow_margin", ocf / rev_d if (ocf is not None and rev_d) else None)
    fcf = (ocf - capex) if (ocf is not None and capex is not None) else None
    add("free_cash_flow", fcf)
    add("free_cash_flow_margin", fcf / rev_d if (fcf is not None and rev_d) else None)
    add("cash_conversion", ocf / ni_d if (ocf is not None and ni_d) else None)

    # leverage — banks get NO debt ratio (their debt isn't reported as
    # short/long/total_debt; leverage is scored via equity_ratio/assets_to_equity).
    # Non-bank sectors keep rule-3 missing->0, so genuine zero-debt names (ISRG) read ~0.
    if not is_bank:
        add("debt_to_assets", debt / ta_d if ta_d else None)
        add("net_debt_to_assets", (debt - cash) / ta_d if (cash is not None and ta_d) else None)
    add("cash_to_assets", cash / ta_d if (cash is not None and ta_d) else None)
    add("equity_ratio", eq_pos / ta_d if (eq_pos is not None and ta_d) else None)

    # efficiency
    add("asset_turnover", rev / ta_d if (rev is not None and ta_d) else None)
    add("operating_income_to_assets", oi / ta_d if (oi is not None and ta_d) else None)
    add("inventory_turnover", cor / inv_d if (cor is not None and inv_d) else None)

    # investment
    add("r_and_d_intensity", rnd / rev_d if (rnd is not None and rev_d) else None)
    add("capex_intensity", capex / rev_d if (capex is not None and rev_d) else None)
    add("reinvestment_rate",
        (rnd + capex) / rev_d if (rnd is not None and capex is not None and rev_d) else None)

    # ROIC
    tax_rate = itax / ibt_d if (itax is not None and ibt_d) else None
    roic_den = (debt + eq_pos - cash) if (eq_pos is not None and cash is not None) else None
    roic = None
    if oi is not None and tax_rate is not None and roic_den not in (None, 0):
        roic = (oi * (1 - tax_rate)) / roic_den
    add("ROIC", roic)

    # bank-only
    if is_bank:
        add("net_interest_margin", nii / ta_d if (nii is not None and ta_d) else None)
        if rep["grain"] == "annual":
            re_cur = _avail(rep, "retained_earnings")
            re_prv = _avail(prior, "retained_earnings") if prior else None
            cr = ((re_cur - re_prv) / ni_d
                  if (re_cur is not None and re_prv is not None and ni_d) else None)
            add("capital_retention", cr)
        else:
            add("capital_retention", None)  # quarterly grain: not computable by design

    return out


def build_all(reports: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for rep in reports:
        for name, value in compute_kpis(rep):
            rows.append({
                "ticker": rep["ticker"],
                "report_release_date": rep["report_release_date"],
                "fiscal_period_end_date": rep["fiscal_period_end_date"],
                "source": rep["source"],
                "form": rep["form"],
                "sector": rep["sector"],
                "company_group": rep["company_group"],
                "kpi_name": name,
                "value": value,
                "computable": 1 if value is not None else 0,
            })
    return rows


# --------------------------------------------------------------------------- #
# preview / reporting
# --------------------------------------------------------------------------- #
def _latest_report(reports: list[dict], ticker: str) -> dict | None:
    cands = [r for r in reports if r["ticker"] == ticker]
    return max(cands, key=lambda r: r["report_release_date"]) if cands else None


def kpis_preview(reports: list[dict], rows: list[dict]) -> None:
    def show(ticker: str, note: str = ""):
        rep = _latest_report(reports, ticker)
        if rep is None:
            print(f"\n### {ticker}: NOT FOUND")
            return
        kpis = dict(compute_kpis(rep))
        print(f"\n### {ticker}  [{rep['sector']}]  {rep['form']} "
              f"period_end={rep['fiscal_period_end_date']} release={rep['report_release_date']}"
              f"  prior={'yes' if rep.get('prior') else 'NONE'}   {note}")
        for name, v in kpis.items():
            tag = f"{v:+.4f}" if v is not None else "NOT COMPUTABLE"
            print(f"    {name:32} {tag}")

    print("=" * 84)
    print("STEP 1 PREVIEW — sample reports (latest per ticker). Nothing written.")
    print("=" * 84)
    show("AAPL", "clean tech — margins/ROA/ROE/ROIC should be sane")
    show("MSFT", "clean tech")
    show("PM", "negative equity — ROE/equity_ratio should be NOT COMPUTABLE")
    show("MCD", "negative equity — ROE/equity_ratio should be NOT COMPUTABLE")
    show("GE", "no operating_income — operating_margin/oi_to_assets/ROIC NOT COMPUTABLE")
    show("SHEL.L", "Energy — gross_margin omitted (not emitted)")
    show("SAP.DE", "non-US — quarterly growth mostly NOT COMPUTABLE (shallow history)")
    show("TD.TO", "bank — NIM + capital_retention; quarterly growth mostly NC")

    # per-KPI computable vs not-computable across ALL 89
    print("\n" + "=" * 84)
    print("PER-KPI computable vs not-computable (all reports, all 89 tickers)")
    print("=" * 84)
    agg: dict[str, list[int]] = {}
    for r in rows:
        a = agg.setdefault(r["kpi_name"], [0, 0])
        a[0 if r["computable"] else 1] += 1
    print(f"  {'kpi_name':32} {'computable':>11} {'not_comp':>10} {'total':>8}")
    for name in sorted(agg):
        c, n = agg[name]
        print(f"  {name:32} {c:>11} {n:>10} {c + n:>8}")
    print(f"\n  total KPI rows: {len(rows)} across "
          f"{len({r['ticker'] for r in rows})} tickers, {len(agg)} distinct KPIs")


# --------------------------------------------------------------------------- #
# write
# --------------------------------------------------------------------------- #
def kpis_create_table() -> None:
    with closing(db.get_connection()) as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS kpi_values (
                ticker                  TEXT NOT NULL,
                report_release_date     TEXT NOT NULL,
                fiscal_period_end_date  TEXT,
                source                  TEXT,
                form                    TEXT,
                sector                  TEXT,
                company_group           TEXT,
                kpi_name                TEXT NOT NULL,
                value                   REAL,
                computable              INTEGER NOT NULL,
                created_at              TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (ticker, report_release_date, kpi_name)
            )
            """
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_kpi_ticker ON kpi_values (ticker)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_kpi_name ON kpi_values (kpi_name)")
        con.commit()


def _kpis_counts(con) -> dict:
    return {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("financial_facts", "daily_prices", "target_63d")}


def kpis_write(rows: list[dict]) -> None:
    kpis_create_table()
    with closing(db.get_connection()) as con:
        before = _kpis_counts(con)
        con.executemany(
            """
            INSERT OR REPLACE INTO kpi_values
              (ticker, report_release_date, fiscal_period_end_date, source, form,
               sector, company_group, kpi_name, value, computable)
            VALUES (:ticker, :report_release_date, :fiscal_period_end_date, :source,
                    :form, :sector, :company_group, :kpi_name, :value, :computable)
            """,
            rows,
        )
        con.commit()
        after = _kpis_counts(con)
        nk = con.execute("SELECT COUNT(*) FROM kpi_values").fetchone()[0]
        nt = con.execute("SELECT COUNT(DISTINCT ticker) FROM kpi_values").fetchone()[0]
        ndk = con.execute("SELECT COUNT(DISTINCT kpi_name) FROM kpi_values").fetchone()[0]

    print(f"\nWrote {nk} rows to kpi_values — {nt} distinct tickers, {ndk} distinct KPIs.")
    print("Untouched-table row counts:")
    for t in before:
        flag = "UNCHANGED" if before[t] == after[t] else "CHANGED! investigate"
        print(f"   {t:16} {before[t]} -> {after[t]}  ({flag})")


def main_kpis(do_write: bool = False) -> None:
    reports = kpis_load_reports()
    attach_priors(reports)
    rows = build_all(reports)
    kpis_preview(reports, rows)
    if not do_write:
        print("\nSTEP 1 DRY-RUN complete. Nothing written. Re-run with --write after review.")
        return
    kpis_write(rows)
    print("\nSTEP 2 complete.")


# ============================================================================
# STAGE: scores (was F_scores)
# ============================================================================

INVERSE_KPIS = {"debt_to_assets", "net_debt_to_assets"}


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
    with closing(db.get_connection()) as con:
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


def scores_preview(score_rows: list[dict], diag: dict) -> None:
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


def scores_create_table() -> None:
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
    with closing(db.get_connection()) as con:
        con.execute(ddl)
        con.execute("CREATE INDEX IF NOT EXISTS idx_scores_grp ON scores (sector, frequency, period)")
        con.commit()


def _scores_counts(con) -> dict:
    return {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("financial_facts", "daily_prices", "target_63d", "kpi_values")}


def scores_write(score_rows: list[dict]) -> None:
    scores_create_table()
    placeholders = ", ".join(f":{c}" for c in SCORE_COLUMNS)
    collist = ", ".join(SCORE_COLUMNS)
    with closing(db.get_connection()) as con:
        before = _scores_counts(con)
        con.executemany(
            f"INSERT OR REPLACE INTO scores ({collist}) VALUES ({placeholders})",
            [{c: r[c] for c in SCORE_COLUMNS} for r in score_rows],
        )
        con.commit()
        after = _scores_counts(con)
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


def main_scores(do_write: bool = False) -> None:
    kpis = load_kpis()
    score_rows, diag = build_scores(kpis)
    scores_preview(score_rows, diag)
    if not do_write:
        print("\nSTEP 1 DRY-RUN complete. Nothing written. Re-run with --write after review.")
        return
    scores_write(score_rows)
    print("\nSTEP 2 complete.")


# ============================================================================
# STAGE: target (was price_target)
# ============================================================================

TRADING_DAYS_PER_YEAR = config.TRADING_DAYS_PER_YEAR
WINDOW = 63  # forward trading-day window length (rows t+1 .. t+63)

RISK_FREE_ANNUAL = config.RISK_FREE_RATE_ANNUAL
RF_DAILY = config.risk_free_per_period(TRADING_DAYS_PER_YEAR)  # 0.02 / 252


def create_target_table() -> None:
    with closing(db.get_connection()) as con:
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
    with closing(db.get_connection()) as con:
        rows = con.execute(
            "SELECT ticker, date, adjusted_close FROM daily_prices ORDER BY ticker, date"
        ).fetchall()
    series: dict[str, tuple[list[str], list[float]]] = {}
    for r in rows:
        d, c = series.setdefault(r["ticker"], ([], []))
        d.append(r["date"])
        c.append(r["adjusted_close"])
    return series


def target_load_reports() -> list[dict]:
    """Distinct (ticker, report_release_date) with period-end + source."""
    with closing(db.get_connection()) as con:
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


def main_target(write: bool = False) -> None:
    mode = "WRITE (create table + upsert)" if write else "DRY-RUN (compute + report, no writes)"
    print(f"price_target — STAGE 3 — {mode}\n" + "=" * 84)
    print(f"risk-free = {RISK_FREE_ANNUAL:.2%} annualized (3-month T-bill proxy, FRED TB3MS) "
          f"-> rf_daily = {RISK_FREE_ANNUAL:.4f}/{TRADING_DAYS_PER_YEAR} = {RF_DAILY:.9f}")

    series = load_price_series()
    reports = target_load_reports()
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
    with closing(db.get_connection()) as con:
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


# ============================================================================
# STAGE: modelling table (was H_modelling)
# ============================================================================

# --------------------------------------------------------------------------- #
# feature definitions
# --------------------------------------------------------------------------- #
SCORE_FEATURES = [f"{s}_score" for s in SUBSCORES] + ["financial_score"]

# core KPI ratios used as DIRECT features. free_cash_flow (a native-currency LEVEL) is
# deliberately EXCLUDED — CLAUDE.md forbids the raw level cross-sectionally; the margin is
# kept. Sector-specific KPIs (inventory_turnover, net_interest_margin, capital_retention)
# are included: missing stays NULL for names/sectors where they don't apply.
KPI_FEATURES = [
    # profitability
    "gross_margin", "operating_margin", "net_margin", "return_on_assets", "return_on_equity",
    # growth
    "revenue_growth_yoy", "operating_income_growth_yoy", "net_income_growth_yoy",
    "operating_cash_flow_growth_yoy",
    # cash flow
    "operating_cash_flow_margin", "free_cash_flow_margin", "cash_conversion",
    # leverage
    "debt_to_assets", "net_debt_to_assets", "cash_to_assets", "equity_ratio",
    # efficiency
    "asset_turnover", "operating_income_to_assets", "inventory_turnover",
    # investment
    "r_and_d_intensity", "capex_intensity", "reinvestment_rate",
    # capital efficiency
    "ROIC",
    # bank-specific
    "net_interest_margin", "capital_retention",
]

# ratio-tail KPIs to winsorize (near-zero-denominator blow-ups). Kept as both _raw and
# winsorized (name stays the winsorized/model column).
WINSOR_KPIS = ["ROIC", "cash_conversion", "revenue_growth_yoy",
               "operating_income_growth_yoy", "net_income_growth_yoy",
               "operating_cash_flow_growth_yoy"]
WINSOR_TARGET = ["future_63d_sharpe"]

# every column that gets a *_change (current - prior)
CHANGE_COLS = SCORE_FEATURES + ["operative_score", "competitive_advantage_score_w050"] + KPI_FEATURES

WINSOR_LO_PCT, WINSOR_HI_PCT = 1.0, 99.0


# --------------------------------------------------------------------------- #
# load
# --------------------------------------------------------------------------- #
def load() -> list[dict]:
    """Build one in-memory row per (ticker, report_release_date) with all level features
    and the target. Spine = scores; strict-key joins to kpi_values / operative_scores /
    target_63d. Change features + winsorization are applied afterwards."""
    with closing(db.get_connection()) as con:
        score_rows = [dict(r) for r in con.execute("SELECT * FROM scores")]
        kpi_rows = [dict(r) for r in con.execute(
            "SELECT ticker, report_release_date, company_group, kpi_name, value, computable "
            "FROM kpi_values")]
        op_rows = [dict(r) for r in con.execute(
            "SELECT ticker, report_release_date, operative_score, status, source "
            "FROM operative_scores")]
        tgt_rows = [dict(r) for r in con.execute(
            "SELECT ticker, report_release_date, future_63d_return, future_63d_volatility, "
            "future_63d_sharpe, status FROM target_63d")]
        # surrogate keys: the blocked non-US names (and ALV.DE's one unmatched period) have
        # NULL report_release_date, so downstream they are keyed on fiscal_period_end_date.
        # Flag those rows: they get NO target (target_missing) and never train (floor).
        no_rd_keys = {(r["ticker"], r["fiscal_period_end_date"]) for r in con.execute(
            "SELECT DISTINCT ticker, fiscal_period_end_date FROM financial_facts "
            "WHERE report_release_date IS NULL")}

    # wide KPI pivot + company_group lookup
    kpi_wide: dict[tuple, dict] = {}
    cgroup: dict[tuple, str] = {}
    for r in kpi_rows:
        key = (r["ticker"], r["report_release_date"])
        cgroup.setdefault(key, r["company_group"])
        if r["kpi_name"] in KPI_FEATURES:
            kpi_wide.setdefault(key, {})[r["kpi_name"]] = (
                r["value"] if r["computable"] else None)

    # operative resolution:
    #   op_exact  = scored operative on the EXACT (ticker, release_date) key (US edgar names).
    #   op_20f    = per-ticker sorted scored 20-F operative rows keyed on their FILING date,
    #               used as a LOOK-AHEAD-SAFE as-of fallback for the internationals whose
    #               yfinance scoring dates never coincide with the 20-F filing date. Attach
    #               the most recent 20-F operative whose filing date is ON OR BEFORE the
    #               report release date (strictly no future 20-F). Integrated / no-20-F
    #               names have no scored 20-F row -> stay NULL.
    op_exact: dict[tuple, float] = {}
    op_20f: dict[str, list[tuple]] = {}
    for r in op_rows:
        if r["status"] != "scored" or r["operative_score"] is None:
            continue
        op_exact[(r["ticker"], r["report_release_date"])] = r["operative_score"]
    for r in op_rows:
        if r["status"] == "scored" and r["operative_score"] is not None and r["source"] == "edgar-20f":
            op_20f.setdefault(r["ticker"], []).append(
                (r["report_release_date"], r["operative_score"]))
    for lst in op_20f.values():
        lst.sort()

    def resolve_operative(ticker: str, release: str):
        """Return (score, match_kind, asof_date). exact -> as-of 20-F -> NULL."""
        v = op_exact.get((ticker, release))
        if v is not None:
            return v, "exact", release
        cands = [(d, s) for d, s in op_20f.get(ticker, []) if d <= release]
        if cands:
            d, s = cands[-1]  # most recent 20-F filed on or before the release date
            return s, "asof_20f", d
        return None, None, None

    tgt_map = {(r["ticker"], r["report_release_date"]): r for r in tgt_rows}

    rows: list[dict] = []
    for s in score_rows:
        key = (s["ticker"], s["report_release_date"])
        row: dict = {
            "ticker": s["ticker"],
            "sector": s["sector"],
            "company_group": cgroup.get(key),
            "source": s["source"],
            "form": s["form"],
            "frequency": s["frequency"],
            "period": s["period"],
            "report_release_date": s["report_release_date"],
            "fiscal_period_end_date": s["fiscal_period_end_date"],
            "peer_group_size": s["peer_group_size"],
        }
        # score-level features
        for col in SCORE_FEATURES:
            row[col] = s[col]

        # operative: exact same-date match, else look-ahead-safe as-of 20-F match.
        op_val, op_match, op_asof = resolve_operative(s["ticker"], s["report_release_date"])
        row["operative_score"] = op_val
        row["operative_missing"] = 0 if op_val is not None else 1
        row["operative_match"] = op_match          # 'exact' | 'asof_20f' | None
        row["operative_asof_date"] = op_asof        # 20-F filing date used (audit)

        # w=0.5 reporting column (fallback -> financial_score where operative missing)
        fin = row["financial_score"]
        if row["operative_missing"] == 0 and fin is not None:
            row["competitive_advantage_score_w050"] = 0.5 * fin + 0.5 * row["operative_score"]
        else:
            row["competitive_advantage_score_w050"] = fin  # fallback (may be None)

        # KPI level features (raw; winsorized copies added later)
        kw = kpi_wide.get(key, {})
        for k in KPI_FEATURES:
            row[k] = kw.get(k)  # None if not computable / absent

        # target (strict key; identical key set proven)
        t = tgt_map.get(key)
        if t is not None:
            row["future_63d_return"] = t["future_63d_return"]
            row["future_63d_volatility"] = t["future_63d_volatility"]
            row["future_63d_sharpe"] = t["future_63d_sharpe"]
        else:
            row["future_63d_return"] = row["future_63d_volatility"] = row["future_63d_sharpe"] = None
        row["target_missing"] = 1 if row["future_63d_sharpe"] is None else 0
        # surrogate-keyed (no real release date) -> report_release_date column holds the
        # period-end; flag it so the ranking/dashboard can show "no release date" honestly.
        row["no_release_date"] = 1 if key in no_rd_keys else 0

        rows.append(row)
    return rows


# --------------------------------------------------------------------------- #
# winsorization
# --------------------------------------------------------------------------- #
def winsorize(rows: list[dict]) -> dict:
    """For each winsor column store {col}_raw = original, {col} = clipped to [p1,p99]
    computed over all non-None values. Returns caps+counts for the report."""
    report: dict[str, dict] = {}
    for col in WINSOR_KPIS + WINSOR_TARGET:
        vals = np.array([r[col] for r in rows if r[col] is not None], dtype=float)
        if vals.size == 0:
            report[col] = {"n": 0, "lo": None, "hi": None, "capped_lo": 0, "capped_hi": 0}
            for r in rows:
                r[f"{col}_raw"] = r[col]
            continue
        lo = float(np.percentile(vals, WINSOR_LO_PCT))
        hi = float(np.percentile(vals, WINSOR_HI_PCT))
        capped_lo = capped_hi = 0
        for r in rows:
            v = r[col]
            r[f"{col}_raw"] = v
            if v is None:
                continue
            if v < lo:
                r[col] = lo
                capped_lo += 1
            elif v > hi:
                r[col] = hi
                capped_hi += 1
        report[col] = {"n": int(vals.size), "lo": lo, "hi": hi,
                       "capped_lo": capped_lo, "capped_hi": capped_hi}
    return report


# --------------------------------------------------------------------------- #
# change features (current - prior, prior = immediately-preceding report by release date)
# --------------------------------------------------------------------------- #
def add_change_features(rows: list[dict]) -> None:
    """Set first_obs and {col}_change for every CHANGE_COLS column. Prior = the
    immediately-preceding SAME-FREQUENCY report by release date (annual diffs against prior
    annual, quarterly against prior quarterly) — because financial_score is a WITHIN-
    frequency percentile, so cross-frequency diffs would mix ranking populations. Change
    uses the winsorized/model column value; NULL unless BOTH ends present. first_obs=1 means
    no same-frequency prior exists."""
    by_key: dict[tuple, list[dict]] = {}
    for r in rows:
        by_key.setdefault((r["ticker"], r["frequency"]), []).append(r)

    for lst in by_key.values():
        lst.sort(key=lambda r: r["report_release_date"])
        prev: dict | None = None
        for r in lst:
            r["first_obs"] = 1 if prev is None else 0
            r["prior_release_date"] = None if prev is None else prev["report_release_date"]
            for col in CHANGE_COLS:
                cur = r.get(col)
                pv = prev.get(col) if prev is not None else None
                r[f"{col}_change"] = (cur - pv) if (cur is not None and pv is not None) else None
            prev = r


# --------------------------------------------------------------------------- #
# STEP 1 report
# --------------------------------------------------------------------------- #
def _f(v):
    return f"{v:+.4f}" if isinstance(v, (int, float)) and v is not None else " NULL "


def report(rows: list[dict], wins: dict) -> None:
    n = len(rows)
    has_t = sum(r["target_missing"] == 0 for r in rows)
    first = sum(r["first_obs"] == 1 for r in rows)
    op_present = sum(r["operative_missing"] == 0 for r in rows)
    usable = sum(r["target_missing"] == 0 and r["first_obs"] == 0 for r in rows)

    print("=" * 92)
    print("STEP 1 DRY-RUN — modelling_data assembled IN MEMORY. NOTHING WRITTEN.")
    print("=" * 92)
    print(f"\nTOTAL rows: {n}   |   distinct tickers: {len({r['ticker'] for r in rows})}")
    print(f"  has-target ............ {has_t:5}     target_missing ...... {n - has_t}")
    print(f"  has-change (non-first)  {n - first:5}     first_obs (no prior)  {first}")
    print(f"  operative present ..... {op_present:5}     operative_missing ... {n - op_present}")
    print(f"  TRAIN-USABLE (target AND change) ......... {usable}")

    # operative coverage (exact same-date vs look-ahead-safe as-of 20-F vs missing)
    from collections import Counter
    match_by = Counter(r["operative_match"] or "MISSING" for r in rows)
    print("\n  operative coverage:")
    for k in ("exact", "asof_20f", "MISSING"):
        print(f"      {k:10} {match_by.get(k, 0)}")
    miss_by_src = Counter(r["source"] for r in rows if r["operative_missing"] == 1)
    print("  operative_missing by source:")
    for src, c in sorted(miss_by_src.items()):
        print(f"      {src:14} {c}")

    # as-of match proof: internationals now recovered, filing date <= release date
    print("\n  AS-OF 20-F MATCHES (proof: operative_asof_date <= report_release_date):")
    asof = [r for r in rows if r["operative_match"] == "asof_20f"]
    print(f"      {len(asof)} rows recovered across "
          f"{len({r['ticker'] for r in asof})} intl names")
    seen = set()
    for r in sorted(asof, key=lambda r: (r["ticker"], r["report_release_date"])):
        if r["ticker"] in seen:
            continue
        seen.add(r["ticker"])
        ok = "OK" if r["operative_asof_date"] <= r["report_release_date"] else "!! FUTURE !!"
        print(f"      {r['ticker']:10} release={r['report_release_date']} "
              f"<- 20-F filed {r['operative_asof_date']}  op={_f(r['operative_score'])}  {ok}")

    # ---- per-company observation-count distribution ----
    from collections import defaultdict
    per: dict[str, dict] = defaultdict(lambda: {"tot": 0, "tgt": 0, "chg": 0, "both": 0})
    for r in rows:
        p = per[r["ticker"]]
        p["tot"] += 1
        if r["target_missing"] == 0:
            p["tgt"] += 1
        if r["first_obs"] == 0:
            p["chg"] += 1
        if r["target_missing"] == 0 and r["first_obs"] == 0:
            p["both"] += 1

    print("\n" + "=" * 92)
    print("PER-COMPANY OBSERVATION COUNTS  (set the min-obs floor from this)")
    print("  tot=all rows | tgt=with target | chg=with change features | both=train-usable")
    print("=" * 92)
    print(f"  {'ticker':10} {'tot':>4} {'tgt':>4} {'chg':>4} {'both':>5}")
    for tk in sorted(per, key=lambda t: (per[t]["both"], per[t]["tot"])):
        p = per[tk]
        print(f"  {tk:10} {p['tot']:>4} {p['tgt']:>4} {p['chg']:>4} {p['both']:>5}")

    booth = sorted(p["both"] for p in per.values())
    tots = sorted(p["tot"] for p in per.values())
    print(f"\n  train-usable (both) per company: min={booth[0]} "
          f"median={booth[len(booth)//2]} max={booth[-1]}")
    hist = Counter(p["both"] for p in per.values())
    print("  histogram of train-usable-per-company (count : #companies):")
    for k in sorted(hist):
        print(f"      both={k:>3} : {hist[k]} companies   {'#'*hist[k]}")
    # cumulative "if floor = f, companies kept / rows kept"
    print("\n  floor sensitivity (floor on train-usable rows-per-company):")
    print(f"      {'floor':>6} {'companies_kept':>15} {'usable_rows_kept':>17}")
    for floor in (1, 2, 3, 4, 5, 6, 8, 10):
        comps = [tk for tk in per if per[tk]["both"] >= floor]
        rows_kept = sum(per[tk]["both"] for tk in comps)
        print(f"      {floor:>6} {len(comps):>15} {rows_kept:>17}")

    # ---- sample full rows ----
    print("\n" + "=" * 92)
    print("SAMPLE ROWS (eyeball features / changes / fallback / target / prior date)")
    print("=" * 92)

    def latest(ticker, freq=None):
        c = [r for r in rows if r["ticker"] == ticker
             and (freq is None or r["frequency"] == freq) and r["first_obs"] == 0]
        return max(c, key=lambda r: r["report_release_date"]) if c else None

    samples = [
        ("AAPL", "quarterly", "US quarterly"),
        ("MSFT", "annual", "US annual"),
        ("SAP.DE", "annual", "non-US annual"),
        ("PM", None, "negative-equity (ROE/equity_ratio NULL)"),
        ("7203.T", None, "intl — operative recovered via as-of 20-F match"),
        ("SHEL.L", None, "integrated 20-F (no scored operative) -> stays NULL"),
    ]
    for tk, freq, note in samples:
        r = latest(tk, freq)
        if r is None:
            print(f"\n### {tk}: no non-first row"); continue
        print(f"\n### {tk} [{r['sector']} / {r['company_group']}] {r['form']} {r['frequency']} "
              f"release={r['report_release_date']}  prior={r['prior_release_date']}  — {note}")
        print(f"    financial_score={_f(r['financial_score'])}  operative_score={_f(r['operative_score'])}"
              f"  match={r['operative_match']} asof={r['operative_asof_date']}"
              f"  cas_w050={_f(r['competitive_advantage_score_w050'])}")
        print(f"    sub-scores: " + " ".join(f"{s[:4]}={_f(r[s+'_score'])}" for s in SUBSCORES))
        print(f"    KPIs: ROA={_f(r['return_on_assets'])} ROE={_f(r['return_on_equity'])} "
              f"op_margin={_f(r['operating_margin'])} rev_g={_f(r['revenue_growth_yoy'])} "
              f"ROIC={_f(r['ROIC'])}(raw={_f(r['ROIC_raw'])})")
        print(f"    CHANGES: fin_chg={_f(r['financial_score_change'])} "
              f"op_chg={_f(r['operative_score_change'])} ROA_chg={_f(r['return_on_assets_change'])} "
              f"revg_chg={_f(r['revenue_growth_yoy_change'])}")
        print(f"    TARGET: ret={_f(r['future_63d_return'])} vol={_f(r['future_63d_volatility'])} "
              f"sharpe={_f(r['future_63d_sharpe'])}(raw={_f(r['future_63d_sharpe_raw'])}) "
              f"target_missing={r['target_missing']}")

    # ---- winsorization report ----
    print("\n" + "=" * 92)
    print("WINSORIZATION (1st/99th pct on FULL computable population)")
    print("  CAVEAT: final caps MUST be refit on TRAIN ONLY at split time (leakage-safe).")
    print("=" * 92)
    print(f"  {'column':34} {'n':>5} {'p1':>12} {'p99':>12} {'capped_lo':>10} {'capped_hi':>10}")
    for col, d in wins.items():
        lo = f"{d['lo']:.4f}" if d["lo"] is not None else "-"
        hi = f"{d['hi']:.4f}" if d["hi"] is not None else "-"
        print(f"  {col:34} {d['n']:>5} {lo:>12} {hi:>12} {d['capped_lo']:>10} {d['capped_hi']:>10}")

    # ---- NaN / integrity check ----
    feat_cols = (SCORE_FEATURES + ["operative_score", "competitive_advantage_score_w050"]
                 + KPI_FEATURES + [f"{c}_change" for c in CHANGE_COLS]
                 + ["future_63d_return", "future_63d_volatility", "future_63d_sharpe"])
    nan_hits = 0
    for r in rows:
        for c in feat_cols:
            v = r.get(c)
            if isinstance(v, float) and v != v:  # NaN
                nan_hits += 1
    print("\n" + "=" * 92)
    print(f"NaN CHECK across {len(feat_cols)} feature/target columns × {n} rows: "
          f"{nan_hits} NaN found (missing is NULL, never silent-NaN).")
    print("=" * 92)
    print("\nSTEP 1 complete. Review, then give the min-obs floor and I will --write.")


# --------------------------------------------------------------------------- #
# STEP 2 write
# --------------------------------------------------------------------------- #
def column_spec() -> list[tuple[str, str]]:
    """(name, sqltype) in write order."""
    cols: list[tuple[str, str]] = [
        ("ticker", "TEXT NOT NULL"), ("report_release_date", "TEXT NOT NULL"),
        ("fiscal_period_end_date", "TEXT"), ("sector", "TEXT"), ("company_group", "TEXT"),
        ("source", "TEXT"), ("form", "TEXT"), ("frequency", "TEXT"), ("period", "TEXT"),
        ("peer_group_size", "INTEGER"),
        ("first_obs", "INTEGER"), ("prior_release_date", "TEXT"),
        ("operative_missing", "INTEGER"), ("operative_match", "TEXT"),
        ("operative_asof_date", "TEXT"), ("target_missing", "INTEGER"),
        ("no_release_date", "INTEGER"), ("train_eligible", "INTEGER"),
    ]
    for c in SCORE_FEATURES + ["operative_score", "competitive_advantage_score_w050"]:
        cols.append((c, "REAL"))
    for k in KPI_FEATURES:
        cols.append((k, "REAL"))
        if k in WINSOR_KPIS:
            cols.append((f"{k}_raw", "REAL"))
    for c in ("future_63d_return", "future_63d_volatility", "future_63d_sharpe",
              "future_63d_sharpe_raw"):
        cols.append((c, "REAL"))
    for c in CHANGE_COLS:
        cols.append((f"{c}_change", "REAL"))
    return cols


def table_create_table() -> None:
    spec = column_spec()
    ddl = ("CREATE TABLE IF NOT EXISTS modelling_data (\n  "
           + ",\n  ".join(f"{n} {t}" for n, t in spec)
           + ",\n  created_at TEXT DEFAULT CURRENT_TIMESTAMP"
           + ",\n  PRIMARY KEY (ticker, report_release_date)\n)")
    with closing(db.get_connection()) as con:
        con.execute(ddl)
        con.execute("CREATE INDEX IF NOT EXISTS idx_md_grp ON modelling_data "
                    "(sector, frequency, period)")
        con.commit()


PROTECTED = ("financial_facts", "daily_prices", "target_63d", "kpi_values",
             "scores", "operative_scores")


def _table_counts(con) -> dict:
    return {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in PROTECTED}


def set_train_eligible(rows: list[dict], floor: int) -> set:
    """Mark train_eligible=1 on rows usable for TRAINING (NOT a delete). A row qualifies
    iff (a) its company has >= floor train-usable rows [target AND change], AND (b) the row
    itself has target AND change (not first_obs, not target_missing). Internationals below
    the floor and every first-obs / target-missing row are train_eligible=0 but RETAINED in
    modelling_data for prediction/ranking. Returns the set of qualifying companies."""
    from collections import Counter
    both = Counter()
    for r in rows:
        if r["target_missing"] == 0 and r["first_obs"] == 0:
            both[r["ticker"]] += 1
    qualifying = {tk for tk, c in both.items() if c >= floor}
    for r in rows:
        r["train_eligible"] = 1 if (
            r["ticker"] in qualifying and r["target_missing"] == 0 and r["first_obs"] == 0
        ) else 0
    return qualifying


def table_write(rows: list[dict], floor: int | None) -> None:
    """Set the train_eligible flag from the floor (retain-not-delete) then idempotent-upsert
    ALL rows of modelling_data."""
    floor = floor if floor is not None else 1
    qualifying = set_train_eligible(rows, floor)
    n_elig = sum(r["train_eligible"] for r in rows)
    n_pred = len(rows) - n_elig
    intl = sorted({r["ticker"] for r in rows if r["source"] != "edgar"})
    intl_elig = sum(r["train_eligible"] for r in rows if r["source"] != "edgar")
    print(f"train_eligible criterion: floor={floor} train-usable rows per company.")
    print(f"  qualifying companies (train): {len(qualifying)}")
    print(f"  train_eligible rows ...... {n_elig}")
    print(f"  prediction-only rows ..... {n_pred}")
    print(f"  internationals retained: {len(intl)} names, "
          f"{sum(r['source'] != 'edgar' for r in rows)} rows, "
          f"train_eligible among them = {intl_elig} (expected 0)")

    table_create_table()
    cols = [n for n, _ in column_spec()]
    placeholders = ", ".join(f":{c}" for c in cols)
    with closing(db.get_connection()) as con:
        before = _table_counts(con)
        con.executemany(
            f"INSERT OR REPLACE INTO modelling_data ({', '.join(cols)}) VALUES ({placeholders})",
            [{c: r.get(c) for c in cols} for r in rows],
        )
        con.commit()
        after = _table_counts(con)
        nm = con.execute("SELECT COUNT(*) FROM modelling_data").fetchone()[0]
        nt = con.execute("SELECT COUNT(DISTINCT ticker) FROM modelling_data").fetchone()[0]

    print(f"\nWrote {nm} rows to modelling_data — {nt} distinct tickers.")
    print("Protected-table row counts:")
    for t in before:
        flag = "UNCHANGED" if before[t] == after[t] else "CHANGED! investigate"
        print(f"   {t:16} {before[t]} -> {after[t]}  ({flag})")


# --------------------------------------------------------------------------- #
def build(rows_only: bool = False):
    rows = load()
    wins = winsorize(rows)
    add_change_features(rows)
    return (rows, wins)


def main_modelling(argv: list[str]) -> None:
    rows, wins = build()
    if "--write" in argv:
        floor = None
        for a in argv:
            if a.startswith("--floor="):
                floor = int(a.split("=", 1)[1])
        table_write(rows, floor)
        print("\nSTEP 2 complete.")
    else:
        report(rows, wins)
