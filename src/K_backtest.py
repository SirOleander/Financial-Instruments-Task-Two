"""
K_backtest.py — analytical phase, step 8: backtest the predicted ranking (leak-safe).

Frames the strategy as a TEST OF THE PIPELINE / honest confirmation of the near-null model
result — not a claim of alpha. Reads modelling_data, refits the chosen ENSEMBLE (SVR + RF +
XGBoost, best-3 non-degenerate from J_models) on train+val (<= 2025-03-31) ONCE, then walks
the held-out test year quarter by quarter: rank the reporting universe by predicted
future_63d_sharpe, hold an equal-weight top-10 LONG / bottom-10 SHORT book for the next 63
trading days, realize returns, subtract transaction costs. Writes artifacts to predictions/;
modifies NO DB table.

LEAK CONTROL: the ensemble is frozen on pre-test data; every rebalance only applies it to
later reports (exactly how it would run live). Only rows with a COMPLETE 63-day forward
window (future_63d_return not null) enter the book. Internationals (train_eligible=0) are
included in the universe but FLAGGED out-of-training.

ASSUMPTIONS (stated): equal-weight top-10 long / bottom-10 short; rebalance each fiscal
quarter (~63 trading days); hold to the next report period; transaction cost applied to
one-way traded notional at each rebalance (reported at 0 / 5 / 10 bps); risk-free = 0;
periods with <20 names skipped (cannot form both legs). 4 quarterly rebalances span the test
year — Sharpe on 4 points is noisy (caveat).

USAGE (run from inside src/):
    python K_backtest.py
"""
from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.svm import SVR
from xgboost import XGBRegressor

import J_models as J

OUT = J.OUT
LEG = 10               # top-10 long / bottom-10 short
MIN_NAMES = 2 * LEG    # need >=20 names to form both legs
COST_BPS_GRID = [0.0, 5.0, 10.0]   # one-way, in bps of traded notional
PRIMARY_COST_BPS = 10.0
PERIODS_PER_YEAR = 252 / 63        # ~4 (63-trading-day holding)


def ensemble_members():
    """The 3 non-degenerate models with the hyperparameters J_models tuned by CV."""
    return {
        "SVR": (SVR(kernel="rbf", gamma="scale", epsilon=0.1, C=10), True),
        "RandomForest": (RandomForestRegressor(n_estimators=400, max_depth=None,
                         max_features=0.5, min_samples_leaf=20, random_state=J.SEED, n_jobs=1),
                         False),
        "XGBoost": (XGBRegressor(n_estimators=300, subsample=0.8, colsample_bytree=0.8,
                    max_depth=2, learning_rate=0.05, reg_lambda=5, random_state=J.SEED,
                    n_jobs=1, verbosity=0), False),
    }


def _fit_ensemble(Xtv, ytv):
    fitted = []
    for name, (model, scale) in ensemble_members().items():
        pipe = Pipeline([("prep", J.make_preprocessor(scale)), ("model", model)])
        ttr = TransformedTargetRegressor(regressor=pipe, transformer=J.YWinsorizer())
        ttr.fit(Xtv, ytv)
        fitted.append(ttr)
    return fitted


def _predict_ensemble(fitted, X):
    return np.mean([m.predict(X) for m in fitted], axis=0)


def _max_drawdown(equity: np.ndarray) -> float:
    peak = np.maximum.accumulate(equity)
    return float((equity / peak - 1.0).min())


