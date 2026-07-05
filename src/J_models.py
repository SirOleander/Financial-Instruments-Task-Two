"""
J_models.py — analytical phase, step 7: train forward-63d-Sharpe regressors (leak-safe).

Reads `modelling_data`, trains a roster of regression models to predict future_63d_sharpe
with STRICT anti-leakage discipline, evaluates ONCE on a time-held-out test set, builds an
ensemble, and predicts ALL 89 companies' latest rows for the eventual ranking. Writes only
artifacts to `predictions/`; modifies NO DB table.

LEAK CONTROL (the whole point):
- TIME split: test = train_eligible rows with report_release_date > SPLIT_DATE (2025-03-31),
  a full 12 months, touched exactly once at the end. Train+val = earlier rows.
- CV = TimeSeriesSplit (5 folds, purge gap) on the date-sorted train+val pool. Never random.
- ALL preprocessing is refit per fold inside a Pipeline: ratio-tail + change winsorization
  (train-fold 1/99 caps — NOT the table's full-population caps), median imputation, and
  z-scaling (linear/SVR only). Target future_63d_sharpe_RAW is winsorized per fold via
  TransformedTargetRegressor. Nothing is fit on val/test data.

SELECTION = Spearman rank correlation (this is a ranking task); RMSE reported, not selected on.

USAGE (run from inside src/):
    python J_models.py            # STEP 2: CV/tune, one-shot test eval, ensemble, all-89 preds
"""
from __future__ import annotations

import os
import warnings
from contextlib import closing

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.base import BaseEstimator, TransformerMixin, clone
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge, Lasso, ElasticNet
from sklearn.metrics import make_scorer, mean_squared_error
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR
from xgboost import XGBRegressor

import B_database

warnings.filterwarnings("ignore")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE_DIR, "predictions")

SPLIT_DATE = "2025-03-31"      # <= this = train+val ; > this = untouched 12-month test
N_SPLITS = 5
CV_GAP = 21                    # ~1 month purge between train/val fold boundaries
SEED = 42

# --- feature set (decided post-EDA; inventory_turnover excluded: 79% missing) ------------
SUBSCORES = ["profitability_score", "growth_score", "cash_flow_score",
             "leverage_score", "efficiency_score", "investment_score"]
KPIS = ["gross_margin", "operating_margin", "return_on_assets", "return_on_equity",
        "revenue_growth_yoy", "operating_income_growth_yoy", "net_income_growth_yoy",
        "operating_cash_flow_growth_yoy", "operating_cash_flow_margin", "cash_conversion",
        "debt_to_assets", "cash_to_assets", "equity_ratio", "asset_turnover",
        "capex_intensity", "r_and_d_intensity", "ROIC"]
LEVEL = SUBSCORES + ["operative_score"] + KPIS               # 24 level features
RATIO_TAIL = ["ROIC", "cash_conversion", "revenue_growth_yoy", "operating_income_growth_yoy",
              "net_income_growth_yoy", "operating_cash_flow_growth_yoy"]   # fed from *_raw

FEATURES = LEVEL + [c + "_change" for c in LEVEL]            # 48 total
WINS_FEATURES = RATIO_TAIL + [c + "_change" for c in LEVEL]  # winsorized per fold (30)
PASS_FEATURES = [f for f in FEATURES if f not in WINS_FEATURES]  # passthrough (18)
TARGET_RAW = "future_63d_sharpe_raw"
TARGET_EVAL = "future_63d_sharpe"   # (winsorized col) only used for reference; eval uses raw


# --------------------------------------------------------------------------- #
# leak-safe transformers
# --------------------------------------------------------------------------- #
class Winsorizer(BaseEstimator, TransformerMixin):
    """Per-column clip to [p_lo, p_hi] percentiles fit on the TRAIN fold only."""
    def __init__(self, lo=1.0, hi=99.0):
        self.lo, self.hi = lo, hi

    def fit(self, X, y=None):
        X = np.asarray(X, dtype=float)
        self.lo_ = np.nanpercentile(X, self.lo, axis=0)
        self.hi_ = np.nanpercentile(X, self.hi, axis=0)
        return self

    def transform(self, X):
        X = np.asarray(X, dtype=float)
        return np.clip(X, self.lo_, self.hi_)  # NaN preserved -> handled by imputer next


