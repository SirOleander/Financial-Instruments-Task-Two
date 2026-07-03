---
name: kpi-values-table
description: Raw KPI layer — src/E_kpis.py + kpi_values table, per-report §2.3 ratios, computability rules
metadata:
  type: project
---

Analytical step 1 (raw KPIs) is DONE. `src/E_kpis.py` computes PROJECT_SPEC §2.3 KPIs
per report from `financial_facts` into NEW long-format table `kpi_values`
(ticker, report_release_date, fiscal_period_end_date, source, form, sector,
company_group, kpi_name, value, computable; PK (ticker,report_release_date,kpi_name);
idempotent INSERT OR REPLACE). 39,796 rows, 89 tickers, 26 KPIs. RAW only — NO percentile
ranks / sub-scores (that is the next step). Purely additive; financial_facts (25,686),
daily_prices (144,632), target_63d (1,662 = 1,573 real + 89 NULL) all unchanged.

**Computability rules (all decided, don't relitigate):** missing IFF selection_status=='missing'
(never value==0); not-computable → computable=0, value NULL (never NaN/fabricated-0).
- Debt sum = short_term_debt + long_term_debt, each missing→0; if BOTH absent use total_debt
  (yfinance names carry total_debt, not short/long). commercial_paper + long_term_debt_current
  are already rolled INTO short_term_debt (status calculated_from_components) — do NOT add again.
- **Banks get NO debt ratio**: debt_to_assets / net_debt_to_assets rows are OMITTED for
  sector=='Banks' (leverage uses equity_ratio); all 13 banks lack every debt input. Non-bank
  sectors keep missing→0 so genuine zero-debt names (ISRG) read ~0.
- Negative equity (total_equity<=0) → return_on_equity, equity_ratio, ROIC NOT computable.
- GE has no operating_income → operating_margin / operating_income_to_assets / ROIC NC (auto).
- Energy sector → gross_margin row OMITTED (no comparable cost/gross).
- Growth *_yoy use TRUE same-period-year-ago (matched by same grain + fiscal_period_end_date
  ~1yr prior; quarterly window 350-381d, annual 330-400d); no prior → NC.

**Stated choices (user-approved):** averages (ROE, asset_turnover, inventory_turnover, NIM)
use single period-end, not 2-pt average. NIM (banks) = net_interest_income / total_assets
(period-end proxy for average_earning_assets). capital_retention (banks) =
(RE − prior-year RE)/net_income, ANNUAL-grain reports only (quarterly→NC). Form collision
(23 yfinance FY+Q4 same-day releases) → prefer the QUARTERLY report. Related: [[prices-and-target-phase]].
