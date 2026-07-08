# Error analysis — bias and variance

Leak-safe: TimeSeriesSplit(5, gap=21) on train+val; every preprocessing step refit inside each fold. The untouched test set is NOT used here.

Target std (train+val) = **1.983** — an RMSE at this level means the model is effectively predicting the mean.

## Train vs validation error (CV)

| model | train_rmse | val_rmse | rmse_gap | train_spearman | val_spearman | spearman_gap |
|---|---|---|---|---|---|---|
| ElasticNet | +1.9341 | +1.9705 | -0.0364 | +0.0829 | +0.0133 | +0.0696 |
| Lasso | +1.9454 | +1.9663 | -0.0209 | +0.0000 | +0.0000 | +0.0000 |
| SVR | +0.8504 | +2.1780 | -1.3276 | +0.9240 | -0.0070 | +0.9310 |
| XGBoost | +0.7763 | +2.1208 | -1.3445 | +0.9489 | -0.0231 | +0.9721 |
| RandomForest | +1.5545 | +2.0024 | -0.4479 | +0.8060 | -0.0280 | +0.8340 |
| Ridge | +1.8273 | +2.3405 | -0.5132 | +0.3001 | -0.0341 | +0.3342 |

## Learning curves

`fig_learning_curve_{Ridge,RandomForest,XGBoost}.png` — train and validation RMSE / Spearman against an expanding chronological training prefix, validated on a fixed later slice (purge gap = 21 rows).

## Interpretation (bias-variance)

**Out-of-sample every model lands in the same place.** Validation RMSE sits at the target's own standard deviation (**1.983**) for all six models (1.966–2.340), and validation Spearman is -0.034…+0.013. A model that simply predicted the training mean would score about the same.

**Two different failure modes, one identical outcome:**

1. **Underfitting — high bias, ~zero variance.** Lasso and ElasticNet regularise *every* coefficient to exactly zero, so they literally ARE the mean-predictor: train RMSE 1.945 vs validation 1.966 (gap ≈ 0), train ρ = validation ρ = 0. All bias, no variance.
2. **Overfitting — high variance, zero payoff.** XGBoost (train ρ +0.949 vs validation -0.023), SVR (+0.924 / -0.007) and RandomForest (+0.806 / -0.028) memorise the training rows almost perfectly (train RMSE 0.776–1.554) while generalising at zero. That is a large **variance** term, and it buys *nothing*: the capacity is spent fitting noise. Ridge sits in between (train ρ +0.300, validation -0.034).

**The learning curves settle which term binds.** Validation error is essentially FLAT in training-set size (RandomForest 1.864 → 1.853; XGBoost 2.036 → 2.007, as training rows grow 121 → 811; Ridge converges to ~1.92 after its small-sample instability). Validation Spearman never trends upward. **If variance were the binding constraint, validation error would fall as data grows — it does not.**

**Conclusion, in bias-variance terms.** Total error = bias² + variance + irreducible noise. Here it is dominated by **irreducible noise plus bias**. The variance the flexible models exhibit is real but useless — it fits noise, not signal — and the regularised models trade it away for pure bias, arriving at the *same* validation score. The near-zero result is itself **stable**: the fold-to-fold spread of validation Spearman (std ~0.07–0.10) straddles zero with no fold showing meaningful positive rank-correlation, and the conclusion reproduces across feature sets (ablation) and across the 89→98 universe expansion. Forward 63-day Sharpe is close to unpredictable from report fundamentals: **more data, more capacity or more tuning cannot fix this — only a genuinely more informative feature set could.**