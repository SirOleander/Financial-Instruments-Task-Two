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
| 2025Q1 | 60 | 2 | +0.2248 | +0.0733 | +0.1515 | 0 | 0 |
| 2025Q2 | 82 | 16 | +0.0768 | +0.1300 | -0.0532 | 0 | 4 |
| 2025Q3 | 80 | 18 | +0.0212 | +0.2288 | -0.2076 | 1 | 5 |
| 2025Q4 | 37 | 18 | +0.1340 | +0.0010 | +0.1331 | 4 | 7 |

## Strategy summary by transaction cost

| cost_bps_oneway | cum_return_LS | mean_period_LS | ann_sharpe_LS | max_drawdown_LS |
|---|---|---|---|---|
| +0.0000 | -0.0211 | +0.0059 | +0.0700 | -0.2497 |
| +5.0000 | -0.0272 | +0.0044 | +0.0523 | -0.2526 |
| +10.0000 | -0.0332 | +0.0029 | +0.0346 | -0.2554 |

**Headline (@10bps):** cumulative long-short -3.32%, annualized Sharpe +0.03, max drawdown -25.54% over 4 quarterly rebalances.

Context (gross): long leg +52.73%, short leg +49.18%, equal-weight universe +43.16%.

## Honest read

With only 4 rebalances the Sharpe/drawdown are high-variance and should not be over-interpreted. Given the model showed no reliable rank signal (CV & test Spearman ~0, robust across the feature-set ablation), any long-short spread here is consistent with noise, not a repeatable edge. The deliverable is the END-TO-END LEAK-FREE PIPELINE (features knowable at release date, time-based split, per-fold preprocessing, frozen-model walk-forward, costs) producing an honest — and honestly weak — result, as expected under market efficiency.
