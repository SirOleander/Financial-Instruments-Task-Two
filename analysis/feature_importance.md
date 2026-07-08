# Feature importance — what the models actually use

Slide-24 requirement: the models are **not black boxes**. Below is exactly what each one leans on. All fitted on train+val only.

## Rank-consensus (mean rank across Ridge, RandomForest, XGBoost, SVR-permutation)

| rank | feature | mean_rank |
|---|---|---|
| 1 | `growth_score_change` | 13.3 |
| 2 | `profitability_score` | 14.2 |
| 3 | `operating_cash_flow_growth_yoy_change` | 14.8 |
| 4 | `operating_margin_change` | 14.8 |
| 5 | `equity_ratio_change` | 17.8 |
| 6 | `asset_turnover_change` | 18.0 |
| 7 | `debt_to_assets` | 18.7 |
| 8 | `net_income_growth_yoy_change` | 19.2 |
| 9 | `operating_cash_flow_margin` | 19.5 |
| 10 | `capex_intensity` | 20.2 |
| 11 | `leverage_score_change` | 20.5 |
| 12 | `operating_income_growth_yoy_change` | 20.8 |

## Per-model views

- `fig_importance_Ridge.png`, `fig_importance_RandomForest.png`, `fig_importance_XGBoost.png`, `fig_importance_consensus.png`
- Non-zero/non-trivial features per model: {'ElasticNet': 0, 'Lasso': 0, 'XGBoost': 48, 'RandomForest': 48, 'Ridge': 48, 'SVR_perm': 48}
- **Lasso and ElasticNet drive EVERY coefficient to exactly zero** — the regularisation path selects *no* feature over the intercept. That is itself the cleanest statement of the finding: no linear combination of these 48 features beats predicting the mean.

## Interpretation

- The models concentrate what little weight they have on **growth_score_change, profitability_score, operating_cash_flow_growth_yoy_change, operating_margin_change** — broadly the *change* features (margin and profitability deltas) rather than levels, consistent with the EDA where `net_margin_change` was the strongest single feature (|Spearman| ~0.075).
- **But the magnitudes are trivial.** No feature is a strong driver: the ranking below is a ranking of near-noise. Ridge's standardized coefficients are small and the tree importances are spread thinly across all 48 features (no dominant split variable). Reading these as economic 'drivers' would be over-interpretation.
- The honest statement: *we can show exactly what the models use, and what they use carries almost no predictive power.* Interpretability here confirms rather than rescues the null.