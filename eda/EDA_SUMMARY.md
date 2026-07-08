# EDA & feature diagnostics — modelling_data

Read-only pass over `modelling_data`. **All modelling-informing statistics (correlation, VIF, feature-target, target-by-sector) are computed on TRAIN-ELIGIBLE rows only** (train_eligible=1, n=1314 rows / 72 US companies). Distribution plots show all rows, labelled train vs prediction-only. Feature columns are the WINSORIZED (model) columns unless suffixed `[RAW]`.

Universe: 1712 rows / 97 companies (182 international rows held out of training, retained for prediction/ranking).

## 1. Feature-target signal (the key question: is there any?)

Forward-return prediction is intrinsically low-signal; weak correlations are expected and still usable in aggregate. Ranked among WELL-POPULATED features (n>=800) so small sector-only subsamples don't masquerade as signal. Strongest **positive** Spearman vs future_63d_sharpe:

| feature | n | pearson | spearman |
|---|---|---|---|
| net_margin_change | 1314 | +0.0618 | +0.0784 |
| ROIC_change | 1050 | +0.0252 | +0.0515 |
| operating_margin_change | 1134 | +0.0671 | +0.0502 |
| return_on_assets_change | 1314 | +0.0193 | +0.0478 |
| net_income_growth_yoy | 1170 | +0.0352 | +0.0470 |
| gross_margin_change | 989 | +0.0212 | +0.0436 |

Strongest **negative** Spearman:

| feature | n | pearson | spearman |
|---|---|---|---|
| operating_income_growth_yoy_change | 886 | -0.0021 | -0.0580 |
| equity_ratio | 1239 | -0.0504 | -0.0568 |
| return_on_assets | 1314 | -0.0226 | -0.0540 |
| asset_turnover | 1314 | -0.0115 | -0.0529 |
| gross_margin | 989 | -0.0506 | -0.0399 |
| return_on_equity | 1239 | -0.0216 | -0.0377 |

**Max |Spearman| among well-populated features = +0.0784 (net_margin_change, n=1314) — essentially no univariate signal.** This is the expected, informative result: rely on multivariate + ensemble models, not any single feature.


**CAUTION — ignore these as leaders:** the raw top-|Spearman| is dominated by sparse, sector-specific features computed on small non-representative subsamples, NOT deployable signal:

| feature | n | spearman |
|---|---|---|
| net_interest_margin | 144 | -0.1307 |
| net_interest_margin_change | 144 | -0.1043 |
| capital_retention | 32 | -0.0792 |
| inventory_turnover_change | 280 | +0.0552 |

## 2. Redundancy / collinearity

**Exact identities that make a linear model RANK-DEFICIENT** (VIF=inf, R2=1.0 — surface explicitly). Drop one variable from each group:

- `financial_score = mean(six sub-scores)`
- `competitive_advantage_score_w050 = 0.5*financial_score + 0.5*operative_score`
- `free_cash_flow_margin = operating_cash_flow_margin - capex_intensity`
- `net_debt_to_assets = debt_to_assets - cash_to_assets`

So do NOT feed both the six sub-scores AND financial_score AND the w050 blend; and within the KPIs keep only two of {operating_cash_flow_margin, capex_intensity, free_cash_flow_margin} and two of {debt_to_assets, cash_to_assets, net_debt_to_assets}. VIF>10 flags:

| block | feature | R2_on_others | VIF |
|---|---|---|---|
| scores | profitability_score | +1.0000 | +9999.0000 |
| scores | growth_score | +1.0000 | +9999.0000 |
| scores | cash_flow_score | +1.0000 | +9999.0000 |
| scores | leverage_score | +1.0000 | +9999.0000 |
| scores | efficiency_score | +1.0000 | +9999.0000 |
| scores | investment_score | +1.0000 | +9999.0000 |
| scores | financial_score | +1.0000 | +9999.0000 |
| scores | operative_score | +1.0000 | +9999.0000 |
| scores | competitive_advantage_score_w050 | +1.0000 | +9999.0000 |
| core_kpis | free_cash_flow_margin | +1.0000 | +9999.0000 |
| core_kpis | operating_cash_flow_margin | +1.0000 | +9999.0000 |
| core_kpis | capex_intensity | +1.0000 | +9999.0000 |
| core_kpis | cash_to_assets | +1.0000 | +9999.0000 |
| core_kpis | debt_to_assets | +1.0000 | +9999.0000 |
| core_kpis | net_debt_to_assets | +1.0000 | +9999.0000 |
| core_kpis | operating_income_to_assets | +0.9687 | +31.9227 |
| core_kpis | return_on_assets | +0.9673 | +30.5796 |
| core_kpis | operating_margin | +0.9073 | +10.7851 |
| core_kpis | net_margin | +0.9020 | +10.1998 |

Feature pairs with |Pearson|>0.8: 12.

