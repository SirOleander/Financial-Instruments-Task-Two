# Forward-63d-Sharpe models — training & evaluation

Leak-safe: time split at **2025-03-31** (train+val <= vs 12-month test >), TimeSeriesSplit CV (5 folds, gap=21), per-fold winsor + impute + scale, target winsorized per fold. Test set touched once. Selection metric = Spearman (ranking task).

## CV rank-correlation (train+val, model selection)

| model | cv_spearman_mean | cv_spearman_std | degenerate_constant |
|---|---|---|---|
| ElasticNet | +0.0112 | +0.0251 | 1 |
| SVR | +0.0013 | +0.0762 | 0 |
| Lasso | +0.0000 | +0.0000 | 1 |
| RandomForest | -0.0218 | +0.0969 | 0 |
| XGBoost | -0.0267 | +0.1009 | 0 |
| Ridge | -0.0380 | +0.1024 | 0 |

**ElasticNet, Lasso collapsed to the NULL (constant) model** — with near-zero linear signal, regularization drives all coefficients to 0 and predicts the mean (CV Spearman 0.0 beats any negative). They carry no ranking information and are EXCLUDED from the ensemble. That collapse is itself an informative result: no linear feature combination beats the mean.

All CV means lie within ~±0.04 of zero with per-fold std ~0.07–0.10, i.e. **indistinguishable from no signal** — consistent with the EDA.

## One-shot TEST metrics (held-out 12 months)

| model | test_spearman_pooled | test_spearman_perperiod_mean | decile_spread_latestperco | perperiod_top10bot10_spread_mean | test_rmse |
|---|---|---|---|---|---|
| Ridge | -0.0458 | -0.0588 | +0.2515 | -0.0820 | +2.1366 |
| Lasso | +0.0000 | +0.0000 | -0.3489 | -0.2047 | +2.0901 |
| ElasticNet | +0.0000 | +0.0000 | -0.3489 | -0.2047 | +2.0901 |
| RandomForest | -0.0357 | +0.0044 | -0.6845 | -0.3526 | +2.1125 |
| XGBoost | -0.0775 | -0.0220 | +0.5832 | -0.6138 | +2.1800 |
| SVR | -0.0031 | -0.0105 | +1.6908 | +0.4210 | +2.3574 |
| ENSEMBLE(mean:SVR+RandomForest+XGBoost) | -0.0394 | -0.0064 | +0.9942 | -0.6328 | +2.1681 |

**Ensemble = mean of best-3 NON-DEGENERATE models by CV Spearman: SVR, RandomForest, XGBoost.** The two decile-spread columns are noisy: the latest-per-company version ranks only ~7 names per tail, and the per-period top-10/bottom-10 spread averages over 4 test quarters — read signs, not magnitudes, and treat both as within-noise here.

## Honest verdict

EDA showed max single-feature |Spearman| ~0.075; the models confirm it. **CV Spearman is indistinguishable from zero for every model, test-set Spearman is ~0 to slightly negative, and the top-vs-bottom realized-Sharpe spreads flip sign across models** — i.e. no reliable, generalizable signal from report fundamentals to forward 63-day Sharpe on this universe/period. This is a valid, expected finding, reported straight and NOT tuned to manufacture a strong-looking number. The ranking below is produced for completeness (the pipeline is correct and leak-safe); it should be treated as low-confidence and the backtest read accordingly.

## Predicted ranking — top 10 (long) / bottom 10 (short)

`out_of_training_dist=1` = held-out international (scored, never trained; treat as lower-confidence).

**Top 10 (long):**
| rank_ensemble | ticker | sector | pred_ensemble | out_of_training_dist |
|---|---|---|---|---|
| 1 | BA | Industrials | +2.1426 | 0 |
| 2 | BAC | Banks | +1.8888 | 0 |
| 3 | MU | Technology | +1.7406 | 0 |
| 4 | SCHW | Banks | +1.7023 | 0 |
| 5 | SAN.MC | Banks | +1.6606 | 1 |
| 6 | IBM | Technology | +1.6384 | 0 |
| 7 | KO | Consumer Staples | +1.5729 | 0 |
| 8 | C | Banks | +1.5651 | 0 |
| 9 | LLY | Healthcare | +1.5606 | 0 |
| 10 | T | Communication | +1.5423 | 0 |

**Bottom 10 (short):**
| rank_ensemble | ticker | sector | pred_ensemble | out_of_training_dist |
|---|---|---|---|---|
| 80 | ASML.AS | Technology | +0.1899 | 1 |
| 81 | AAPL | Technology | +0.1359 | 0 |
| 82 | NOW | Technology | +0.1226 | 0 |
| 83 | V | Financial Services | +0.1013 | 0 |
| 84 | CVX | Energy, Materials & Utilities | +0.0675 | 0 |
| 85 | PG | Consumer Staples | +0.0048 | 0 |
| 86 | TSM | Technology | -0.0053 | 1 |
| 87 | INTC | Technology | -0.2116 | 0 |
| 88 | AZN.L | Healthcare | -0.2206 | 1 |
| 89 | SHOP.TO | Technology | -0.7383 | 1 |

Full ranking of all 89 in predictions_all89.csv (final models refit on ALL train_eligible rows; the 89 rows are each company's latest report, forward window still open — these are the ranking signals, not evaluable yet).