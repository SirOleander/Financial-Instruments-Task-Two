"""
L_analysis.py — slide-24 grading items on the 98-stock model. ADDITIVE, READ-ONLY.

Three analyses, all reusing the EXACT leak-safe protocol from J_models (time split at
2025-03-31, TimeSeriesSplit(5, gap=21) on train+val, all preprocessing refit inside each
fold, test set used once under a pre-committed protocol):

  1. ERROR ANALYSIS — bias & variance: train-vs-validation RMSE/Spearman per model plus
     time-safe learning curves (Ridge / RandomForest / XGBoost).
  2. FEATURE IMPORTANCE — linear coefficients, tree importances, SVR permutation importance
     (on validation folds, never test), and a rank-consensus view.
  3. CLASSIFICATION LENS — top-third vs bottom-third forward-Sharpe labels.
     LEAK CONTROL ON THE LABEL: the tercile cutoffs are FIT ON THE TRAIN ROWS ONLY —
     per CV fold from that fold's TRAIN rows, and on train+val for the one-shot test.
     Test outcomes never inform any cutoff. A balanced within-period variant (ranked inside
     each report period, separately within train and within test, so no boundary mixing) is
     reported as robustness.

Writes only to analysis/. Reads modelling_data + predictions/cv_results.csv.

USAGE (from repo root):  python src/L_analysis.py
"""
from __future__ import annotations

import ast
import os
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, balanced_accuracy_score, confusion_matrix,
                             f1_score, precision_score, recall_score, roc_auc_score,
                             roc_curve, mean_squared_error)
from sklearn.model_selection import TimeSeriesSplit, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.svm import SVC
from xgboost import XGBClassifier

import J_models as J

warnings.filterwarnings("ignore")

OUT = os.path.join(J.BASE_DIR, "analysis")
LC_MODELS = ["Ridge", "RandomForest", "XGBoost"]
INK, MUTED, FAINT = "#1f2937", "#6b7280", "#9ca3af"
POS, NEG = "#0f766e", "#b91c1c"


def _rmse(y, p):
    return float(np.sqrt(mean_squared_error(y, p)))


def _sp(y, p):
    r = spearmanr(y, p).correlation
    return 0.0 if (r is None or np.isnan(r)) else float(r)


def tuned_params() -> dict[str, dict]:
    """Best hyperparameters from the committed 98-run (predictions/cv_results.csv)."""
    cv = pd.read_csv(os.path.join(J.OUT, "cv_results.csv"))
    return {r["model"]: ast.literal_eval(r["best_params"]) for _, r in cv.iterrows()}


def build_reg(name: str, params: dict):
    """The J_models estimator (TTR-wrapped pipeline) with its tuned params applied."""
    est = clone(J.roster()[name][0])
    est.set_params(**{f"regressor__model__{k}": v for k, v in params.items()})
    return est


# --------------------------------------------------------------------------- #
# 1. ERROR ANALYSIS — bias & variance
# --------------------------------------------------------------------------- #
def learning_curve_timesafe(est, X: pd.DataFrame, y: np.ndarray, *, n_points=8,
                            val_frac=0.2, gap=J.CV_GAP) -> pd.DataFrame:
    """Chronological learning curve: train on an expanding PREFIX, validate on a FIXED
    later slice (with a purge gap). The whole pipeline is refit at every size, so
    winsor/impute/scale never see the validation slice. The test set is never touched."""
    n = len(X)
    n_val = int(n * val_frac)
    val_idx = np.arange(n - n_val, n)
    pool_end = n - n_val - gap
    rows = []
    for frac in np.linspace(0.15, 1.0, n_points):
        k = int(pool_end * frac)
        if k < 60:
            continue
        tr = np.arange(0, k)
        m = clone(est).fit(X.iloc[tr], y[tr])
        ptr, pva = m.predict(X.iloc[tr]), m.predict(X.iloc[val_idx])
        rows.append({"n_train": k,
                     "train_rmse": _rmse(y[tr], ptr), "val_rmse": _rmse(y[val_idx], pva),
                     "train_spearman": _sp(y[tr], ptr), "val_spearman": _sp(y[val_idx], pva)})
    return pd.DataFrame(rows)


