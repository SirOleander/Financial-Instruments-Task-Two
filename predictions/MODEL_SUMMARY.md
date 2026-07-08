# Forward-63d-Sharpe models — training & evaluation

Leak-safe: time split at **2025-03-31** (train+val <= vs 12-month test >), TimeSeriesSplit CV (5 folds, gap=21), per-fold winsor + impute + scale, target winsorized per fold. Test set touched once. Selection metric = Spearman (ranking task).

## CV rank-correlation (train+val, model selection)

| model | cv_spearman_mean | cv_spearman_std | degenerate_constant |
|---|---|---|---|
| ElasticNet | +0.0122 | +0.0149 | 1 |
| Lasso | +0.0000 | +0.0000 | 1 |
| SVR | -0.0011 | +0.0852 | 0 |
| XGBoost | -0.0114 | +0.0824 | 0 |
| RandomForest | -0.0142 | +0.0841 | 0 |
| Ridge | -0.0317 | +0.0910 | 0 |

**ElasticNet, Lasso collapsed to the NULL (constant) model** — with near-zero linear signal, regularization drives all coefficients to 0 and predicts the mean (CV Spearman 0.0 beats any negative). They carry no ranking information and are EXCLUDED from the ensemble. That collapse is itself an informative result: no linear feature combination beats the mean.

All CV means lie within ~±0.04 of zero with per-fold std ~0.07–0.10, i.e. **indistinguishable from no signal** — consistent with the EDA.

## One-shot TEST metrics (held-out 12 months)

| model | test_spearman_pooled | test_spearman_perperiod_mean | decile_spread_latestperco | perperiod_top10bot10_spread_mean | test_rmse |
|---|---|---|---|---|---|
| Ridge | -0.0302 | -0.0403 | +0.2778 | +0.2114 | +2.1404 |
| Lasso | +0.0000 | +0.0000 | -0.3515 | -0.2085 | +2.1036 |
| ElasticNet | +0.0000 | +0.0000 | -0.3515 | -0.2085 | +2.1036 |
| RandomForest | -0.0221 | -0.0246 | +0.6458 | -0.3292 | +2.1158 |
| XGBoost | -0.0375 | -0.0079 | -0.4271 | -0.8240 | +2.1694 |
| SVR | +0.0071 | +0.0659 | +0.8222 | +0.1321 | +2.3474 |
| ENSEMBLE(mean:SVR+XGBoost+RandomForest) | -0.0222 | +0.0115 | +1.0964 | -0.6329 | +2.1609 |

**Ensemble = mean of best-3 NON-DEGENERATE models by CV Spearman: SVR, XGBoost, RandomForest.** The two decile-spread columns are noisy: the latest-per-company version ranks only ~7 names per tail, and the per-period top-10/bottom-10 spread averages over 4 test quarters — read signs, not magnitudes, and treat both as within-noise here.

## Honest verdict

EDA showed max single-feature |Spearman| ~0.075; the models confirm it. **CV Spearman is indistinguishable from zero for every model, test-set Spearman is ~0 to slightly negative, and the top-vs-bottom realized-Sharpe spreads flip sign across models** — i.e. no reliable, generalizable signal from report fundamentals to forward 63-day Sharpe on this universe/period. This is a valid, expected finding, reported straight and NOT tuned to manufacture a strong-looking number. The ranking below is produced for completeness (the pipeline is correct and leak-safe); it should be treated as low-confidence and the backtest read accordingly.

## Predicted ranking — top 10 (long) / bottom 10 (short)

`out_of_training_dist=1` = held-out international (scored, never trained; treat as lower-confidence).

**Top 10 (long):**
| rank_ensemble | ticker | sector | pred_ensemble | out_of_training_dist |
|---|---|---|---|---|
| 1 | BA | Industrials | +2.0955 | 0 |
| 2 | BAC | Banks | +1.8383 | 0 |
| 3 | MU | Technology | +1.6429 | 0 |
| 4 | 000660.KS | Technology | +1.5909 | 1 |
| 5 | KO | Consumer Staples | +1.5856 | 0 |
| 6 | SAN.MC | Banks | +1.5695 | 1 |
| 7 | SCHW | Banks | +1.5287 | 0 |
| 8 | 005930.KS | Technology | +1.5209 | 1 |
| 9 | LLY | Healthcare | +1.4826 | 0 |
| 10 | NFLX | Communication | +1.4771 | 0 |

**Bottom 10 (short):**
| rank_ensemble | ticker | sector | pred_ensemble | out_of_training_dist |
|---|---|---|---|---|
| 88 | CSCO | Technology | +0.1319 | 0 |
| 89 | AAPL | Technology | +0.1297 | 0 |
| 90 | INTU | Technology | +0.0889 | 0 |
| 91 | NOW | Technology | +0.0651 | 0 |
| 92 | TSM | Technology | +0.0219 | 1 |
| 93 | CVX | Energy, Materials & Utilities | -0.0261 | 0 |
| 94 | AZN.L | Healthcare | -0.0939 | 1 |
| 95 | PG | Consumer Staples | -0.1905 | 0 |
| 96 | INTC | Technology | -0.2293 | 0 |
| 97 | SHOP.TO | Technology | -0.7199 | 1 |

Full ranking of all 89 in predictions_all89.csv (final models refit on ALL train_eligible rows; the 89 rows are each company's latest report, forward window still open — these are the ranking signals, not evaluable yet).