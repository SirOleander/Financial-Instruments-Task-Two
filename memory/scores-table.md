---
name: scores-table
description: Sector-percentile scoring layer — src/F_scores.py + scores table (6 sub-scores + financial_score)
metadata:
  type: project
---

Analytical step 2 (financial scoring) is DONE. `src/F_scores.py` turns raw `kpi_values`
into cross-sectional percentile scores in NEW table `scores` (PK (ticker,report_release_date);
cols: fiscal_period_end_date, source, form, sector, frequency, period, peer_group_size,
{profitability,growth,cash_flow,leverage,efficiency,investment}_score + _computable each,
financial_score + financial_computable; idempotent upsert). 1,662 rows, 89 tickers, 0 NaN,
all scores in [0,1]. Additive; financial_facts/daily_prices/target_63d/kpi_values unchanged.

**Method (decided):** peer group = (sector, frequency, period). frequency=annual(10-K/annual)
vs quarterly(10-Q/quarterly). period = calendar YEAR of fiscal_period_end_date (annual) or
calendar QUARTER YYYYQn (quarterly) — only robust cross-fiscal-calendar alignment; US+non-US
co-occur in annual pools. Percentile = mid-rank empirical CDF (below + 0.5*equal)/n, n==1→0.5,
computable values only. INVERSE KPIs sign-flipped before ranking: debt_to_assets,
net_debt_to_assets (only ones in kpi_values). Sub-score = mean of its computable oriented
percentiles (§2.5 per-sector KPI sets); drop-and-renormalize, all-NC→sub-score NC.
financial_score = mean of computable sub-scores. NO strategic/competitive_advantage score
(separate later step). ROIC & free_cash_flow are in kpi_values but NOT in any §2.5 sub-score
set, so not ranked here (kept for the change-features step).

**Bank cash_flow proxy (opted in):** Banks cash_flow_score = mean of operating_cash_flow_margin
+ cash_conversion (the §2.5 "operating_cash_flow if meaningful" proxy). Computable on 191 of 207
bank reports; still NC on 16 (HSBA.L/8306.T/SAN.MC reports lacking OCF inputs).

**Known NC / cautions (surfaced, not fixed):** Banks investment NC on 167 quarterly bank reports
(capital_retention annual-only). growth NC scattered = first-obs + shallow non-US quarterly. Small pools: 74 of 235 groups have <5 peers (215 rows ~13%); 18
singleton groups → every KPI pct 0.5 → financial_score exactly 0.5. Open options user may revisit:
add operating_cash_flow_margin as bank cash_flow proxy; handle singletons. See [[kpi-values-table]],
[[prices-and-target-phase]].
