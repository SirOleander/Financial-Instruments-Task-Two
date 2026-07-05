# EDA & feature diagnostics — modelling_data

Read-only pass over `modelling_data`. **All modelling-informing statistics (correlation, VIF, feature-target, target-by-sector) are computed on TRAIN-ELIGIBLE rows only** (train_eligible=1, n=1308 rows / 71 US companies). Distribution plots show all rows, labelled train vs prediction-only. Feature columns are the WINSORIZED (model) columns unless suffixed `[RAW]`.

Universe: 1662 rows / 89 companies (141 international rows held out of training, retained for prediction/ranking).

## 1. Feature-target signal (the key question: is there any?)

Forward-return prediction is intrinsically low-signal; weak correlations are expected and still usable in aggregate. Ranked among WELL-POPULATED features (n>=800) so small sector-only subsamples don't masquerade as signal. Strongest **positive** Spearman vs future_63d_sharpe:

| feature | n | pearson | spearman |
|---|---|---|---|
| net_margin_change | 1308 | +0.0589 | +0.0749 |
| operating_margin_change | 1128 | +0.0648 | +0.0468 |
| ROIC_change | 1044 | +0.0111 | +0.0463 |
| return_on_assets_change | 1308 | +0.0164 | +0.0441 |
| efficiency_score | 1308 | +0.0464 | +0.0427 |
| net_income_growth_yoy | 1166 | +0.0341 | +0.0419 |

Strongest **negative** Spearman:

| feature | n | pearson | spearman |
|---|---|---|---|
| operating_income_growth_yoy_change | 884 | -0.0028 | -0.0598 |
| asset_turnover | 1308 | -0.0116 | -0.0549 |
| return_on_assets | 1308 | -0.0218 | -0.0543 |
| equity_ratio | 1233 | -0.0466 | -0.0538 |
| return_on_equity | 1233 | -0.0215 | -0.0392 |
| operative_score | 1281 | -0.0349 | -0.0359 |

**Max |Spearman| among well-populated features = +0.0749 (net_margin_change, n=1308) — essentially no univariate signal.** This is the expected, informative result: rely on multivariate + ensemble models, not any single feature.


**CAUTION — ignore these as leaders:** the raw top-|Spearman| is dominated by sparse, sector-specific features computed on small non-representative subsamples, NOT deployable signal:

| feature | n | spearman |
|---|---|---|
| net_interest_margin | 144 | -0.1307 |
| net_interest_margin_change | 144 | -0.1043 |
| capital_retention | 32 | -0.0792 |
| inventory_turnover_change | 274 | +0.0678 |

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
| core_kpis | operating_income_to_assets | +0.9697 | +32.9772 |
| core_kpis | return_on_assets | +0.9674 | +30.6856 |
| core_kpis | operating_margin | +0.9068 | +10.7302 |
| core_kpis | net_margin | +0.9019 | +10.1978 |

Feature pairs with |Pearson|>0.8: 12.

| feat_a | feat_b | pearson |
|---|---|---|
| return_on_assets | operating_income_to_assets | +0.9634 |
| return_on_assets | net_interest_margin | +0.9087 |
| operative_score | competitive_advantage_score_w050 | +0.9010 |
| operating_margin | net_margin | +0.8956 |
| return_on_equity | net_interest_margin | +0.8859 |
| debt_to_assets | net_debt_to_assets | +0.8854 |
| asset_turnover | net_interest_margin | +0.8811 |
| leverage_score | net_debt_to_assets | -0.8634 |
| capex_intensity | reinvestment_rate | +0.8545 |
| investment_score | capital_retention | +0.8361 |
| operating_cash_flow_margin | free_cash_flow_margin | +0.8182 |
| leverage_score | debt_to_assets | -0.8177 |

## 3. Distributions / skew

Winsorization tamed the ratio-tail KPIs (see fig_dist_winsor_rawvswins.png). Features still |skew|>2 after winsorization:

