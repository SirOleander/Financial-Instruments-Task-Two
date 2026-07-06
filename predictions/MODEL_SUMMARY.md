# Forward-63d-Sharpe models — training & evaluation

Leak-safe: time split at **2025-03-31** (train+val <= vs 12-month test >), TimeSeriesSplit CV (5 folds, gap=21), per-fold winsor + impute + scale, target winsorized per fold. Test set touched once. Selection metric = Spearman (ranking task).

## CV rank-correlation (train+val, model selection)

| model | cv_spearman_mean | cv_spearman_std | degenerate_constant |
|---|---|---|---|
| ElasticNet | +0.0133 | +0.0388 | 1 |
| Lasso | +0.0000 | +0.0000 | 1 |
| SVR | -0.0070 | +0.0716 | 0 |
| XGBoost | -0.0231 | +0.0881 | 0 |
| RandomForest | -0.0280 | +0.0907 | 0 |
| Ridge | -0.0341 | +0.1050 | 0 |

**ElasticNet, Lasso collapsed to the NULL (constant) model** — with near-zero linear signal, regularization drives all coefficients to 0 and predicts the mean (CV Spearman 0.0 beats any negative). They carry no ranking information and are EXCLUDED from the ensemble. That collapse is itself an informative result: no linear feature combination beats the mean.

All CV means lie within ~±0.04 of zero with per-fold std ~0.07–0.10, i.e. **indistinguishable from no signal** — consistent with the EDA.

## One-shot TEST metrics (held-out 12 months)

| model | test_spearman_pooled | test_spearman_perperiod_mean | decile_spread_latestperco | perperiod_top10bot10_spread_mean | test_rmse |
|---|---|---|---|---|---|
| Ridge | -0.0475 | -0.0523 | +0.2727 | +0.2002 | +2.1499 |
| Lasso | +0.0000 | +0.0000 | -0.2398 | -0.0555 | +2.1065 |
| ElasticNet | +0.0000 | +0.0000 | -0.2398 | -0.0555 | +2.1065 |
| RandomForest | -0.0410 | -0.0215 | +0.7465 | -0.6675 | +2.1197 |
| XGBoost | -0.0341 | -0.0229 | -0.4089 | -0.9497 | +2.2085 |
| SVR | -0.0039 | +0.0187 | +0.8127 | +0.0381 | +2.3624 |
| ENSEMBLE(mean:SVR+XGBoost+RandomForest) | -0.0292 | -0.0188 | +0.7524 | -0.5106 | +2.1796 |

**Ensemble = mean of best-3 NON-DEGENERATE models by CV Spearman: SVR, XGBoost, RandomForest.** The two decile-spread columns are noisy: the latest-per-company version ranks only ~7 names per tail, and the per-period top-10/bottom-10 spread averages over 4 test quarters — read signs, not magnitudes, and treat both as within-noise here.

## Honest verdict

EDA showed max single-feature |Spearman| ~0.075; the models confirm it. **CV Spearman is indistinguishable from zero for every model, test-set Spearman is ~0 to slightly negative, and the top-vs-bottom realized-Sharpe spreads flip sign across models** — i.e. no reliable, generalizable signal from report fundamentals to forward 63-day Sharpe on this universe/period. This is a valid, expected finding, reported straight and NOT tuned to manufacture a strong-looking number. The ranking below is produced for completeness (the pipeline is correct and leak-safe); it should be treated as low-confidence and the backtest read accordingly.

## Predicted ranking — top 10 (long) / bottom 10 (short)

`out_of_training_dist=1` = held-out international (scored, never trained; treat as lower-confidence).

**Top 10 (long):**
| rank_ensemble | ticker | sector | pred_ensemble | out_of_training_dist |
|---|---|---|---|---|
| 1 | BA | Industrials | +2.4031 | 0 |
| 2 | BAC | Banks | +1.9839 | 0 |
| 3 | GOOG | Communication | +1.8325 | 0 |
| 4 | GOOGL | Communication | +1.8325 | 0 |
| 5 | SAN.MC | Banks | +1.7949 | 1 |
| 6 | MU | Technology | +1.7364 | 0 |
| 7 | 005930.KS | Technology | +1.7319 | 1 |
| 8 | SCHW | Banks | +1.7195 | 0 |
| 9 | 000660.KS | Technology | +1.7133 | 1 |
| 10 | NFLX | Communication | +1.6814 | 0 |

**Bottom 10 (short):**
| rank_ensemble | ticker | sector | pred_ensemble | out_of_training_dist |
|---|---|---|---|---|
| 89 | ASML.AS | Technology | +0.2362 | 1 |
| 90 | CVX | Energy, Materials & Utilities | +0.1865 | 0 |
| 91 | AZN.L | Healthcare | +0.1606 | 1 |
| 92 | TSM | Technology | +0.0952 | 1 |
| 93 | V | Financial Services | +0.0947 | 0 |
| 94 | INTU | Technology | +0.0584 | 0 |
| 95 | NOW | Technology | +0.0519 | 0 |
| 96 | PG | Consumer Staples | -0.0283 | 0 |
| 97 | INTC | Technology | -0.2094 | 0 |
| 98 | SHOP.TO | Technology | -0.5026 | 1 |

Full ranking of all 89 in predictions_all89.csv (final models refit on ALL train_eligible rows; the 89 rows are each company's latest report, forward window still open — these are the ranking signals, not evaluable yet).