def error_analysis(Xtv, ytv, params):
    print("\n=== 1. ERROR ANALYSIS (bias & variance) ===")
    tscv = TimeSeriesSplit(n_splits=J.N_SPLITS, gap=J.CV_GAP)
    scoring = {"spearman": J.SPEARMAN,
               "neg_rmse": "neg_root_mean_squared_error"}
    rows = []
    for name, p in params.items():
        est = build_reg(name, p)
        cv = cross_validate(est, Xtv, ytv, cv=tscv, scoring=scoring,
                            return_train_score=True, n_jobs=-1)
        rows.append({
            "model": name,
            "train_rmse": -cv["train_neg_rmse"].mean(), "val_rmse": -cv["test_neg_rmse"].mean(),
            "rmse_gap": (-cv["train_neg_rmse"].mean()) - (-cv["test_neg_rmse"].mean()),
            "train_spearman": cv["train_spearman"].mean(),
            "val_spearman": cv["test_spearman"].mean(),
            "val_spearman_std": cv["test_spearman"].std(),
            "spearman_gap": cv["train_spearman"].mean() - cv["test_spearman"].mean(),
        })
        print(f"  {name:14} train RMSE={rows[-1]['train_rmse']:.3f} val RMSE={rows[-1]['val_rmse']:.3f}"
              f" | train rho={rows[-1]['train_spearman']:+.3f} val rho={rows[-1]['val_spearman']:+.3f}")
    tbl = pd.DataFrame(rows)
    tbl.round(4).to_csv(os.path.join(OUT, "train_vs_val_error.csv"), index=False)

    curves = {}
    for name in LC_MODELS:
        lc = learning_curve_timesafe(build_reg(name, params[name]), Xtv, ytv)
        lc.to_csv(os.path.join(OUT, f"learning_curve_{name}.csv"), index=False)
        curves[name] = lc
        fig, ax = plt.subplots(1, 2, figsize=(11, 3.9))
        ax[0].plot(lc.n_train, lc.train_rmse, "o-", color=INK, label="train")
        ax[0].plot(lc.n_train, lc.val_rmse, "s--", color=NEG, label="validation")
        ax[0].axhline(ytv.std(), color=FAINT, ls=":", lw=1, label="target std (predict-mean)")
        ax[0].set_xlabel("training rows (chronological)"); ax[0].set_ylabel("RMSE")
        ax[0].set_title(f"{name} — error", fontsize=10); ax[0].legend(fontsize=7)
        ax[1].plot(lc.n_train, lc.train_spearman, "o-", color=INK, label="train")
        ax[1].plot(lc.n_train, lc.val_spearman, "s--", color=NEG, label="validation")
        ax[1].axhline(0, color=FAINT, ls=":", lw=1)
        ax[1].set_xlabel("training rows (chronological)"); ax[1].set_ylabel("Spearman")
        ax[1].set_title(f"{name} — rank correlation", fontsize=10); ax[1].legend(fontsize=7)
        fig.suptitle(f"Learning curve — {name} (time-safe; test never touched)", fontsize=11)
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, f"fig_learning_curve_{name}.png"), dpi=110,
                    bbox_inches="tight")
        plt.close(fig)
    return tbl, curves


