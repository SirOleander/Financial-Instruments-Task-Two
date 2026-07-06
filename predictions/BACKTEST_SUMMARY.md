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
| 2025Q1 | 63 | 3 | +0.2803 | +0.1250 | +0.1553 | 0 | 0 |
| 2025Q2 | 86 | 18 | +0.0771 | +0.1300 | -0.0530 | 0 | 4 |
| 2025Q3 | 84 | 20 | +0.0540 | +0.2227 | -0.1687 | 2 | 5 |
| 2025Q4 | 39 | 20 | +0.0863 | -0.0257 | +0.1121 | 5 | 6 |

## Strategy summary by transaction cost

| cost_bps_oneway | cum_return_LS | mean_period_LS | ann_sharpe_LS | max_drawdown_LS |
|---|---|---|---|---|
| +0.0000 | +0.0115 | +0.0114 | +0.1525 | -0.2127 |
| +5.0000 | +0.0054 | +0.0100 | +0.1327 | -0.2154 |
| +10.0000 | -0.0006 | +0.0085 | +0.1130 | -0.2181 |

**Headline (@10bps):** cumulative long-short -0.06%, annualized Sharpe +0.11, max drawdown -21.81% over 4 quarterly rebalances.

Context (gross): long leg +57.90%, short leg +51.44%, equal-weight universe +43.08%.

## Honest read

With only 4 rebalances the Sharpe/drawdown are high-variance and should not be over-interpreted. Given the model showed no reliable rank signal (CV & test Spearman ~0, robust across the feature-set ablation), any long-short spread here is consistent with noise, not a repeatable edge. The deliverable is the END-TO-END LEAK-FREE PIPELINE (features knowable at release date, time-based split, per-fold preprocessing, frozen-model walk-forward, costs) producing an honest — and honestly weak — result, as expected under market efficiency.
