# Backtest — predicted top-10 long / bottom-10 short (test year)

**Framing: this is a test of the leak-free PIPELINE and an honest confirmation of the near-null model result — NOT a claim of alpha.** The ensemble (SVR + RF + XGBoost) is frozen on train+val (<= 2025-03-31) and applied forward to each of 4 quarterly rebalances in the held-out test year.

## Assumptions

- Equal-weight **top-10 long / bottom-10 short**, ranked by predicted future_63d_sharpe.
- Rebalance each fiscal quarter (~63 trading days); hold to next report period.
- Transaction cost on one-way traded notional, reported at 0 / 5 / 10 bps (primary = 10 bps). Risk-free = 0.
- Periods with <20 names skipped (cannot form both legs); internationals included but flagged out-of-training.

## Per-rebalance long-short (gross)

| period | n_universe | n_intl | long_ret | short_ret | gross_ls | intl_in_long | intl_in_short |
|---|---|---|---|---|---|---|---|
| 2025Q1 | 62 | 3 | +0.2675 | +0.0910 | +0.1766 | 0 | 0 |
| 2025Q2 | 85 | 18 | +0.0832 | +0.1300 | -0.0469 | 0 | 4 |
| 2025Q3 | 83 | 20 | +0.0134 | +0.2093 | -0.1960 | 1 | 5 |
| 2025Q4 | 39 | 20 | +0.0624 | -0.0201 | +0.0825 | 5 | 6 |

## Strategy summary by transaction cost

| cost_bps_oneway | cum_return_LS | mean_period_LS | ann_sharpe_LS | max_drawdown_LS |
|---|---|---|---|---|
| +0.0000 | -0.0240 | +0.0041 | +0.0501 | -0.2337 |
| +5.0000 | -0.0298 | +0.0026 | +0.0322 | -0.2362 |
| +10.0000 | -0.0356 | +0.0012 | +0.0142 | -0.2388 |

**Headline (@10bps):** cumulative long-short -3.56%, annualized Sharpe +0.01, max drawdown -23.88% over 4 quarterly rebalances.

Context (gross): long leg +47.80%, short leg +46.09%, equal-weight universe +42.48%.

## Honest read

With only 4 rebalances the Sharpe/drawdown are high-variance and should not be over-interpreted. Given the model showed no reliable rank signal (CV & test Spearman ~0, robust across the feature-set ablation), any long-short spread here is consistent with noise, not a repeatable edge. The deliverable is the END-TO-END LEAK-FREE PIPELINE (features knowable at release date, time-based split, per-fold preprocessing, frozen-model walk-forward, costs) producing an honest — and honestly weak — result, as expected under market efficiency.
