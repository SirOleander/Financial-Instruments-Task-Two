# Backtest — predicted top-10 long / bottom-10 short (test year)

**Framing: this is a test of the leak-free PIPELINE and an honest confirmation of the near-null model result — NOT a claim of alpha.** The ensemble (SVR + RF + XGBoost) is frozen on train+val (<= 2025-03-31) and applied forward to each of 4 quarterly rebalances in the held-out test year.

## Assumptions

- Equal-weight **top-10 long / bottom-10 short**, ranked by predicted future_63d_sharpe.
- Rebalance each fiscal quarter (~63 trading days); hold to next report period.
- Transaction cost on one-way traded notional, reported at 0 / 5 / 10 bps (primary = 10 bps).
- Periods with <20 names skipped (cannot form both legs); internationals included but flagged out-of-training.

## Risk-free rate

Constant **rf = 2.0% annualized** (~average 3-month US T-bill yield, FRED series TB3MS, over the 2020-2026 sample; the 3-month bill is the standard academic risk-free proxy). The strategy return series is one observation per ~63-trading-day rebalance, so the frequency-converted rate is **RF_PERIOD = 0.02 / 4 = 0.0050** per period — the annual 2% is never subtracted from a 63-day return.

The book is **dollar-neutral and self-financing**: the short proceeds fund the long leg and earn rf. That rf credit exactly cancels the rf subtracted to form an excess return —

```
net_p    = (long_p - short_p) + RF_PERIOD - cost_p
excess_p = net_p - RF_PERIOD = long_p - short_p - cost_p
```

— so **`ann_sharpe_LS` is unchanged by the risk-free rate**. This cancellation is a consequence of the self-financing structure, not an omission of rf. `ann_sharpe_LS_funded` is reported as a **sensitivity**: the naive fully-funded variant that charges rf on capital the strategy never borrowed (`excess_p = gross_ls_p - cost_p - 0.0050`). It is the more pessimistic reading, shown for transparency, not as the headline.

Note the target uses the SAME annual rate at a DIFFERENT horizon: `rf_daily = 0.02/252`, subtracted from each daily return before mean/std.

## Per-rebalance long-short (gross)

| period | n_universe | n_intl | long_ret | short_ret | gross_ls | intl_in_long | intl_in_short |
|---|---|---|---|---|---|---|---|
| 2025Q1 | 62 | 3 | +0.2675 | +0.0903 | +0.1772 | 0 | 0 |
| 2025Q2 | 85 | 18 | +0.0832 | +0.1300 | -0.0469 | 0 | 4 |
| 2025Q3 | 83 | 20 | +0.0540 | +0.1703 | -0.1163 | 2 | 6 |
| 2025Q4 | 39 | 20 | +0.1340 | -0.0020 | +0.1360 | 4 | 6 |

## Strategy summary by transaction cost

| cost_bps_oneway | cum_return_LS | mean_period_LS | ann_sharpe_LS | ann_sharpe_LS_funded | max_drawdown_LS |
|---|---|---|---|---|---|
| +0.0000 | +0.1264 | +0.0375 | +0.5305 | +0.4598 | -0.1577 |
| +5.0000 | +0.1200 | +0.0361 | +0.5096 | +0.4390 | -0.1605 |
| +10.0000 | +0.1136 | +0.0346 | +0.4887 | +0.4181 | -0.1633 |

**Headline (@10bps):** cumulative long-short +11.36%, annualized Sharpe +0.49 (self-financing; fully-funded sensitivity +0.42), max drawdown -16.33% over 4 quarterly rebalances.

Context (gross): long leg +64.11%, short leg +43.91%, equal-weight universe +42.48%.

## Honest read

The per-rebalance spread FLIPS SIGN (2 of 4 positive) and its mean +3.75% sits well inside one standard deviation 14.14% (t = +0.53 on 3 d.f.) — **not distinguishable from zero**, whatever sign the cumulative figure takes. Do not read the cumulative number as an edge.

With only 4 rebalances the Sharpe/drawdown are high-variance and should not be over-interpreted. Given the model showed no reliable rank signal (CV & test Spearman ~0, robust across the feature-set ablation), any long-short spread here is consistent with noise, not a repeatable edge. The deliverable is the END-TO-END LEAK-FREE PIPELINE (features knowable at release date, time-based split, per-fold preprocessing, frozen-model walk-forward, costs) producing an honest — and honestly weak — result, as expected under market efficiency.