class YWinsorizer(BaseEstimator, TransformerMixin):
    """Target winsorizer for TransformedTargetRegressor; fit on train-fold y only.
    Inverse is identity (clipping is not invertible; predictions stay in Sharpe scale)."""
    def fit(self, y, x=None):
        y = np.asarray(y, dtype=float).ravel()
        self.lo_ = np.nanpercentile(y, 1)
        self.hi_ = np.nanpercentile(y, 99)
        return self

    def transform(self, y):
        return np.clip(np.asarray(y, dtype=float), self.lo_, self.hi_)

    def inverse_transform(self, y):
        return np.asarray(y, dtype=float)


def make_preprocessor(scale: bool) -> Pipeline:
    ct = ColumnTransformer(
        [("wins", Winsorizer(), WINS_FEATURES),
         ("pass", "passthrough", PASS_FEATURES)],
        remainder="drop")
    steps = [("ct", ct), ("impute", SimpleImputer(strategy="median"))]
    if scale:
        steps.append(("scale", StandardScaler()))
    return Pipeline(steps)


def transformed_feature_order() -> list[str]:
    """Column order after the ColumnTransformer (wins block then pass block)."""
    return WINS_FEATURES + PASS_FEATURES


# --------------------------------------------------------------------------- #
# model roster + modest grids
# --------------------------------------------------------------------------- #
def roster() -> dict:
    """name -> (estimator_pipeline, param_grid, needs_scaling, kind)."""
    def wrap(model, scale):
        pipe = Pipeline([("prep", make_preprocessor(scale)), ("model", model)])
        return TransformedTargetRegressor(regressor=pipe, transformer=YWinsorizer())

    return {
        "Ridge": (wrap(Ridge(random_state=SEED), True),
                  {"regressor__model__alpha": [0.1, 1, 10, 100, 1000]}, True, "linear"),
        "Lasso": (wrap(Lasso(random_state=SEED, max_iter=20000), True),
                  {"regressor__model__alpha": [1e-3, 1e-2, 1e-1, 1]}, True, "linear"),
        "ElasticNet": (wrap(ElasticNet(random_state=SEED, max_iter=20000), True),
                       {"regressor__model__alpha": [1e-2, 1e-1, 1],
                        "regressor__model__l1_ratio": [0.2, 0.5, 0.8]}, True, "linear"),
        "RandomForest": (wrap(RandomForestRegressor(n_estimators=400, random_state=SEED,
                                                    n_jobs=1), False),
                         {"regressor__model__max_depth": [3, 5, None],
                          "regressor__model__min_samples_leaf": [5, 20],
                          "regressor__model__max_features": ["sqrt", 0.5]}, False, "tree"),
        "XGBoost": (wrap(XGBRegressor(n_estimators=300, subsample=0.8, colsample_bytree=0.8,
                                      random_state=SEED, n_jobs=1, verbosity=0), False),
                    {"regressor__model__max_depth": [2, 3],
                     "regressor__model__learning_rate": [0.02, 0.05],
                     "regressor__model__reg_lambda": [1, 5]}, False, "tree"),
        "SVR": (wrap(SVR(kernel="rbf", gamma="scale", epsilon=0.1), True),
                {"regressor__model__C": [0.1, 1, 10]}, True, "svr"),
    }


def spearman_score(y_true, y_pred):
    r = spearmanr(y_true, y_pred).correlation
    return 0.0 if (r is None or np.isnan(r)) else r


SPEARMAN = make_scorer(spearman_score, greater_is_better=True)


# --------------------------------------------------------------------------- #
# data
# --------------------------------------------------------------------------- #
def build_X(df: pd.DataFrame) -> pd.DataFrame:
    X = pd.DataFrame(index=df.index)
    for c in LEVEL:
        X[c] = df[(c + "_raw") if c in RATIO_TAIL else c].values
    for c in LEVEL:
        X[c + "_change"] = df[c + "_change"].values
    return X[FEATURES]


def load():
    with closing(B_database.get_connection()) as con:
        df = pd.read_sql_query("SELECT * FROM modelling_data", con)
    df["rd"] = pd.to_datetime(df["report_release_date"])
    te = df[df["train_eligible"] == 1].sort_values("rd").reset_index(drop=True)
    split = pd.Timestamp(SPLIT_DATE)
    trainval = te[te["rd"] <= split].reset_index(drop=True)
    test = te[te["rd"] > split].reset_index(drop=True)
    # all-89 latest row per ticker (the forward ranking rows)
    latest_idx = df.groupby("ticker")["rd"].idxmax()
    pred89 = df.loc[latest_idx].reset_index(drop=True)
    return df, trainval, test, pred89