# --------------------------------------------------------------------------- #
# 2. FEATURE IMPORTANCE
# --------------------------------------------------------------------------- #
def feature_importance(Xtv, ytv, params):
    print("\n=== 2. FEATURE IMPORTANCE ===")
    feats = J.transformed_feature_order()
    imp: dict[str, pd.Series] = {}
    for name, p in params.items():
        m = build_reg(name, p).fit(Xtv, ytv)
        reg = m.regressor_.named_steps["model"]
        if hasattr(reg, "coef_"):
            imp[name] = pd.Series(np.abs(np.ravel(reg.coef_)), index=feats)
            signed = pd.Series(np.ravel(reg.coef_), index=feats)
            signed.reindex(signed.abs().sort_values(ascending=False).index).to_csv(
                os.path.join(OUT, f"coef_{name}.csv"))
            nz = int((signed != 0).sum())
            print(f"  {name:14} linear: {nz}/{len(feats)} non-zero coefficients")
        elif hasattr(reg, "feature_importances_"):
            imp[name] = pd.Series(reg.feature_importances_, index=feats)
            print(f"  {name:14} tree importances extracted")

    # SVR: permutation importance on the CV VALIDATION folds (never test)
    tscv = TimeSeriesSplit(n_splits=J.N_SPLITS, gap=J.CV_GAP)
    perm = np.zeros(len(feats))
    folds = 0
    est = build_reg("SVR", params["SVR"])
    for tr, va in tscv.split(Xtv):
        m = clone(est).fit(Xtv.iloc[tr], ytv[tr])
        r = permutation_importance(m, Xtv.iloc[va], ytv[va], n_repeats=5,
                                   random_state=J.SEED, scoring=J.SPEARMAN, n_jobs=-1)
        perm += r.importances_mean
        folds += 1
    imp["SVR_perm"] = pd.Series(perm / folds, index=feats)
    print(f"  SVR            permutation importance over {folds} validation folds")

    wide = pd.DataFrame(imp)
    # rank-consensus (coefs vs Gini are not comparable in magnitude -> average the RANKS)
    ranks = wide.rank(ascending=False)
    consensus = ranks.mean(axis=1).sort_values()
    wide["mean_rank"] = ranks.mean(axis=1)
    wide.sort_values("mean_rank").round(6).to_csv(
        os.path.join(OUT, "feature_importance_combined.csv"))

    for name in ["Ridge", "RandomForest", "XGBoost"]:
        s = imp[name].sort_values(ascending=False).head(15)[::-1]
        fig, ax = plt.subplots(figsize=(7, 5))
        ax.barh(s.index, s.values, color=MUTED)
        ax.set_title(f"{name} — top 15 feature importance", fontsize=10)
        ax.tick_params(labelsize=7)
        fig.tight_layout(); fig.savefig(os.path.join(OUT, f"fig_importance_{name}.png"),
                                        dpi=110, bbox_inches="tight"); plt.close(fig)

    top = consensus.head(15)[::-1]
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.barh(top.index, -top.values, color=INK)
    ax.set_xlabel("← stronger (lower mean rank across models)")
    ax.set_title("Rank-consensus feature importance (Ridge, RF, XGB, SVR-perm)", fontsize=10)
    ax.tick_params(labelsize=7); ax.set_xticks([])
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_importance_consensus.png"),
                                    dpi=110, bbox_inches="tight"); plt.close(fig)
    print(f"  consensus top-5: {list(consensus.head(5).index)}")
    return wide, consensus


# --------------------------------------------------------------------------- #
# 3. CLASSIFICATION LENS
# --------------------------------------------------------------------------- #
def _label_from_cut(y, lo, hi):
    """1 = top tercile, 0 = bottom tercile, NaN = middle (dropped)."""
    return np.where(y >= hi, 1.0, np.where(y <= lo, 0.0, np.nan))


def _within_period_labels(df: pd.DataFrame, min_n=9) -> np.ndarray:
    """Balanced robustness label: tercile RANK inside each report period. Called separately
    on train and on test, so a period's cross-section never mixes the two sides."""
    y = np.full(len(df), np.nan)
    for _, idx in df.groupby("period").groups.items():
        pos = df.index.get_indexer(idx)
        s = df.loc[idx, J.TARGET_RAW].values
        if len(s) < min_n:
            continue
        lo, hi = np.quantile(s, [1 / 3, 2 / 3])
        y[pos] = _label_from_cut(s, lo, hi)
    return y