| feat_a | feat_b | pearson |
|---|---|---|
| return_on_assets | operating_income_to_assets | +0.9630 |
| return_on_assets | net_interest_margin | +0.9087 |
| operative_score | competitive_advantage_score_w050 | +0.8995 |
| operating_margin | net_margin | +0.8954 |
| debt_to_assets | net_debt_to_assets | +0.8867 |
| return_on_equity | net_interest_margin | +0.8859 |
| asset_turnover | net_interest_margin | +0.8811 |
| leverage_score | net_debt_to_assets | -0.8654 |
| capex_intensity | reinvestment_rate | +0.8542 |
| operating_cash_flow_margin | free_cash_flow_margin | +0.8184 |
| leverage_score | debt_to_assets | -0.8176 |
| investment_score | capital_retention | +0.8100 |

## 3. Distributions / skew

Winsorization tamed the ratio-tail KPIs (see fig_dist_winsor_rawvswins.png). Features still |skew|>2 after winsorization:

| feature | skew | kurtosis |
|---|---|---|
| return_on_equity | +15.8268 | +302.2219 |
| inventory_turnover | +5.2055 | +32.8442 |
| net_income_growth_yoy | +5.0700 | +31.3024 |
| net_income_growth_yoy [RAW] | +5.0700 | +31.3024 |
| asset_turnover | +4.6290 | +32.7292 |
| operating_income_growth_yoy [RAW] | +4.1123 | +21.2960 |
| operating_income_growth_yoy | +4.1123 | +21.2960 |
| operating_cash_flow_margin | -3.3806 | +45.2181 |

## 4. Missingness

Highest-missing features (all rows):

| feature | pct_missing_all | pct_missing_US | pct_missing_intl |
|---|---|---|---|
| capital_retention_change | +98.3645 | +98.4314 | +97.8022 |
| capital_retention | +97.5467 | +97.9085 | +94.5055 |
| net_interest_margin_change | +89.3692 | +90.0654 | +83.5165 |
| net_interest_margin | +87.7921 | +89.0196 | +77.4725 |
| inventory_turnover_change | +81.6005 | +80.6536 | +89.5604 |
| inventory_turnover | +79.0888 | +78.5621 | +83.5165 |
| reinvestment_rate_change | +50.1752 | +48.4314 | +64.8352 |
| r_and_d_intensity_change | +49.7079 | +47.9085 | +64.8352 |
| operating_income_growth_yoy_change | +43.9252 | +38.0392 | +93.4066 |
| reinvestment_rate | +43.6916 | +42.7451 | +51.6484 |

Drivers: sparse sector-specific KPIs (net_interest_margin, capital_retention banks-only; inventory_turnover a few sectors; r_and_d only tech/health), negative-equity ROE/equity_ratio/ROIC (PM/MCD/BKNG/ABBV), Energy gross_margin (not emitted), operative_score (integrated/no-20-F intl), and all `*_change` features on first_obs rows. Missing is honest NULL — models must handle it (tree split-on-missing, or impute-in-pipeline; never mean-fill silently).

## 5. Target

future_63d_sharpe (train, winsorized): median=+0.743, mean=+0.831, std=1.979. See target_by_sector.csv / fig_target_by_sector.png for sector dispersion — some sectors sit systematically above/below zero in-sample (a look-ahead caution: do NOT hardcode sector means into features).

Lag-1 autocorrelation of a company's consecutive forward Sharpes:

| frequency | n_pairs | lag1_pearson |
|---|---|---|
| quarterly | 954 | -0.0354 |
| annual | 216 | -0.0676 |

Non-trivial serial correlation => consecutive same-company rows are NOT independent. Use a **time-based split** (already planned) and consider grouping by company to avoid train/test leakage across adjacent windows.

## 6. Recommendations (for the modelling step — you decide)

1. **Scores: pick ONE level of aggregation.** For linear/SVM models use the **six sub-scores** (richer, less collinear) and DROP `financial_score` + `competitive_advantage_score_w050` (both collinear by construction). Keep `operative_score` separate (as designed). Tree/boosting models tolerate the redundancy but gain nothing from the duplicates.

2. **Drop within high-corr KPI pairs.** e.g. `return_on_assets` vs `operating_income_to_assets` (r=+0.96) — keep one. See high_corr_pairs.csv (candidates like return_on_assets vs operating_income_to_assets, debt_to_assets vs net_debt_to_assets, reinvestment_rate vs its components).

3. **Lead features (well-populated only, n>=800):** net_margin_change, ROIC_change, operating_margin_change (positive); operating_income_growth_yoy_change, equity_ratio, return_on_assets (negative). All |Spearman|<0.08 — weak; value comes from combining them, and change features carry as much of the (thin) signal as levels. Do NOT prioritise the sparse bank-only features despite their larger raw correlations.

4. **Split by time AND respect company grouping** (serial-correlated targets); **refit winsor caps on the training slice only** at split time (caps here were fit on the full train-eligible set for EDA); and keep missingness as NULL for a model that handles it natively.