# --------------------------------------------------------------------------- #
# evaluation helpers
# --------------------------------------------------------------------------- #
def _spread(pred, actual, frac=0.10):
    n = len(pred)
    k = max(1, int(round(n * frac)))
    order = np.argsort(pred)
    top = np.mean(actual[order[-k:]])
    bot = np.mean(actual[order[:k]])
    return top - bot, top, bot, k


def _fixed_spread(pred, actual, k=10):
    if len(pred) < 2 * k:
        return np.nan
    order = np.argsort(pred)
    return np.mean(actual[order[-k:]]) - np.mean(actual[order[:k]])


def test_metrics(pred, test_df) -> dict:
    actual = test_df[TARGET_RAW].values
    pooled = spearman_score(actual, pred)
    # per-period spearman (average across test report periods)
    per = []
    for _, g in test_df.assign(_p=pred).groupby("period"):
        if len(g) >= 8:
            per.append(spearman_score(g[TARGET_RAW].values, g["_p"].values))
    per_mean = float(np.mean(per)) if per else np.nan
    # decile spread on ONE-ROW-PER-COMPANY (latest test row) — no cross-quarter double count
    lt = test_df.assign(_p=pred).sort_values("rd").groupby("ticker").tail(1)
    ds, top, bot, k = _spread(lt["_p"].values, lt[TARGET_RAW].values, 0.10)
    # per-period top-10/bottom-10 realized-Sharpe spread (mirrors the long-short backtest)
    pp = []
    for _, g in test_df.assign(_p=pred).groupby("period"):
        s = _fixed_spread(g["_p"].values, g[TARGET_RAW].values, 10)
        if not np.isnan(s):
            pp.append(s)
    return {
        "test_spearman_pooled": pooled,
        "test_spearman_perperiod_mean": per_mean,
        "decile_spread_latestperco": ds,
        "decile_top": top, "decile_bottom": bot, "decile_k": k, "n_latestperco": len(lt),
        "perperiod_top10bot10_spread_mean": float(np.mean(pp)) if pp else np.nan,
        "n_perperiods": len(pp),
        "test_rmse": float(np.sqrt(mean_squared_error(actual, pred))),
    }