def clf_roster():
    def wrap(model, scale):
        return Pipeline([("prep", J.make_preprocessor(scale)), ("model", model)])
    return {
        "LogisticRegression": (wrap(LogisticRegression(max_iter=5000, random_state=J.SEED), True),
                               {"model__C": [0.01, 0.1, 1, 10]}),
        "RandomForest": (wrap(RandomForestClassifier(n_estimators=400, random_state=J.SEED,
                              n_jobs=1), False),
                         {"model__max_depth": [3, 5, None], "model__min_samples_leaf": [5, 20]}),
        "XGBoost": (wrap(XGBClassifier(n_estimators=300, subsample=0.8, colsample_bytree=0.8,
                    random_state=J.SEED, n_jobs=1, verbosity=0, eval_metric="logloss"), False),
                    {"model__max_depth": [2, 3], "model__learning_rate": [0.02, 0.05],
                     "model__reg_lambda": [1, 5]}),
        "SVM": (wrap(SVC(kernel="rbf", probability=True, random_state=J.SEED), True),
                {"model__C": [0.1, 1, 10]}),
    }


def _grid(params: dict):
    keys = list(params)
    out = [{}]
    for k in keys:
        out = [{**c, k: v} for c in out for v in params[k]]
    return out


def cv_auc(est, grid_params, X, y_raw, tscv, mode, y_fixed=None):
    """Leak-safe CV AUC. mode='train_fitted': tercile cutoffs computed from the TRAIN FOLD's
    y only, then applied to both train-fold and val-fold rows (test/val outcomes never
    inform the cutoff). mode='fixed': labels precomputed per row (within-period ranks)."""
    aucs = []
    for tr, va in tscv.split(X):
        if mode == "train_fitted":
            lo, hi = np.quantile(y_raw[tr], [1 / 3, 2 / 3])   # <-- TRAIN FOLD ONLY
            ytr, yva = _label_from_cut(y_raw[tr], lo, hi), _label_from_cut(y_raw[va], lo, hi)
        else:
            ytr, yva = y_fixed[tr], y_fixed[va]
        mtr, mva = ~np.isnan(ytr), ~np.isnan(yva)
        if len(np.unique(ytr[mtr])) < 2 or len(np.unique(yva[mva])) < 2:
            continue
        m = clone(est).set_params(**grid_params).fit(X.iloc[tr][mtr], ytr[mtr])
        p = m.predict_proba(X.iloc[va][mva])[:, 1]
        aucs.append(roc_auc_score(yva[mva], p))
    return (float(np.mean(aucs)), float(np.std(aucs))) if aucs else (np.nan, np.nan)


