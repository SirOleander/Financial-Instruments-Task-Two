# Financial Instruments — Project Specification (report-signal equity strategy)

Authoritative end-to-end plan. CLAUDE.md holds current implementation state and the
gaps between this plan and what the pipeline produces; read both together.

## Objective

For each company, extract signals at every report release, use them to predict the
company's forward 63-trading-day risk-adjusted return (Sharpe), rank the ~98-company
universe, form a long portfolio (top 10) and a short portfolio (bottom 10), and
backtest under strict forward-bias controls.

## 1. Prepare the data
- ~98 tickers, each mapped to one of nine sector groups (see 2.5).
- Financial reports (annual + quarterly) and their **release dates**.
- Daily prices covering each report period PLUS 63 trading days after the last report.
- Sector-specific extra data where sub-scores need it (see 2.3 and OPEN DECISIONS).

## 2. Extract report signals
Each company, at each report date, gets three scores:
```
financial_score (quantitative) ─┐
                                ├─> competitive_advantage_score
strategic_score (qualitative) ──┘
```

### 2.1 Scoring methodology
- Financial signals → continuous percentile in [0,1], ranked cross-sectionally
  **within sector group, within the same report period**.
- Qualitative signals → 1–5 rubric, rescaled to [0,1] as `(rating − 1)/4`.
- **Orient every metric so higher = better before ranking.** A KPI marked "inverse"
  is sign-flipped so lower raw values rank higher (lower leverage, lower
  efficiency_ratio = better). Invert "strength/stability" (std-dev) metrics too.
- **Missing data ("if available"):** if a KPI can't be retrieved, DROP it and average
  over the remaining KPIs in that sub-score (renormalize). Do NOT treat it as 0.
- Aggregate: KPI percentiles → sub-score (mean); six sub-scores → financial_score
  (mean or weighted); qualitative ratings → strategic_score (mean); then
  `competitive_advantage_score = w*financial_score + (1−w)*strategic_score` (w TBD).

### 2.2 The six financial sub-scores
Same six for every sector; KPIs feeding each are sector-specific (see 2.5). Each
sub-score is the mean of its oriented, percentile-ranked KPIs:
`profitability_score, growth_score, cash_flow_score, leverage_score,
efficiency_score, investment_score`.

### 2.3 KPI formula glossary

Core (industrial / tech-style sectors):
```
gross_margin                   = gross_profit / revenue
operating_margin               = operating_income / revenue
net_margin                     = net_income / revenue
return_on_assets               = net_income / total_assets
return_on_equity               = net_income / average_equity
revenue_growth_yoy             = (rev_t − rev_{t-1}) / rev_{t-1}
operating_income_growth_yoy    = (op_t − op_{t-1}) / |op_{t-1}|
net_income_growth_yoy          = (ni_t − ni_{t-1}) / |ni_{t-1}|
operating_cash_flow_growth_yoy = (ocf_t − ocf_{t-1}) / |ocf_{t-1}|
operating_cash_flow_margin     = operating_cash_flow / revenue
free_cash_flow                 = operating_cash_flow − capital_expenditure
free_cash_flow_margin          = free_cash_flow / revenue
cash_conversion                = operating_cash_flow / net_income
debt_to_assets                 = (short_term_debt + long_term_debt) / total_assets
net_debt_to_assets             = (short_term_debt + long_term_debt − cash) / total_assets
cash_to_assets                 = cash_and_cash_equivalents / total_assets
equity_ratio                   = total_equity / total_assets
asset_turnover                 = revenue / total_assets (average preferred)
operating_income_to_assets     = operating_income / total_assets
inventory_turnover             = cost_of_revenue / average_inventory
r_and_d_intensity              = research_and_development / revenue
capex_intensity                = capital_expenditure / revenue
reinvestment_rate              = (research_and_development + capital_expenditure) / revenue
ROIC                           = (operating_income * (1 − tax_rate)) /
                                 (short_term_debt + long_term_debt + total_equity − cash)
                                 tax_rate = income_tax / income_before_tax
```

