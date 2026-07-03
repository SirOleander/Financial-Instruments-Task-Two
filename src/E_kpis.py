"""
E_kpis.py — analytical phase, step 1: RAW per-company KPI ratios.

Computes the PROJECT_SPEC §2.3 KPIs from `financial_facts`, one report at a time,
into a NEW long-format table `kpi_values`. RAW values only — NO percentile ranks,
NO sub-scores (that is the next, separate step). Purely additive: never touches
financial_facts / daily_prices / target_63d.

KEY RULES (see the task brief + CLAUDE.md):
- Missing IFF selection_status == 'missing' (never value == 0). A missing input
  makes its KPI NOT COMPUTABLE for that report — recorded as computable=0 / value NULL,
  never a fabricated 0 or NaN.
- Debt-sum exception: short_term_debt + long_term_debt, each MISSING → 0 in the sum.
  If BOTH are absent/missing but total_debt is present, use total_debt (position-name
  equivalence for the yfinance names). This 0-fill applies ONLY to the additive debt
  sum, never to a lone denominator.
- Banks get NO debt ratio: debt_to_assets / net_debt_to_assets are NOT emitted for the
  Banks sector (their debt isn't reported this way; leverage uses equity_ratio). Non-bank
  sectors keep missing->0, so genuine zero-debt names (e.g. ISRG) still read ~0.
- Negative book equity (total_equity <= 0): return_on_equity, equity_ratio and ROIC
  (equity in denominator) are NOT computable.
- GE has no operating_income → operating_margin / operating_income_to_assets / ROIC
  fall out as NOT computable automatically.
- Energy sector: gross_margin is NOT computed (no comparable cost/gross) — row omitted.
- YoY growth KPIs use the TRUE same-period-a-year-ago report (matched by same grain +
  fiscal_period_end_date ~1yr prior). No prior → not computable.

STATED CHOICES:
- Averages (return_on_equity, asset_turnover, inventory_turnover, net_interest_margin)
  use the single period-end balance, NOT a 2-point average (no prior fabricated).
- net_interest_margin = net_interest_income / total_assets (period-end proxy for
  average_earning_assets, which is not in the data). Banks only.
- capital_retention = (retained_earnings − prior-year retained_earnings) / net_income,
  ANNUAL-grain reports only (quarterly ΔRE-over-year vs quarterly NI is ~4x mismatched).
  Banks only.
- Form collision (a few yfinance FY+Q4 released same day, same period-end): prefer the
  QUARTERLY report for that release date.

USAGE (run from inside src/):
    python E_kpis.py            # STEP 1 DRY-RUN: compute + preview, write NOTHING
    python E_kpis.py --write    # STEP 2: create table + idempotent upsert + verify
"""
from __future__ import annotations

import sys
from contextlib import closing

import B_database

QUARTERLY_FORMS = {"10-Q", "quarterly"}
ANNUAL_FORMS = {"10-K", "annual"}
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


def load_reports() -> list[dict]:
    """One record per (ticker, report_release_date). On a same-day annual+quarterly
    collision, keep the quarterly form. positions = {pos: (value, missing_bool)}."""
    with closing(B_database.get_connection()) as con:
        rows = con.execute(
            """
            SELECT ticker, report_release_date, form, fiscal_period_end_date,
                   sector, company_group, source, position, value, selection_status
            FROM financial_facts
            WHERE report_release_date IS NOT NULL
            """
        ).fetchall()

    grouped: dict[tuple, dict] = {}
    for r in rows:
        key = (r["ticker"], r["report_release_date"])
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


def preview(reports: list[dict], rows: list[dict]) -> None:
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
def create_table() -> None:
    with closing(B_database.get_connection()) as con:
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


def _counts(con) -> dict:
    return {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("financial_facts", "daily_prices", "target_63d")}


def write(rows: list[dict]) -> None:
    create_table()
    with closing(B_database.get_connection()) as con:
        before = _counts(con)
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
        after = _counts(con)
        nk = con.execute("SELECT COUNT(*) FROM kpi_values").fetchone()[0]
        nt = con.execute("SELECT COUNT(DISTINCT ticker) FROM kpi_values").fetchone()[0]
        ndk = con.execute("SELECT COUNT(DISTINCT kpi_name) FROM kpi_values").fetchone()[0]

    print(f"\nWrote {nk} rows to kpi_values — {nt} distinct tickers, {ndk} distinct KPIs.")
    print("Untouched-table row counts:")
    for t in before:
        flag = "UNCHANGED" if before[t] == after[t] else "CHANGED! investigate"
        print(f"   {t:16} {before[t]} -> {after[t]}  ({flag})")


def main(do_write: bool = False) -> None:
    reports = load_reports()
    attach_priors(reports)
    rows = build_all(reports)
    preview(reports, rows)
    if not do_write:
        print("\nSTEP 1 DRY-RUN complete. Nothing written. Re-run with --write after review.")
        return
    write(rows)
    print("\nSTEP 2 complete.")


if __name__ == "__main__":
    main(do_write="--write" in sys.argv)