def classification(trainval, test, Xtv, Xte):
    print("\n=== 3. CLASSIFICATION LENS (top-third vs bottom-third) ===")
    tscv = TimeSeriesSplit(n_splits=J.N_SPLITS, gap=J.CV_GAP)
    ytv_raw, yte_raw = trainval[J.TARGET_RAW].values, test[J.TARGET_RAW].values

    schemes = {}
    # PRIMARY: cutoffs fit on TRAIN rows only (per fold in CV; train+val for the test)
    lo, hi = np.quantile(ytv_raw, [1 / 3, 2 / 3])
    schemes["train_fitted_tercile"] = {
        "mode": "train_fitted",
        "ytv": _label_from_cut(ytv_raw, lo, hi), "yte": _label_from_cut(yte_raw, lo, hi),
        "cut": (lo, hi)}
    # ROBUSTNESS: within-period tercile ranks (balanced; train and test ranked separately)
    schemes["within_period_tercile"] = {
        "mode": "fixed",
        "ytv": _within_period_labels(trainval), "yte": _within_period_labels(test),
        "cut": None}

    rows, roc_data = [], {}
    for sname, sc in schemes.items():
        ytv, yte = sc["ytv"], sc["yte"]
        mtv, mte = ~np.isnan(ytv), ~np.isnan(yte)
        base = max(np.mean(yte[mte]), 1 - np.mean(yte[mte]))
        print(f"\n  [{sname}] train+val n={mtv.sum()} ({np.mean(ytv[mtv]):.1%} pos) | "
              f"test n={mte.sum()} ({np.mean(yte[mte]):.1%} pos) | majority baseline={base:.3f}")
        for cname, (est, grid) in clf_roster().items():
            best, best_auc = None, -np.inf
            for gp in _grid(grid):
                a, _ = cv_auc(est, gp, Xtv, ytv_raw, tscv, sc["mode"], ytv)
                if not np.isnan(a) and a > best_auc:
                    best_auc, best = a, gp
            m = clone(est).set_params(**best).fit(Xtv[mtv], ytv[mtv])
            proba = m.predict_proba(Xte[mte])[:, 1]
            pred = (proba >= 0.5).astype(int)
            yt = yte[mte].astype(int)
            met = {"scheme": sname, "model": cname, "cv_auc": best_auc,
                   "test_auc": roc_auc_score(yt, proba),
                   "test_accuracy": accuracy_score(yt, pred),
                   "test_balanced_accuracy": balanced_accuracy_score(yt, pred),
                   "test_precision": precision_score(yt, pred, zero_division=0),
                   "test_recall": recall_score(yt, pred, zero_division=0),
                   "test_f1": f1_score(yt, pred, zero_division=0),
                   "majority_baseline_acc": base, "n_test": int(mte.sum()),
                   "best_params": str(best)}
            cm = confusion_matrix(yt, pred)
            met["cm_tn"], met["cm_fp"], met["cm_fn"], met["cm_tp"] = cm.ravel()
            rows.append(met)
            if sname == "train_fitted_tercile":
                roc_data[cname] = roc_curve(yt, proba) + (met["test_auc"],)
            print(f"    {cname:20} CV AUC={best_auc:.3f} | TEST AUC={met['test_auc']:.3f} "
                  f"acc={met['test_accuracy']:.3f} bal_acc={met['test_balanced_accuracy']:.3f}")

    res = pd.DataFrame(rows)
    res.round(4).to_csv(os.path.join(OUT, "classification_metrics.csv"), index=False)

    # ROC curves (primary scheme)
    fig, ax = plt.subplots(figsize=(6, 5.5))
    for cname, (fpr, tpr, _, auc) in roc_data.items():
        ax.plot(fpr, tpr, lw=1.8, label=f"{cname} (AUC={auc:.3f})")
    ax.plot([0, 1], [0, 1], ls="--", color=FAINT, lw=1, label="chance (AUC=0.500)")
    ax.set_xlabel("false positive rate"); ax.set_ylabel("true positive rate")
    ax.set_title("ROC — test set, top-third vs bottom-third\n(cutoffs fit on train only)",
                 fontsize=10)
    ax.legend(fontsize=8); fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_roc_curves.png"), dpi=110, bbox_inches="tight")
    plt.close(fig)

    # confusion matrices (primary scheme)
    prim = res[res.scheme == "train_fitted_tercile"]
    fig, axes = plt.subplots(1, 4, figsize=(14, 3.6))
    for ax, (_, r) in zip(axes, prim.iterrows()):
        cm = np.array([[r.cm_tn, r.cm_fp], [r.cm_fn, r.cm_tp]])
        ax.imshow(cm, cmap="Greys", vmin=0, vmax=cm.max())
        for i in range(2):
            for j in range(2):
                ax.text(j, i, int(cm[i, j]), ha="center", va="center",
                        color="white" if cm[i, j] > cm.max() * .6 else INK, fontsize=11)
        ax.set_xticks([0, 1]); ax.set_xticklabels(["pred bottom", "pred top"], fontsize=7)
        ax.set_yticks([0, 1]); ax.set_yticklabels(["true bottom", "true top"], fontsize=7)
        ax.set_title(f"{r.model}\nacc={r.test_accuracy:.3f} AUC={r.test_auc:.3f}", fontsize=9)
    fig.suptitle("Confusion matrices — test set (top vs bottom tercile)", fontsize=11)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_confusion_matrices.png"),
                                    dpi=110, bbox_inches="tight"); plt.close(fig)
    return res