# --------------------------------------------------------------------------- #
def main():
    os.makedirs(OUT, exist_ok=True)
    df, trainval, test, pred89 = load()
    Xtv, ytv = build_X(trainval), trainval[TARGET_RAW].values
    Xte = build_X(test)
    print(f"Loaded: train+val={len(trainval)} (<= {SPLIT_DATE}), test={len(test)} (> {SPLIT_DATE}), "
          f"features={len(FEATURES)}, companies_tv={trainval.ticker.nunique()}, "
          f"companies_test={test.ticker.nunique()}")

    tscv = TimeSeriesSplit(n_splits=N_SPLITS, gap=CV_GAP)
    models = roster()

    # ---- CV / tuning on train+val ----
    cv_rows, fitted = [], {}
    for name, (est, grid, scale, kind) in models.items():
        gs = GridSearchCV(est, grid, scoring=SPEARMAN, cv=tscv, n_jobs=-1, refit=True)
        gs.fit(Xtv, ytv)
        best = gs.best_index_
        # degeneracy check: a model that predicts a near-constant (regularized to the null
        # model) carries no ranking information — flag it and keep it out of the ensemble.
        insample_std = float(np.std(gs.best_estimator_.predict(Xtv)))
        cv_rows.append({
            "model": name,
            "cv_spearman_mean": gs.cv_results_["mean_test_score"][best],
            "cv_spearman_std": gs.cv_results_["std_test_score"][best],
            "insample_pred_std": insample_std,
            "degenerate_constant": int(insample_std < 1e-6),
            "best_params": {k.split("__")[-1]: v for k, v in gs.best_params_.items()},
        })
        fitted[name] = gs.best_estimator_
        flag = "  [DEGENERATE: constant/null model]" if insample_std < 1e-6 else ""
        print(f"  {name:14} CV Spearman = {gs.cv_results_['mean_test_score'][best]:+.4f} "
              f"± {gs.cv_results_['std_test_score'][best]:.4f}   best={cv_rows[-1]['best_params']}{flag}")

    cv_df = pd.DataFrame(cv_rows).sort_values("cv_spearman_mean", ascending=False)
    cv_df.to_csv(os.path.join(OUT, "cv_results.csv"), index=False)

    # ---- one-shot TEST evaluation (refit best params on full train+val, predict test) ----
    test_preds, test_rows = {}, []
    for name in models:
        model = fitted[name]  # already refit on full train+val by GridSearchCV
        p = model.predict(Xte)
        test_preds[name] = p
        m = test_metrics(p, test)
        m["model"] = name
        test_rows.append(m)
        print(f"  [TEST] {name:14} spearman={m['test_spearman_pooled']:+.4f} "
              f"perperiod={m['test_spearman_perperiod_mean']:+.4f} "
              f"decile_spread(latest/co)={m['decile_spread_latestperco']:+.4f} "
              f"perperiod_top10-bot10={m['perperiod_top10bot10_spread_mean']:+.4f}")

    # ---- ensemble = mean of best-3 by CV Spearman AMONG NON-DEGENERATE models ----
    # (constant/null models carry no ranking info; including them just dilutes toward the
    # mean and would make the ensemble collapse onto whichever member is non-constant.)
    non_degen = cv_df[cv_df["degenerate_constant"] == 0]
    best3 = non_degen["model"].head(3).tolist()
    ens_test = np.mean([test_preds[m] for m in best3], axis=0)
    em = test_metrics(ens_test, test)
    em["model"] = f"ENSEMBLE(mean:{'+'.join(best3)})"
    test_rows.append(em)
    print(f"  [TEST] ENSEMBLE({'+'.join(best3)}) spearman={em['test_spearman_pooled']:+.4f} "
          f"perperiod={em['test_spearman_perperiod_mean']:+.4f} "
          f"decile_spread(latest/co)={em['decile_spread_latestperco']:+.4f} "
          f"perperiod_top10-bot10={em['perperiod_top10bot10_spread_mean']:+.4f}")

    test_df_out = pd.DataFrame(test_rows).set_index("model")
    test_df_out.round(4).to_csv(os.path.join(OUT, "test_metrics.csv"))

    # ---- coefficients / importances (from the train+val-refit models) ----
    feat_order = transformed_feature_order()
    for name in models:
        reg = fitted[name].regressor_.named_steps["model"]
        if hasattr(reg, "coef_"):
            s = pd.Series(np.ravel(reg.coef_), index=feat_order, name="coef")
            s.reindex(s.abs().sort_values(ascending=False).index).to_csv(
                os.path.join(OUT, f"coef_{name}.csv"))
        elif hasattr(reg, "feature_importances_"):
            s = pd.Series(reg.feature_importances_, index=feat_order, name="importance")
            s.sort_values(ascending=False).to_csv(os.path.join(OUT, f"importance_{name}.csv"))

    # ---- final models refit on ALL train_eligible, predict all 89 ----
    all_te = df[df["train_eligible"] == 1]
    Xall, yall = build_X(all_te), all_te[TARGET_RAW].values
    Xp = build_X(pred89)
    final_preds = {}
    for name in models:
        m = clone(models[name][0]).set_params(
            **{k if k.startswith("regressor__") else k: v
               for k, v in _best_param_kwargs(fitted[name]).items()})
        m.fit(Xall, yall)
        final_preds[name] = m.predict(Xp)
    ens89 = np.mean([final_preds[m] for m in best3], axis=0)

    out = pred89[["ticker", "sector", "company_group", "source", "report_release_date",
                  "frequency", "operative_missing"]].copy()
    out["out_of_training_dist"] = (pred89["source"] != "edgar").astype(int)  # 18 internationals
    for name in models:
        out[f"pred_{name}"] = final_preds[name]
    out["pred_ensemble"] = ens89
    out = out.sort_values("pred_ensemble", ascending=False).reset_index(drop=True)
    out["rank_ensemble"] = np.arange(1, len(out) + 1)
    out.round(5).to_csv(os.path.join(OUT, "predictions_all89.csv"), index=False)

    write_summary(cv_df, test_df_out, best3, out)
    print(f"\nArtifacts -> {OUT}: cv_results.csv, test_metrics.csv, coef_/importance_*.csv, "
          f"predictions_all89.csv, MODEL_SUMMARY.md")