Sector-specific / new (extra data needed in brackets):
```
net_interest_margin                 = net_interest_income / average_earning_assets [bank interest data]
efficiency_ratio (inverse)          = noninterest_expense / revenue [noninterest expense]
noninterest_expense_to_revenue (inv)= noninterest_expense / revenue [noninterest expense]
cost_to_income_ratio (inverse)      = operating_expenses / operating_income [cost breakdown]
loan_growth_yoy                     = YoY change in total loans [loan balances]
deposit_growth_yoy                  = YoY change in total deposits [deposit balances]
assets_to_equity (inverse)          = total_assets / total_equity
CET1_ratio / tier1_capital_ratio    = regulatory capital ratios [regulatory capital]
provision_coverage                  = allowance for credit losses / non-performing loans [provisions, NPLs]
net_income_stability                = inverse std-dev of net income over 3-5y [history, have it]
capital_retention                   = retained-earnings build / net income (~1 − payout) [dividends / retained earnings]
acquisition_intensity               = acquisition spend / revenue [acquisitions (investing CF)]
content_or_network_investment_intensity = content/network investment / revenue [content/network capex]
free_cash_flow_after_capex_margin   = NEEDS DEFINITION (see OPEN DECISIONS #1)
balance_sheet_growth_quality        = composite: loan_growth, deposit_growth, capital_retention [loans, deposits]
```

### 2.4 Qualitative signals (1–5 rubric)
Quant operatives: pricing power, customer engagement, customer loyalty, market share
leadership, backlog/order growth, revenue stability, demand stability, capital
discipline, R&D strength.
Evidence operatives: brand strength, regulatory trust, technological leadership,
platform strength, asset quality, risk management quality, contract quality, patent
protection.

### 2.5 Per-sector signal sets
Each group lists its six sub-scores (the KPIs feeding them) and its operatives.

**1 — TECHNOLOGY**
- profitability: gross_margin, operating_margin, net_margin, return_on_assets
- growth: revenue_growth_yoy, operating_income_growth_yoy, net_income_growth_yoy, operating_cash_flow_growth_yoy
- cash_flow: operating_cash_flow_margin, free_cash_flow_margin, cash_conversion
- leverage: inverse debt_to_assets, inverse net_debt_to_assets, cash_to_assets, equity_ratio
- efficiency: asset_turnover, operating_income_to_assets, return_on_assets
- investment: r_and_d_intensity, capex_intensity, reinvestment_rate
- operative: ecosystem/platform lock-in, innovation/R&D strength, market share leadership, product differentiation, technological leadership

**2 — COMMUNICATION**
- profitability: gross_margin, operating_margin, net_margin, return_on_assets
- growth: revenue_growth_yoy, operating_income_growth_yoy, net_income_growth_yoy, operating_cash_flow_growth_yoy
- cash_flow: operating_cash_flow_margin, free_cash_flow_margin, cash_conversion
- leverage: inverse debt_to_assets, inverse net_debt_to_assets, cash_to_assets, equity_ratio
- efficiency: asset_turnover, operating_income_to_assets, return_on_assets
- investment: capex_intensity, reinvestment_rate, content_or_network_investment_intensity (if available)
- operative: advertising/subscription power, content or data advantage, customer engagement, network effects, platform strength

**3 — CONSUMER DISCRETIONARY**
- profitability: gross_margin, operating_margin, net_margin, return_on_assets
- growth: revenue_growth_yoy, operating_income_growth_yoy, net_income_growth_yoy, operating_cash_flow_growth_yoy
- cash_flow: operating_cash_flow_margin, free_cash_flow_margin, cash_conversion
- leverage: inverse debt_to_assets, inverse net_debt_to_assets, cash_to_assets, equity_ratio
- efficiency: asset_turnover, inventory_turnover, operating_income_to_assets
- investment: capex_intensity, reinvestment_rate
- operative: brand strength, customer loyalty, digital or logistics advantage, pricing power, scale/distribution advantage

**4 — CONSUMER STAPLES**
- profitability: gross_margin, operating_margin, net_margin, return_on_assets
- growth: revenue_growth_yoy, operating_income_growth_yoy, net_income_growth_yoy, operating_cash_flow_growth_yoy
- cash_flow: operating_cash_flow_margin, free_cash_flow_margin, cash_conversion
- leverage: inverse debt_to_assets, inverse net_debt_to_assets, cash_to_assets, equity_ratio
- efficiency: asset_turnover, inventory_turnover, operating_income_to_assets
- investment: capex_intensity, reinvestment_rate
- operative: brand strength, demand stability, distribution strength, pricing power, retailer/supplier bargaining power