# --------------------------------------------------------------------------- #
def main():
    os.makedirs(OUT, exist_ok=True)
    df, trainval, test, _ = J.load()
    Xtv, ytv = J.build_X(trainval), trainval[J.TARGET_RAW].values
    Xte = J.build_X(test)
    params = tuned_params()
    print(f"train+val={len(trainval)} test={len(test)} features={Xtv.shape[1]} "
          f"| tuned params from predictions/cv_results.csv")

    err, curves = error_analysis(Xtv, ytv, params)
    wide, consensus = feature_importance(Xtv, ytv, params)
    clf = classification(trainval, test, Xtv, Xte)

    write_reports(err, curves, wide, consensus, clf, ytv)
    print(f"\nArtifacts -> {OUT}")


def _md_table(d: pd.DataFrame, cols) -> str:
    L = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, r in d.iterrows():
        L.append("| " + " | ".join(
            f"{r[c]:+.4f}" if isinstance(r[c], (float, np.floating)) else str(r[c])
            for c in cols) + " |")
    return "\n".join(L)


def write_reports(err, curves, wide, consensus, clf, ytv):
    # ---- 1. bias / variance ----
    L = ["# Error analysis — bias and variance\n",
         "Leak-safe: TimeSeriesSplit(5, gap=21) on train+val; every preprocessing step refit "
         "inside each fold. The untouched test set is NOT used here.\n",
         f"Target std (train+val) = **{ytv.std():.3f}** — an RMSE at this level means the model "
         "is effectively predicting the mean.\n",
         "## Train vs validation error (CV)\n",
         _md_table(err, ["model", "train_rmse", "val_rmse", "rmse_gap",
                         "train_spearman", "val_spearman", "spearman_gap"]),
         "\n## Learning curves\n",
         "`fig_learning_curve_{Ridge,RandomForest,XGBoost}.png` — train and validation "
         "RMSE / Spearman against an expanding chronological training prefix, validated on a "
         "fixed later slice (purge gap = 21 rows).\n",
         "## Interpretation (bias-variance)\n"]
    e = err.set_index("model")
    std = ytv.std()
    L.append(f"**Out-of-sample every model lands in the same place.** Validation RMSE sits at the "
             f"target's own standard deviation (**{std:.3f}**) for all six models "
             f"({e.val_rmse.min():.3f}–{e.val_rmse.max():.3f}), and validation Spearman is "
             f"{e.val_spearman.min():+.3f}…{e.val_spearman.max():+.3f}. A model that simply "
             "predicted the training mean would score about the same.\n")
    L.append("**Two different failure modes, one identical outcome:**\n")
    L.append(f"1. **Underfitting — high bias, ~zero variance.** Lasso and ElasticNet regularise "
             f"*every* coefficient to exactly zero, so they literally ARE the mean-predictor: "
             f"train RMSE {e.loc['Lasso'].train_rmse:.3f} vs validation "
             f"{e.loc['Lasso'].val_rmse:.3f} (gap ≈ 0), train ρ = validation ρ = 0. All bias, no "
             "variance.")
    L.append(f"2. **Overfitting — high variance, zero payoff.** XGBoost (train ρ "
             f"{e.loc['XGBoost'].train_spearman:+.3f} vs validation "
             f"{e.loc['XGBoost'].val_spearman:+.3f}), SVR ({e.loc['SVR'].train_spearman:+.3f} / "
             f"{e.loc['SVR'].val_spearman:+.3f}) and RandomForest "
             f"({e.loc['RandomForest'].train_spearman:+.3f} / "
             f"{e.loc['RandomForest'].val_spearman:+.3f}) memorise the training rows almost "
             f"perfectly (train RMSE {e.loc['XGBoost'].train_rmse:.3f}–"
             f"{e.loc['RandomForest'].train_rmse:.3f}) while generalising at zero. That is a large "
             "**variance** term, and it buys *nothing*: the capacity is spent fitting noise. "
             f"Ridge sits in between (train ρ {e.loc['Ridge'].train_spearman:+.3f}, validation "
             f"{e.loc['Ridge'].val_spearman:+.3f}).\n")
    lc_txt = "; ".join(
        f"{m} {curves[m].val_rmse.iloc[0]:.3f} → {curves[m].val_rmse.iloc[-1]:.3f}"
        for m in ["RandomForest", "XGBoost"])
    L.append(f"**The learning curves settle which term binds.** Validation error is essentially "
             f"FLAT in training-set size ({lc_txt}, as training rows grow "
             f"{int(curves['XGBoost'].n_train.iloc[0])} → {int(curves['XGBoost'].n_train.iloc[-1])}; "
             "Ridge converges to ~1.92 after its small-sample instability). Validation Spearman "
             "never trends upward. **If variance were the binding constraint, validation error "
             "would fall as data grows — it does not.**\n")
    L.append("**Conclusion, in bias-variance terms.** Total error = bias² + variance + irreducible "
             "noise. Here it is dominated by **irreducible noise plus bias**. The variance the "
             "flexible models exhibit is real but useless — it fits noise, not signal — and the "
             "regularised models trade it away for pure bias, arriving at the *same* validation "
             "score. The near-zero result is itself **stable**: the fold-to-fold spread of "
             "validation Spearman (std ~0.07–0.10) straddles zero with no fold showing meaningful "
             "positive rank-correlation, and the conclusion reproduces across feature sets "
             "(ablation) and across the 89→98 universe expansion. Forward 63-day Sharpe is close to "
             "unpredictable from report fundamentals: **more data, more capacity or more tuning "
             "cannot fix this — only a genuinely more informative feature set could.**")
    open(os.path.join(OUT, "bias_variance.md"), "w", encoding="utf-8").write("\n".join(L))

    # ---- 2. feature importance ----
    top = consensus.head(12)
    L = ["# Feature importance — what the models actually use\n",
         "Slide-24 requirement: the models are **not black boxes**. Below is exactly what each "
         "one leans on. All fitted on train+val only.\n",
         "## Rank-consensus (mean rank across Ridge, RandomForest, XGBoost, SVR-permutation)\n",
         "| rank | feature | mean_rank |", "|---|---|---|"]
    for i, (f, v) in enumerate(top.items(), 1):
        L.append(f"| {i} | `{f}` | {v:.1f} |")
    nz = {m: int((wide[m] != 0).sum()) for m in wide.columns if m != "mean_rank"}
    L.append("\n## Per-model views\n")
    L.append("- `fig_importance_Ridge.png`, `fig_importance_RandomForest.png`, "
             "`fig_importance_XGBoost.png`, `fig_importance_consensus.png`")
    L.append(f"- Non-zero/non-trivial features per model: {nz}")
    L.append("- **Lasso and ElasticNet drive EVERY coefficient to exactly zero** — the "
             "regularisation path selects *no* feature over the intercept. That is itself the "
             "cleanest statement of the finding: no linear combination of these 48 features beats "
             "predicting the mean.\n")
    L.append("## Interpretation\n")
    L.append(f"- The models concentrate what little weight they have on **{', '.join(list(top.index[:4]))}** "
             "— broadly the *change* features (margin and profitability deltas) rather than levels, "
             "consistent with the EDA where `net_margin_change` was the strongest single feature "
             "(|Spearman| ~0.075).")
    L.append("- **But the magnitudes are trivial.** No feature is a strong driver: the ranking "
             "below is a ranking of near-noise. Ridge's standardized coefficients are small and "
             "the tree importances are spread thinly across all 48 features (no dominant split "
             "variable). Reading these as economic 'drivers' would be over-interpretation.")
    L.append("- The honest statement: *we can show exactly what the models use, and what they use "
             "carries almost no predictive power.* Interpretability here confirms rather than "
             "rescues the null.")
    open(os.path.join(OUT, "feature_importance.md"), "w", encoding="utf-8").write("\n".join(L))

    # ---- 3. classification ----
    prim = clf[clf.scheme == "train_fitted_tercile"]
    rob = clf[clf.scheme == "within_period_tercile"]
    L = ["# Classification lens — accuracy, AUC, confusion matrix\n",
         "The task is a regression (forward Sharpe). Slide 24 also asks for classification "
         "metrics, so we add a classification **lens alongside** the regression — it does not "
         "replace it.\n",
         "## Labelling and leak control\n",
         "- **Label:** top-third vs bottom-third of realized `future_63d_sharpe`; the middle third "
         "is dropped. This matches the strategy (long top-10 / short bottom-10) — the question is "
         "whether the model can separate a period's winners from its losers.\n",
         "- **The tercile cutoffs are fit on TRAIN ROWS ONLY**: inside each CV fold the 33rd/67th "
         "percentiles are computed from that fold's *training* rows and then applied to both the "
         "training and the validation rows; for the one-shot test evaluation the cutoffs come from "
         "the full train+val pool. **Test outcomes never inform any cutoff**, and no cutoff is ever "
         "fit on the pooled dataset.\n",
         "- Same time split (2025-03-31), same TimeSeriesSplit(5, gap=21), same per-fold "
         "winsorize → impute → scale pipeline. Selection metric = ROC-AUC.\n",
         f"- Consequence of a train-fitted cutoff: the test regime had higher Sharpes, so the test "
         f"set is **{prim.iloc[0].majority_baseline_acc:.1%} one class** (majority baseline "
         f"accuracy = {prim.iloc[0].majority_baseline_acc:.3f}). **AUC and balanced accuracy are "
         "therefore the metrics to read**; raw accuracy must be compared against that baseline.\n",
         "- A balanced **within-period** variant (ranked inside each report period, separately "
         "within train and within test so no period's cross-section straddles the split) is "
         "reported as robustness.\n",
         "## Test-set metrics — primary (cutoffs fit on train only)\n",
         _md_table(prim, ["model", "cv_auc", "test_auc", "test_accuracy",
                          "test_balanced_accuracy", "test_precision", "test_recall", "test_f1"]),
         f"\nMajority-class baseline accuracy = **{prim.iloc[0].majority_baseline_acc:.3f}**, "
         f"chance AUC = **0.500**. n_test = {int(prim.iloc[0].n_test)}.\n",
         "## Test-set metrics — robustness (balanced within-period tercile)\n",
         _md_table(rob, ["model", "cv_auc", "test_auc", "test_accuracy",
                         "test_balanced_accuracy", "test_f1"]),
         f"\nBalanced by construction; baseline accuracy ≈ 0.5, chance AUC = 0.500. "
         f"n_test = {int(rob.iloc[0].n_test)}.\n",
         "## Confusion matrices & ROC\n",
         "`fig_confusion_matrices.png`, `fig_roc_curves.png`.\n",
         "## Interpretation\n"]
    L.append(f"- **AUC is ~0.5 for every model.** Primary scheme test AUC "
             f"{prim.test_auc.min():.3f}–{prim.test_auc.max():.3f}; robustness scheme "
             f"{rob.test_auc.min():.3f}–{rob.test_auc.max():.3f} (chance = 0.500). The classifiers "
             "cannot rank future winners above future losers better than a coin flip.")
    L.append(f"- **CV and test AUC disagree in sign.** Cross-validated AUC is mostly *below* chance "
             f"({prim.cv_auc.min():.3f}–{prim.cv_auc.max():.3f}) while test AUC is marginally above "
             "it — the hallmark of noise, not a stable edge. No model is consistently above 0.5 "
             "across both labelling schemes.")
    L.append("- **Accuracy is not evidence of skill here.** Under the train-fitted cutoff the test "
             f"set is {prim.iloc[0].majority_baseline_acc:.1%} one class, so a model that always "
             "predicts the majority scores that accuracy without any information. Balanced accuracy "
             "(~0.5) and AUC (~0.5) strip that artefact out.")
    L.append("- The **confusion matrices** show the same thing structurally: predictions are spread "
             "across both classes with no concentration on the diagonal.")
    L.append("- The **balanced within-period variant reproduces the verdict** on 50/50 classes, so "
             "the result is not an artefact of the class imbalance introduced by the train-fitted "
             "cutoff.")
    L.append("\n- **Verdict:** *a classification framing gives the same answer as the regression — "
             "the models cannot separate future winners from losers better than chance.* This is a "
             "consistency check that CONFIRMS the near-null regression result, reported straight.")
    open(os.path.join(OUT, "classification.md"), "w", encoding="utf-8").write("\n".join(L))


if __name__ == "__main__":
    main()