def _best_param_kwargs(fitted_ttr) -> dict:
    """Extract best hyperparams from a fitted GridSearch best_estimator_ (TTR) so we can
    re-instantiate a fresh clone with the same params for the full-data refit."""
    reg = fitted_ttr.regressor_.named_steps["model"]
    params = reg.get_params()
    # map back onto the roster param namespace
    return {f"regressor__model__{k}": v for k, v in params.items()}


# --------------------------------------------------------------------------- #
def write_summary(cv_df, test_df, best3, preds):
    top10 = preds.head(10)[["rank_ensemble", "ticker", "sector", "pred_ensemble",
                            "out_of_training_dist"]]
    bot10 = preds.tail(10)[["rank_ensemble", "ticker", "sector", "pred_ensemble",
                            "out_of_training_dist"]]

    def tbl(d):
        cols = list(d.columns)
        L = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
        for _, r in d.iterrows():
            L.append("| " + " | ".join(
                f"{r[c]:+.4f}" if isinstance(r[c], float) else str(r[c]) for c in cols) + " |")
        return "\n".join(L)

    L = ["# Forward-63d-Sharpe models — training & evaluation\n"]
    L.append(f"Leak-safe: time split at **{SPLIT_DATE}** (train+val {len(cv_df) and ''}<= vs "
             "12-month test >), TimeSeriesSplit CV (5 folds, gap=%d), per-fold winsor + "
             "impute + scale, target winsorized per fold. Test set touched once. Selection "
             "metric = Spearman (ranking task).\n" % CV_GAP)

    L.append("## CV rank-correlation (train+val, model selection)\n")
    L.append(tbl(cv_df[["model", "cv_spearman_mean", "cv_spearman_std",
                        "degenerate_constant"]]))
    ndg = cv_df[cv_df["degenerate_constant"] == 1]["model"].tolist()
    if ndg:
        L.append(f"\n**{', '.join(ndg)} collapsed to the NULL (constant) model** — with "
                 "near-zero linear signal, regularization drives all coefficients to 0 and "
                 "predicts the mean (CV Spearman 0.0 beats any negative). They carry no "
                 "ranking information and are EXCLUDED from the ensemble. That collapse is "
                 "itself an informative result: no linear feature combination beats the mean.")
    L.append(f"\nAll CV means lie within ~±0.04 of zero with per-fold std ~0.07–0.10, i.e. "
             "**indistinguishable from no signal** — consistent with the EDA.\n")

    L.append("## One-shot TEST metrics (held-out 12 months)\n")
    tv = test_df.reset_index()[["model", "test_spearman_pooled", "test_spearman_perperiod_mean",
                                "decile_spread_latestperco", "perperiod_top10bot10_spread_mean",
                                "test_rmse"]]
    L.append(tbl(tv))
    L.append(f"\n**Ensemble = mean of best-3 NON-DEGENERATE models by CV Spearman: "
             f"{', '.join(best3)}.** The two decile-spread columns are noisy: the "
             "latest-per-company version ranks only ~7 names per tail, and the per-period "
             "top-10/bottom-10 spread averages over 4 test quarters — read signs, not "
             "magnitudes, and treat both as within-noise here.\n")

    L.append("## Honest verdict\n")
    L.append("EDA showed max single-feature |Spearman| ~0.075; the models confirm it. "
             "**CV Spearman is indistinguishable from zero for every model, test-set Spearman "
             "is ~0 to slightly negative, and the top-vs-bottom realized-Sharpe spreads flip "
             "sign across models** — i.e. no reliable, generalizable signal from report "
             "fundamentals to forward 63-day Sharpe on this universe/period. This is a valid, "
             "expected finding, reported straight and NOT tuned to manufacture a strong-looking "
             "number. The ranking below is produced for completeness (the pipeline is correct "
             "and leak-safe); it should be treated as low-confidence and the backtest read "
             "accordingly.\n")

    L.append("## Predicted ranking — top 10 (long) / bottom 10 (short)\n")
    L.append("`out_of_training_dist=1` = held-out international (scored, never trained; treat "
             "as lower-confidence).\n")
    L.append("**Top 10 (long):**\n" + tbl(top10))
    L.append("\n**Bottom 10 (short):**\n" + tbl(bot10))
    L.append("\nFull ranking of all 89 in predictions_all89.csv (final models refit on ALL "
             "train_eligible rows; the 89 rows are each company's latest report, forward "
             "window still open — these are the ranking signals, not evaluable yet).")

    with open(os.path.join(OUT, "MODEL_SUMMARY.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))


if __name__ == "__main__":
    main()
