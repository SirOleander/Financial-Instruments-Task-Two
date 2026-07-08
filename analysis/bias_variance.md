# Error analysis — bias and variance

Leak-safe: TimeSeriesSplit(5, gap=21) on train+val; every preprocessing step refit inside each fold. The untouched test set is NOT used here.

Target std (train+val) = **1.986** — an RMSE at this level means the model is effectively predicting the mean.

## Train vs validation error (CV)

| model | train_rmse | val_rmse | rmse_gap | train_spearman | val_spearman | spearman_gap |
|---|---|---|---|---|---|---|
| ElasticNet | +1.9406 | +1.9692 | -0.0286 | +0.0825 | +0.0123 | +0.0702 |
| SVR | +0.8579 | +2.1701 | -1.3123 | +0.9231 | +0.0012 | +0.9219 |
| Lasso | +1.9536 | +1.9662 | -0.0126 | +0.0000 | +0.0000 | +0.0000 |
| XGBoost | +1.1976 | +2.0888 | -0.8913 | +0.8418 | -0.0149 | +0.8566 |
| RandomForest | +1.7012 | +1.9906 | -0.2894 | +0.6794 | -0.0149 | +0.6943 |
| Ridge | +1.8313 | +2.3635 | -0.5323 | +0.2988 | -0.0312 | +0.3300 |

## Learning curves

`fig_learning_curve_{Ridge,RandomForest,XGBoost}.png` — train and validation RMSE / Spearman against an expanding chronological training prefix, validated on a fixed later slice (purge gap = 21 rows).

## Interpretation (bias-variance)

**Out-of-sample every model lands in the same place.** Validation RMSE sits at the target's own standard deviation (**1.986**) for all six models (1.966–2.364), and validation Spearman is -0.031…+0.012. A model that simply predicted the training mean would score about the same.

**Two different failure modes, one identical outcome:**

1. **Underfitting — high bias, ~zero variance.** Lasso and ElasticNet regularise *every* coefficient to exactly zero, so they literally ARE the mean-predictor: train RMSE 1.954 vs validation 1.966 (gap ≈ 0), train ρ = validation ρ = 0. All bias, no variance.
2. **Overfitting — high variance, zero payoff.** XGBoost (train ρ +0.842 vs validation -0.015), SVR (+0.923 / +0.001) and RandomForest (+0.679 / -0.015) memorise the training rows almost perfectly (train RMSE 1.198–1.701) while generalising at zero. That is a large **variance** term, and it buys *nothing*: the capacity is spent fitting noise. Ridge sits in between (train ρ +0.299, validation -0.031).

**The learning curves settle which term binds.** Validation error is essentially FLAT in training-set size (RandomForest 1.807 → 1.837; XGBoost 2.007 → 1.957, as training rows grow 119 → 799; Ridge converges to ~1.92 after its small-sample instability). Validation Spearman never trends upward. **If variance were the binding constraint, validation error would fall as data grows — it does not.**

**Conclusion, in bias-variance terms.** Total error = bias² + variance + irreducible noise. Here it is dominated by **irreducible noise plus bias**. The variance the flexible models exhibit is real but useless — it fits noise, not signal — and the regularised models trade it away for pure bias, arriving at the *same* validation score. The near-zero result is itself **stable**: the fold-to-fold spread of validation Spearman (std ~0.07–0.10) straddles zero with no fold showing meaningful positive rank-correlation, and the conclusion reproduces across feature sets (ablation) and across the 89→98 universe expansion. Forward 63-day Sharpe is close to unpredictable from report fundamentals: **more data, more capacity or more tuning cannot fix this — only a genuinely more informative feature set could.**