**5 — HEALTHCARE**
- profitability: gross_margin, operating_margin, net_margin, return_on_assets
- growth: revenue_growth_yoy, operating_income_growth_yoy, net_income_growth_yoy, operating_cash_flow_growth_yoy
- cash_flow: operating_cash_flow_margin, free_cash_flow_margin, cash_conversion
- leverage: inverse debt_to_assets, inverse net_debt_to_assets, cash_to_assets, equity_ratio
- efficiency: asset_turnover, operating_income_to_assets, return_on_assets
- investment: r_and_d_intensity, capex_intensity, reinvestment_rate
- operative: product diversification, innovation/IP strength, market leadership, patent/regulatory protection, pipeline strength

**6 — BANKS** (revenue, debt, cash, OCF don't behave like industrials)
- profitability: return_on_assets, return_on_equity, net_interest_margin (if available), inverse efficiency_ratio
- growth: revenue_growth_yoy, net_income_growth_yoy, loan_growth_yoy, deposit_growth_yoy
- cash_flow: earnings-quality proxies — net_income_stability, provision_coverage, operating_cash_flow (only if meaningful)
- leverage: equity_to_assets, inverse assets_to_equity, CET1_ratio (if available), tier1_capital_ratio (if available)
- efficiency: inverse efficiency_ratio, revenue_to_assets, inverse noninterest_expense_to_revenue
- investment: balance_sheet_growth_quality (loan_growth, deposit_growth, capital_retention)
- operative: customer franchise strength, deposit/funding advantage, regulatory trust, risk management quality, scale & market position

**7 — FINANCIAL SERVICES** (V/MA/BLK/SPGI/SCHW/BRK — mixed, mostly non-bank financial KPIs)
- profitability: operating_margin, net_margin, return_on_assets, return_on_equity
- growth: revenue_growth_yoy, operating_income_growth_yoy, net_income_growth_yoy
- cash_flow: operating_cash_flow_margin, free_cash_flow_margin, cash_conversion
- leverage: inverse debt_to_assets, inverse net_debt_to_assets, equity_ratio
- efficiency: asset_turnover, operating_income_to_assets, inverse cost_to_income_ratio (if available)
- investment: capex_intensity, reinvestment_rate, acquisition_intensity (if available)
- operative: brand & trust, client stickiness, network effects, risk/underwriting/platform quality, scale advantage

**8 — INDUSTRIALS**
- profitability: gross_margin, operating_margin, net_margin, return_on_assets
- growth: revenue_growth_yoy, operating_income_growth_yoy, net_income_growth_yoy, operating_cash_flow_growth_yoy
- cash_flow: operating_cash_flow_margin, free_cash_flow_margin, cash_conversion
- leverage: inverse debt_to_assets, inverse net_debt_to_assets, cash_to_assets, equity_ratio
- efficiency: asset_turnover, inventory_turnover, operating_income_to_assets
- investment: capex_intensity, reinvestment_rate
- operative: contract quality, customer/contract stickiness, operational efficiency, pricing power, scale advantage

**9 — ENERGY, MATERIALS & UTILITIES** (capital-intensive; capex & leverage matter more)
- profitability: operating_margin, net_margin, return_on_assets, return_on_equity
- growth: revenue_growth_yoy, operating_income_growth_yoy, net_income_growth_yoy, operating_cash_flow_growth_yoy
- cash_flow: operating_cash_flow_margin, free_cash_flow_margin, cash_conversion
- leverage: inverse debt_to_assets, inverse net_debt_to_assets, cash_to_assets, equity_ratio
- efficiency: asset_turnover, operating_income_to_assets, return_on_assets
- investment: capex_intensity, reinvestment_rate, free_cash_flow_after_capex_margin
- operative: asset quality, capital discipline, cost position, regulatory position, reserve/resource quality

## 3. Create signal change features
For every signal: `x_change = x_current − x_previous` (vs previous report).
- Scores: competitive_advantage_score_change, financial_score_change, strategic_score_change
- Sub-scores (all six): profitability_score_change … investment_score_change
- Financial metrics: ROIC_change, revenue_growth_change, operating_margin_change, free_cash_flow_margin_change, gross_margin_change, debt_strength_change
- Sector metrics: ARPU_growth_change, R&D_efficiency_change, credit_quality_change, capital_strength_change, backlog_growth_change, capex_discipline_change
- Operatives: pricing_power_change, innovation_strength_change, customer_stickiness_change, market_position_change, capital_discipline_change

## 4. Calculate future performance (the target)
- Confirm available annual + quarterly reports; choose a common report period; keep
  companies with enough observations.
- Download prices covering that period + 63 trading days after the last report. Older
  prices are for charts/context only — never as model targets.
- After each report **release** date, compute over the next 63 trading days: 63-day
  return, 63-day volatility, 63-day Sharpe. **Sharpe is the target.**

## 5. Build the modelling dataset
One row per (ticker, report_date): ticker, report_date; signal scores (§2) and signal
changes (§3); future_63d_return, future_63d_volatility, future_63d_sharpe.

## 6. Split the data by time
Time-based, never random: train = early reports, validation = middle, test = latest.

## 7. Train models
Linear/Logistic Regression, Random Forest, XGBoost, SVM. Learn: report signals →
forward 63-day Sharpe.

## 8. Evaluate the models
Feature importance + bias/variance discussion, plus metrics matched to the framing
(see OPEN DECISIONS #4): regression (R², MAE/RMSE, rank correlation) if predicting
Sharpe directly; classification (accuracy, AUC, confusion matrix) if predicting an
up/down or top/bottom-quantile label.

## 9. Build the ensemble model
`ensemble_score = mean(model predictions)`.

## 10. Rank the stocks
Rank by ensemble score. Top 10 = long, bottom 10 = short.

## 11. Backtest the strategy
Equally weighted long (top 10), equally weighted short (bottom 10), optional
long-short. State assumptions: 63-trading-day holding period, rebalancing rule,
transaction costs, equal weighting, and that signals apply ONLY after the report
release date.

## 12. Report final results
Stock ranking, top-10 buys, bottom-10 shorts, model evaluation, feature importance,
backtest performance, forward-bias controls.

## Simplified flow
Load data → extract report signals → signal changes → 63-day future Sharpe →
modelling dataset → split by time → train → evaluate → ensemble → rank →
backtest top10/bottom10 → report.

## OPEN DECISIONS (need the user's call — ASK, do not assume)
1. **Define `free_cash_flow_after_capex_margin` (Energy).** FCF is already OCF − capex,
   so the name is ambiguous: FCF after ALL investing (incl. acquisitions), after
   maintenance capex only, or just free_cash_flow_margin?
2. **"if available" fallback.** Per 2.1: drop a missing KPI and renormalize the
   sub-score over what's left. Confirm (vs a fixed proxy), especially for bank capital
   ratios and content_or_network_investment_intensity.
3. **Bank cash_flow_score and investment_score are proxies**, not standard KPIs. They
   use earnings-quality / balance-sheet-growth substitutes and need their own
   definitions before they're computable.
4. **Regression vs classification.** Sharpe is continuous (→ regression), but §8 also
   lists Accuracy/AUC/Confusion Matrix (→ classification, e.g. top/bottom Sharpe
   quantile). Pick one; metrics follow.
5. **Data still to retrieve** beyond current positions: noninterest expense & interest
   income, loans & deposits, regulatory capital (CET1/Tier1), provisions/NPLs (banks);
   inventory (Discretionary, Staples, Industrials); acquisitions CF (Financial
   Services); content/network investment (Communication); dividends or retained
   earnings (capital_retention). NOTE: adding these means config edits + a full
   13-group rebuild (see CLAUDE.md rebuild cautions) — it loops back into extraction.
6. **Confirmed definitions:** cash_conversion = operating_cash_flow / net_income;
   reinvestment_rate = (R&D + capex) / revenue.
7. **Division safety.** Missing values are stored as 0, so guard every denominator
   (revenue, total_assets, net_income, equity): treat `selection_status=='missing'`
   (NOT a naive value==0) as "not computable" rather than dividing.
