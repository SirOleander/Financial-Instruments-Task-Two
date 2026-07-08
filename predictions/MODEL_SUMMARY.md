# Forward-63d-Sharpe models — training & evaluation

Leak-safe: time split at **2025-03-31** (train+val <= vs 12-month test >), TimeSeriesSplit CV (5 folds, gap=21), per-fold winsor + impute + scale, target winsorized per fold. Test set touched once. Selection metric = Spearman (ranking task).

## CV rank-correlation (train+val, model selection)

| model | cv_spearman_mean | cv_spearman_std | degenerate_constant |
|---|---|---|---|
| ElasticNet | +0.0123 | +0.0155 | 1 |
| SVR | +0.0012 | +0.0865 | 0 |
| Lasso | +0.0000 | +0.0000 | 1 |
| XGBoost | -0.0149 | +0.0946 | 0 |
| RandomForest | -0.0149 | +0.0856 | 0 |
| Ridge | -0.0312 | +0.0938 | 0 |

**ElasticNet, Lasso collapsed to the NULL (constant) model** — with near-zero linear signal, regularization drives all coefficients to 0 and predicts the mean (CV Spearman 0.0 beats any negative). They carry no ranking information and are EXCLUDED from the ensemble. That collapse is itself an informative result: no linear feature combination beats the mean.

All CV means lie within ~±0.04 of zero with per-fold std ~0.07–0.10, i.e. **indistinguishable from no signal** — consistent with the EDA.

## One-shot TEST metrics (held-out 12 months)

| model | test_spearman_pooled | test_spearman_perperiod_mean | decile_spread_latestperco | perperiod_top10bot10_spread_mean | test_rmse |
|---|---|---|---|---|---|
| Ridge | -0.0378 | -0.0431 | -0.0983 | -0.0674 | +2.1407 |
| Lasso | +0.0000 | +0.0000 | -0.3422 | -0.2111 | +2.1017 |
| ElasticNet | +0.0000 | +0.0000 | -0.3422 | -0.2111 | +2.1017 |
| RandomForest | -0.0104 | +0.0012 | +0.8939 | -0.2739 | +2.1155 |
| XGBoost | -0.0303 | -0.0075 | -0.0735 | -0.5941 | +2.1612 |
| SVR | +0.0046 | +0.0444 | +0.8127 | +0.1266 | +2.3507 |
| ENSEMBLE(mean:SVR+XGBoost+RandomForest) | -0.0191 | +0.0148 | +0.5863 | -0.4968 | +2.1600 |

**Ensemble = mean of best-3 NON-DEGENERATE models by CV Spearman: SVR, XGBoost, RandomForest.** The two decile-spread columns are noisy: the latest-per-company version ranks only ~7 names per tail, and the per-period top-10/bottom-10 spread averages over 4 test quarters — read signs, not magnitudes, and treat both as within-noise here.

## Honest verdict

EDA showed max single-feature |Spearman| ~0.075; the models confirm it. **CV Spearman is indistinguishable from zero for every model, test-set Spearman is ~0 to slightly negative, and the top-vs-bottom realized-Sharpe spreads flip sign across models** — i.e. no reliable, generalizable signal from report fundamentals to forward 63-day Sharpe on this universe/period. This is a valid, expected finding, reported straight and NOT tuned to manufacture a strong-looking number. The ranking below is produced for completeness (the pipeline is correct and leak-safe); it should be treated as low-confidence and the backtest read accordingly.

## Predicted ranking — top 10 (long) / bottom 10 (short)

`out_of_training_dist=1` = held-out international (scored, never trained; treat as lower-confidence).

**Top 10 (long):**
| rank_ensemble | ticker | sector | pred_ensemble | out_of_training_dist |
|---|---|---|---|---|
| 1 | BA | Industrials | +2.1917 | 0 |
| 2 | BAC | Banks | +1.9766 | 0 |
| 3 | SAN.MC | Banks | +1.6943 | 1 |
| 4 | KO | Consumer Staples | +1.6837 | 0 |
| 5 | SCHW | Banks | +1.6796 | 0 |
| 6 | MU | Technology | +1.6302 | 0 |
| 7 | C | Banks | +1.6095 | 0 |
| 8 | 005930.KS | Technology | +1.5771 | 1 |
| 9 | LLY | Healthcare | +1.5736 | 0 |
| 10 | JPM | Banks | +1.5719 | 0 |

**Bottom 10 (short):**
| rank_ensemble | ticker | sector | pred_ensemble | out_of_training_dist |
|---|---|---|---|---|
| 88 | TCEHY | Communication | +0.2281 | 1 |
| 89 | AAPL | Technology | +0.2094 | 0 |
| 90 | INTU | Technology | +0.1764 | 0 |
| 91 | NOW | Technology | +0.1049 | 0 |
| 92 | CVX | Energy, Materials & Utilities | +0.0591 | 0 |
| 93 | AZN.L | Healthcare | +0.0219 | 1 |
| 94 | TSM | Technology | +0.0017 | 1 |
| 95 | PG | Consumer Staples | -0.1463 | 0 |
| 96 | INTC | Technology | -0.2004 | 0 |
| 97 | SHOP.TO | Technology | -0.6270 | 1 |

Full ranking of all 89 in predictions_all89.csv (final models refit on ALL train_eligible rows; the 89 rows are each company's latest report, forward window still open — these are the ranking signals, not evaluable yet).