def main():
    os.makedirs(OUT, exist_ok=True)
    df, trainval, test, _ = J.load()

    # freeze ensemble on train+val
    Xtv, ytv = J.build_X(trainval), trainval[J.TARGET_RAW].values
    fitted = _fit_ensemble(Xtv, ytv)

    # backtest universe: quarterly, test window, complete forward window, has change features
    df["rd"] = pd.to_datetime(df["report_release_date"])
    uni = df[(df["rd"] > pd.Timestamp(J.SPLIT_DATE)) & (df["frequency"] == "quarterly")
             & (df["future_63d_return"].notna()) & (df["first_obs"] == 0)].copy()
    uni["pred"] = _predict_ensemble(fitted, J.build_X(uni))
    uni["intl"] = (uni["source"] != "edgar").astype(int)

    periods = sorted(p for p, g in uni.groupby("period") if len(g) >= MIN_NAMES)
    print(f"Ensemble frozen on train+val ({len(trainval)} rows). Backtest rebalances: "
          f"{periods}  (skipped <{MIN_NAMES}-name periods)")

    prev_long, prev_short = set(), set()
    rows, holdings = [], []
    for per in periods:
        g = uni[uni["period"] == per].sort_values("pred", ascending=False)
        longs = g.head(LEG)
        shorts = g.tail(LEG)
        lset, sset = set(longs["ticker"]), set(shorts["ticker"])
        long_ret = longs["future_63d_return"].mean()
        short_ret = shorts["future_63d_return"].mean()
        gross_ls = long_ret - short_ret
        # one-way traded notional per leg = 0.1 * |symmetric difference| vs prior book
        traded = 0.1 * (len(lset ^ prev_long) + len(sset ^ prev_short))
        rows.append({
            "period": per, "n_universe": len(g), "n_intl": int(g["intl"].sum()),
            "long_ret": long_ret, "short_ret": short_ret, "gross_ls": gross_ls,
            "traded_notional_oneway": traded,
            "intl_in_long": int(longs["intl"].sum()), "intl_in_short": int(shorts["intl"].sum()),
        })
        for _, r in pd.concat([longs.assign(leg="long"), shorts.assign(leg="short")]).iterrows():
            holdings.append({"period": per, "leg": r["leg"], "ticker": r["ticker"],
                             "sector": r["sector"], "pred": round(r["pred"], 4),
                             "realized_63d_return": round(r["future_63d_return"], 4),
                             "out_of_training_dist": r["intl"]})
        prev_long, prev_short = lset, sset

    bt = pd.DataFrame(rows)

    # apply transaction costs at each cost level; compound the long-short book
    summary = []
    equity_curves = {}
    for c in COST_BPS_GRID:
        cost = (c / 1e4) * bt["traded_notional_oneway"].values
        net = bt["gross_ls"].values - cost
        equity = np.cumprod(1.0 + net)
        equity_curves[c] = equity
        ann_sharpe = (net.mean() / net.std(ddof=1) * np.sqrt(PERIODS_PER_YEAR)
                      if net.std(ddof=1) > 0 else np.nan)
        summary.append({
            "cost_bps_oneway": c,
            "cum_return_LS": float(equity[-1] - 1.0),
            "mean_period_LS": float(net.mean()),
            "ann_sharpe_LS": float(ann_sharpe),
            "max_drawdown_LS": _max_drawdown(equity),
            "n_rebalances": len(bt),
        })
    # long-only and short-only legs (gross, context) + universe benchmark
    long_cum = float(np.cumprod(1.0 + bt["long_ret"].values)[-1] - 1.0)
    short_cum = float(np.cumprod(1.0 + bt["short_ret"].values)[-1] - 1.0)
    bench = float(np.cumprod(1.0 + uni.groupby("period")["future_63d_return"].mean()
                             .reindex(periods).values)[-1] - 1.0)

    bt_out = bt.copy()
    bt_out["net_ls_%dbps" % int(PRIMARY_COST_BPS)] = (
        bt["gross_ls"] - (PRIMARY_COST_BPS / 1e4) * bt["traded_notional_oneway"])
    bt_out.round(4).to_csv(os.path.join(OUT, "backtest_periods.csv"), index=False)
    pd.DataFrame(holdings).to_csv(os.path.join(OUT, "backtest_holdings.csv"), index=False)
    sm = pd.DataFrame(summary)
    sm.round(4).to_csv(os.path.join(OUT, "backtest_summary.csv"), index=False)

    # equity curve figure (primary cost)
    fig, ax = plt.subplots(figsize=(9, 5))
    xs = range(1, len(bt) + 1)
    ax.plot(xs, equity_curves[PRIMARY_COST_BPS], marker="o", label=f"long-short @ {int(PRIMARY_COST_BPS)}bps")
    ax.plot(xs, np.cumprod(1 + bt["long_ret"].values), marker="^", ls="--", label="long leg (gross)")
    ax.plot(xs, np.cumprod(1 + bt["short_ret"].values), marker="v", ls="--", label="short leg (gross)")
    ax.axhline(1.0, color="k", lw=0.8, ls=":")
    ax.set_xticks(list(xs)); ax.set_xticklabels(bt["period"], rotation=20)
    ax.set_ylabel("growth of $1"); ax.legend(fontsize=8)
    ax.set_title("Backtest equity — top-10 long / bottom-10 short (test year, ensemble)")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_backtest_equity.png"), dpi=110, bbox_inches="tight")
    plt.close(fig)

    # console report
    print("\nPer-rebalance long-short (gross):")
    print(bt[["period", "n_universe", "n_intl", "long_ret", "short_ret", "gross_ls",
              "intl_in_long", "intl_in_short"]].round(4).to_string(index=False))
    print("\nStrategy summary by transaction cost:")
    print(sm.round(4).to_string(index=False))
    print(f"\nContext (gross, compounded over the {len(bt)} rebalances): "
          f"long-leg={long_cum:+.4f}  short-leg={short_cum:+.4f}  "
          f"equal-weight universe benchmark={bench:+.4f}")

    write_summary(bt, sm, long_cum, short_cum, bench, periods)
    print(f"\nArtifacts -> {OUT}: backtest_periods.csv, backtest_holdings.csv, "
          f"backtest_summary.csv, fig_backtest_equity.png, BACKTEST_SUMMARY.md")