| feature | skew | kurtosis |
|---|---|---|
| return_on_equity | +15.7912 | +300.8239 |
| inventory_turnover | +5.1537 | +32.1607 |
| net_income_growth_yoy | +4.8853 | +29.2347 |
| net_income_growth_yoy [RAW] | +4.8853 | +29.2347 |
| asset_turnover | +4.6241 | +32.6336 |
| operating_income_growth_yoy [RAW] | +4.1498 | +21.6193 |
| operating_income_growth_yoy | +4.1498 | +21.6193 |
| operating_cash_flow_margin | -3.3773 | +45.0383 |

## 4. Missingness

Highest-missing features (all rows):

| feature | pct_missing_all | pct_missing_US | pct_missing_intl |
|---|---|---|---|
| capital_retention_change | +98.3755 | +98.4221 | +97.8723 |
| capital_retention | +97.5933 | +97.8961 | +94.3262 |
| net_interest_margin_change | +89.1697 | +90.0066 | +80.1418 |
| net_interest_margin | +87.6053 | +88.9546 | +73.0496 |
| inventory_turnover_change | +81.6486 | +80.9993 | +88.6525 |
| inventory_turnover | +79.4826 | +79.0270 | +84.3972 |
| reinvestment_rate_change | +49.1576 | +48.5865 | +55.3191 |
| r_and_d_intensity_change | +48.6763 | +48.0605 | +55.3191 |
| reinvestment_rate | +42.6594 | +42.9980 | +39.0071 |
| operating_income_growth_yoy_change | +42.5391 | +37.8698 | +92.9078 |

Drivers: sparse sector-specific KPIs (net_interest_margin, capital_retention banks-only; inventory_turnover a few sectors; r_and_d only tech/health), negative-equity ROE/equity_ratio/ROIC (PM/MCD/BKNG/ABBV), Energy gross_margin (not emitted), operative_score (integrated/no-20-F intl), and all `*_change` features on first_obs rows. Missing is honest NULL — models must handle it (tree split-on-missing, or impute-in-pipeline; never mean-fill silently).

## 5. Target

future_63d_sharpe (train, winsorized): median=+0.739, mean=+0.823, std=1.974. See target_by_sector.csv / fig_target_by_sector.png for sector dispersion — some sectors sit systematically above/below zero in-sample (a look-ahead caution: do NOT hardcode sector means into features).

Lag-1 autocorrelation of a company's consecutive forward Sharpes:

| frequency | n_pairs | lag1_pearson |
|---|---|---|
| quarterly | 950 | -0.0344 |
| annual | 216 | -0.0676 |

Non-trivial serial correlation => consecutive same-company rows are NOT independent. Use a **time-based split** (already planned) and consider grouping by company to avoid train/test leakage across adjacent windows.

## 6. Recommendations (for the modelling step — you decide)

1. **Scores: pick ONE level of aggregation.** For linear/SVM models use the **six sub-scores** (richer, less collinear) and DROP `financial_score` + `competitive_advantage_score_w050` (both collinear by construction). Keep `operative_score` separate (as designed). Tree/boosting models tolerate the redundancy but gain nothing from the duplicates.

2. **Drop within high-corr KPI pairs.** e.g. `return_on_assets` vs `operating_income_to_assets` (r=+0.96) — keep one. See high_corr_pairs.csv (candidates like return_on_assets vs operating_income_to_assets, debt_to_assets vs net_debt_to_assets, reinvestment_rate vs its components).

3. **Lead features (well-populated only, n>=800):** net_margin_change, operating_margin_change, ROIC_change (positive); operating_income_growth_yoy_change, asset_turnover, return_on_assets (negative). All |Spearman|<0.08 — weak; value comes from combining them, and change features carry as much of the (thin) signal as levels. Do NOT prioritise the sparse bank-only features despite their larger raw correlations.

4. **Split by time AND respect company grouping** (serial-correlated targets); **refit winsor caps on the training slice only** at split time (caps here were fit on the full train-eligible set for EDA); and keep missingness as NULL for a model that handles it natively.
