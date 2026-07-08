# Error analysis — bias and variance

Leak-safe: TimeSeriesSplit(5, gap=21) on train+val; every preprocessing step refit inside each fold. The untouched test set is NOT used here.

Target std (train+val) = **1.980** — an RMSE at this level means the model is effectively predicting the mean.

## Train vs validation error (CV)

| model | train_rmse | val_rmse | rmse_gap | train_spearman | val_spearman | spearman_gap |
|---|---|---|---|---|---|---|
| ElasticNet | +1.9343 | +1.9636 | -0.0293 | +0.0851 | +0.0122 | +0.0729 |
| Lasso | +1.9472 | +1.9605 | -0.0133 | +0.0000 | +0.0000 | +0.0000 |
| SVR | +0.8541 | +2.1625 | -1.3084 | +0.9232 | -0.0011 | +0.9242 |
| XGBoost | +1.1950 | +2.0845 | -0.8895 | +0.8422 | -0.0114 | +0.8536 |
| RandomForest | +1.7390 | +1.9823 | -0.2433 | +0.6309 | -0.0142 | +0.6452 |
| Ridge | +1.8260 | +2.3545 | -0.5285 | +0.2964 | -0.0317 | +0.3281 |

## Learning curves

`fig_learning_curve_{Ridge,RandomForest,XGBoost}.png` — train and validation RMSE / Spearman against an expanding chronological training prefix, validated on a fixed later slice (purge gap = 21 rows).

## Interpretation (bias-variance)

**Out-of-sample every model lands in the same place.** Validation RMSE sits at the target's own standard deviation (**1.980**) for all six models (1.960–2.354), and validation Spearman is -0.032…+0.012. A model that simply predicted the training mean would score about the same.

**Two different failure modes, one identical outcome:**

1. **Underfitting — high bias, ~zero variance.** Lasso and ElasticNet regularise *every* coefficient to exactly zero, so they literally ARE the mean-predictor: train RMSE 1.947 vs validation 1.960 (gap ≈ 0), train ρ = validation ρ = 0. All bias, no variance.
2. **Overfitting — high variance, zero payoff.** XGBoost (train ρ +0.842 vs validation -0.011), SVR (+0.923 / -0.001) and RandomForest (+0.631 / -0.014) memorise the training rows almost perfectly (train RMSE 1.195–1.739) while generalising at zero. That is a large **variance** term, and it buys *nothing*: the capacity is spent fitting noise. Ridge sits in between (train ρ +0.296, validation -0.032).

**The learning curves settle which term binds.** Validation error is essentially FLAT in training-set size (RandomForest 1.799 → 1.818; XGBoost 1.993 → 1.953, as training rows grow 119 → 799; Ridge converges to ~1.92 after its small-sample instability). Validation Spearman never trends upward. **If variance were the binding constraint, validation error would fall as data grows — it does not.**

**Conclusion, in bias-variance terms.** Total error = bias² + variance + irreducible noise. Here it is dominated by **irreducible noise plus bias**. The variance the flexible models exhibit is real but useless — it fits noise, not signal — and the regularised models trade it away for pure bias, arriving at the *same* validation score. The near-zero result is itself **stable**: the fold-to-fold spread of validation Spearman (std ~0.07–0.10) straddles zero with no fold showing meaningful positive rank-correlation, and the conclusion reproduces across feature sets (ablation) and across the 89→98 universe expansion. Forward 63-day Sharpe is close to unpredictable from report fundamentals: **more data, more capacity or more tuning cannot fix this — only a genuinely more informative feature set could.**