def write_summary(bt, sm, long_cum, short_cum, bench, periods):
    def tbl(d, cols):
        L = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
        for _, r in d.iterrows():
            L.append("| " + " | ".join(
                f"{r[c]:+.4f}" if isinstance(r[c], float) else str(r[c]) for c in cols) + " |")
        return "\n".join(L)

    prim = sm[sm["cost_bps_oneway"] == PRIMARY_COST_BPS].iloc[0]
    L = ["# Backtest — predicted top-10 long / bottom-10 short (test year)\n"]
    L.append("**Framing: this is a test of the leak-free PIPELINE and an honest confirmation "
             "of the near-null model result — NOT a claim of alpha.** The ensemble (SVR + RF "
             f"+ XGBoost) is frozen on train+val (<= {J.SPLIT_DATE}) and applied forward to "
             f"each of {len(bt)} quarterly rebalances in the held-out test year.\n")
    L.append("## Assumptions\n")
    L.append(f"- Equal-weight **top-{LEG} long / bottom-{LEG} short**, ranked by predicted "
             "future_63d_sharpe.\n"
             "- Rebalance each fiscal quarter (~63 trading days); hold to next report period.\n"
             "- Transaction cost on one-way traded notional, reported at 0 / 5 / 10 bps "
             f"(primary = {int(PRIMARY_COST_BPS)} bps). Risk-free = 0.\n"
             f"- Periods with <{MIN_NAMES} names skipped (cannot form both legs); "
             "internationals included but flagged out-of-training.\n")
    L.append("## Per-rebalance long-short (gross)\n")
    L.append(tbl(bt, ["period", "n_universe", "n_intl", "long_ret", "short_ret", "gross_ls",
                      "intl_in_long", "intl_in_short"]))
    L.append("\n## Strategy summary by transaction cost\n")
    L.append(tbl(sm, ["cost_bps_oneway", "cum_return_LS", "mean_period_LS", "ann_sharpe_LS",
                      "max_drawdown_LS"]))
    L.append(f"\n**Headline (@{int(PRIMARY_COST_BPS)}bps):** cumulative long-short "
             f"{prim['cum_return_LS']:+.2%}, annualized Sharpe {prim['ann_sharpe_LS']:+.2f}, "
             f"max drawdown {prim['max_drawdown_LS']:+.2%} over {int(prim['n_rebalances'])} "
             "quarterly rebalances.\n")
    L.append(f"Context (gross): long leg {long_cum:+.2%}, short leg {short_cum:+.2%}, "
             f"equal-weight universe {bench:+.2%}.\n")
    L.append("## Honest read\n")
    L.append("With only 4 rebalances the Sharpe/drawdown are high-variance and should not be "
             "over-interpreted. Given the model showed no reliable rank signal (CV & test "
             "Spearman ~0, robust across the feature-set ablation), any long-short spread here "
             "is consistent with noise, not a repeatable edge. The deliverable is the "
             "END-TO-END LEAK-FREE PIPELINE (features knowable at release date, time-based "
             "split, per-fold preprocessing, frozen-model walk-forward, costs) producing an "
             "honest — and honestly weak — result, as expected under market efficiency.\n")
    with open(os.path.join(OUT, "BACKTEST_SUMMARY.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))


if __name__ == "__main__":
    main()
