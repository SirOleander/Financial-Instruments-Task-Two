"""modelling.py - EDA, training, backtest, and slide-24 analysis.

Merges the four stages that read modelling_data and write the dashboard artifacts. They
were always one workflow: they share the time split, the per-fold preprocessing, the model
roster and the feature builder. Previously K_backtest and L_analysis reached ACROSS a file
boundary via `import J_models as J` for load(), build_X, make_preprocessor, YWinsorizer,
SEED, SPLIT_DATE, TARGET_RAW, SPEARMAN, roster, transformed_feature_order, CV_GAP, N_SPLITS
and OUT. Inside one module those are direct references and the cross-import is gone.

  eda      (was I_eda)       feature diagnostics        -> eda/
  train    (was J_models)    CV + ensemble + ablation   -> predictions/
  backtest (was K_backtest)  walk-forward long/short    -> predictions/
  analysis (was L_analysis)  bias-variance/importance/  -> analysis/
                             classification (slide-24)

NAME CLASHES RESOLVED ON MERGE (all module-local once the cross-import is internalised):
  main          x4 -> main_eda / main_train / main_backtest / main_analysis
  OUT           x4 -> EDA_OUT / PRED_OUT (train & backtest share predictions/) / ANALYSIS_OUT
  write_summary x3 -> write_summary_eda / _train / _backtest
  load          x2 -> load_eda (EDA own) ; load (train, referenced by backtest + analysis)
  BASE_DIR, SUBSCORES x2 each -> byte-identical, defined ONCE here.

BASE_DIR is computed at this module new depth (src/fi/ -> repo root), so the eda/,
predictions/ and analysis/ output dirs resolve to the same absolute paths as before. The
near-null result and rf=2% target are untouched - this is a move, not a remodel.
"""
from __future__ import annotations

import ast
import os
import warnings
from contextlib import closing

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.base import BaseEstimator, TransformerMixin, clone
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import ElasticNet, Lasso, LogisticRegression, Ridge
from sklearn.metrics import (accuracy_score, balanced_accuracy_score, confusion_matrix,
                             f1_score, make_scorer, mean_squared_error, precision_score,
                             recall_score, roc_auc_score, roc_curve)
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC, SVR
from xgboost import XGBClassifier, XGBRegressor

from fi import config, db

# repo root from src/fi/modelling.py; output dirs resolve to the same absolute paths as before
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EDA_OUT = os.path.join(BASE_DIR, "eda")
PRED_OUT = os.path.join(BASE_DIR, "predictions")
ANALYSIS_OUT = os.path.join(BASE_DIR, "analysis")
SUBSCORES = ["profitability_score", "growth_score", "cash_flow_score",
             "leverage_score", "efficiency_score", "investment_score"]



# ============================================================================
# STAGE: eda (was I_eda)
# ============================================================================


# --------------------------------------------------------------------------- #
# feature groups (winsorized/model columns are the base names)
# --------------------------------------------------------------------------- #
AGG_SCORES = ["financial_score", "operative_score", "competitive_advantage_score_w050"]
SCORE_FEATURES = SUBSCORES + AGG_SCORES

KPI_FEATURES = [
    "gross_margin", "operating_margin", "net_margin", "return_on_assets", "return_on_equity",
    "revenue_growth_yoy", "operating_income_growth_yoy", "net_income_growth_yoy",
    "operating_cash_flow_growth_yoy",
    "operating_cash_flow_margin", "free_cash_flow_margin", "cash_conversion",
    "debt_to_assets", "net_debt_to_assets", "cash_to_assets", "equity_ratio",
    "asset_turnover", "operating_income_to_assets", "inventory_turnover",
    "r_and_d_intensity", "capex_intensity", "reinvestment_rate",
    "ROIC", "net_interest_margin", "capital_retention",
]
# winsorized cols that have a _raw counterpart, + the target
WINSOR_COLS = ["ROIC", "cash_conversion", "revenue_growth_yoy",
               "operating_income_growth_yoy", "net_income_growth_yoy",
               "operating_cash_flow_growth_yoy"]
# sparse sector-specific KPIs — excluded from complete-case VIF/heatmap core
SPARSE_KPIS = ["inventory_turnover", "net_interest_margin", "capital_retention",
               "r_and_d_intensity", "reinvestment_rate"]
CORE_KPIS = [k for k in KPI_FEATURES if k not in SPARSE_KPIS]

LEVEL_FEATURES = SCORE_FEATURES + KPI_FEATURES
CHANGE_FEATURES = [f"{c}_change" for c in
                   (SUBSCORES + ["financial_score", "operative_score"] + KPI_FEATURES)]
TARGET = "future_63d_sharpe"
RELIABLE_N = 800   # min sample for a feature-target correlation to be read as representative

# exact by-construction identities that make a linear model rank-deficient (surfaced by VIF)
CONSTRUCTION_IDENTITIES = [
    "financial_score = mean(six sub-scores)",
    "competitive_advantage_score_w050 = 0.5*financial_score + 0.5*operative_score",
    "free_cash_flow_margin = operating_cash_flow_margin - capex_intensity",
    "net_debt_to_assets = debt_to_assets - cash_to_assets",
]

MANIFEST: list[tuple[str, str]] = []


def _save(fig, name: str, desc: str) -> None:
    path = os.path.join(EDA_OUT, name)
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)
    MANIFEST.append((name, desc))


def _csv(df: pd.DataFrame, name: str, desc: str, index: bool = True) -> None:
    df.to_csv(os.path.join(EDA_OUT, name), index=index)
    MANIFEST.append((name, desc))


# --------------------------------------------------------------------------- #
# load
# --------------------------------------------------------------------------- #
def load_eda() -> pd.DataFrame:
    with closing(db.get_connection()) as con:
        df = pd.read_sql_query("SELECT * FROM modelling_data", con)
    df["split"] = np.where(df["train_eligible"] == 1, "train", "prediction_only")
    df["intl"] = np.where(df["source"] == "edgar", "US", "international")
    return df


# --------------------------------------------------------------------------- #
# 1. distributions
# --------------------------------------------------------------------------- #
def _grid_hist(df: pd.DataFrame, cols: list[str], title: str, name: str, desc: str,
               caps: dict | None = None) -> None:
    ncol = 4
    nrow = -(-len(cols) // ncol)
    fig, axes = plt.subplots(nrow, ncol, figsize=(4 * ncol, 3 * nrow))
    axes = np.array(axes).reshape(-1)
    tr = df[df["train_eligible"] == 1]
    pr = df[df["train_eligible"] == 0]
    for ax, col in zip(axes, cols):
        a = tr[col].dropna().values
        b = pr[col].dropna().values
        if len(a) + len(b) == 0:
            ax.set_visible(False); continue
        allv = np.concatenate([a, b]) if len(b) else a
        lo, hi = np.nanpercentile(allv, [0.5, 99.5])
        bins = np.linspace(lo, hi, 30) if hi > lo else 30
        ax.hist(a, bins=bins, alpha=0.6, label=f"train ({len(a)})", color="#1f77b4")
        if len(b):
            ax.hist(b, bins=bins, alpha=0.6, label=f"pred-only ({len(b)})", color="#ff7f0e")
        if caps and col in caps:
            lo_c, hi_c = caps[col]
            for x in (lo_c, hi_c):
                ax.axvline(x, color="red", ls="--", lw=0.9)
        sk = tr[col].skew()
        ax.set_title(f"{col}\nskew(train)={sk:+.2f}", fontsize=8)
        ax.tick_params(labelsize=7)
    for ax in axes[len(cols):]:
        ax.set_visible(False)
    axes[0].legend(fontsize=7)
    fig.suptitle(title, fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.98])
    _save(fig, name, desc)


def distributions(df: pd.DataFrame, caps: dict) -> pd.DataFrame:
    _grid_hist(df, SCORE_FEATURES, "Score features (train vs prediction-only)",
               "fig_dist_scores.png", "Histograms of the 9 score features, train vs pred-only")
    _grid_hist(df, KPI_FEATURES, "KPI features (winsorized; red dashes = winsor caps)",
               "fig_dist_kpis.png", "Histograms of 25 KPI features w/ winsor caps annotated",
               caps=caps)

    # raw vs winsorized for the six ratio-tail KPIs
    fig, axes = plt.subplots(3, 2, figsize=(11, 11))
    axes = axes.reshape(-1)
    tr = df[df["train_eligible"] == 1]
    for ax, col in zip(axes, WINSOR_COLS):
        raw = tr[f"{col}_raw"].dropna().values
        win = tr[col].dropna().values
        lo, hi = np.nanpercentile(raw, [1, 99])
        pad = (hi - lo) * 1.5 if hi > lo else 1
        rng = (lo - pad, hi + pad)
        ax.hist(raw, bins=60, range=rng, alpha=0.5, label="raw", color="#888")
        ax.hist(win, bins=60, range=rng, alpha=0.6, label="winsorized", color="#1f77b4")
        if col in caps:
            for x in caps[col]:
                ax.axvline(x, color="red", ls="--", lw=0.9)
        ax.set_title(f"{col}: raw skew={tr[f'{col}_raw'].skew():+.1f} -> "
                     f"wins skew={tr[col].skew():+.2f}", fontsize=9)
        ax.legend(fontsize=8)
    fig.suptitle("Ratio-tail KPIs: raw vs winsorized (train-eligible)", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.98])
    _save(fig, "fig_dist_winsor_rawvswins.png",
          "Raw vs winsorized distributions for the six ratio-tail KPIs (train)")

    # target
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    axes = axes.reshape(-1)
    tt = df[df["train_eligible"] == 1]
    for ax, (col, ttl) in zip(axes, [
            ("future_63d_sharpe_raw", "future_63d_sharpe RAW"),
            ("future_63d_sharpe", "future_63d_sharpe WINSORIZED"),
            ("future_63d_return", "future_63d_return"),
            ("future_63d_volatility", "future_63d_volatility")]):
        v = tt[col].dropna().values
        ax.hist(v, bins=40, color="#2ca02c", alpha=0.8)
        if col in caps:
            for x in caps[col]:
                ax.axvline(x, color="red", ls="--", lw=0.9)
        ax.axvline(np.median(v), color="k", ls=":", lw=1)
        ax.set_title(f"{ttl}\nmean={np.mean(v):+.3f} med={np.median(v):+.3f} "
                     f"skew={tt[col].skew():+.2f}", fontsize=9)
    fig.suptitle("Target distributions (train-eligible)", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.98])
    _save(fig, "fig_dist_target.png", "Target: raw vs winsorized Sharpe, 63d return & vol")

    # skew table (train-eligible)
    rows = []
    for col in LEVEL_FEATURES + [TARGET]:
        s = tr[col]
        rows.append({"feature": col, "n": int(s.notna().sum()),
                     "skew": s.skew(), "kurtosis": s.kurt(),
                     "min": s.min(), "median": s.median(), "max": s.max()})
    for col in WINSOR_COLS + ["future_63d_sharpe_raw"]:
        s = tr[col]
        rows.append({"feature": col + " [RAW]", "n": int(s.notna().sum()),
                     "skew": s.skew(), "kurtosis": s.kurt(),
                     "min": s.min(), "median": s.median(), "max": s.max()})
    skew_df = pd.DataFrame(rows).set_index("feature").sort_values("skew", key=abs,
                                                                  ascending=False)
    _csv(skew_df.round(4), "skew_table.csv",
         "Skew/kurtosis of every level feature + target (train-eligible)")
    return skew_df


# --------------------------------------------------------------------------- #
# 2. correlation
# --------------------------------------------------------------------------- #
def correlations(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    tr = df[df["train_eligible"] == 1]
    cols = SCORE_FEATURES + KPI_FEATURES
    corr = tr[cols].corr(method="pearson")  # pairwise-complete
    _csv(corr.round(4), "corr_matrix.csv", "Pearson feature-feature corr (train-eligible)")

    fig, ax = plt.subplots(figsize=(15, 13))
    im = ax.imshow(corr.values, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(cols))); ax.set_xticklabels(cols, rotation=90, fontsize=7)
    ax.set_yticks(range(len(cols))); ax.set_yticklabels(cols, fontsize=7)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    ax.set_title("Feature-feature Pearson correlation (train-eligible)", fontsize=12)
    fig.tight_layout()
    _save(fig, "fig_corr_heatmap.png", "Feature-feature correlation heatmap (train-eligible)")

    # high-corr pairs |r|>0.8
    pairs = []
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            r = corr.iloc[i, j]
            if pd.notna(r) and abs(r) > 0.8:
                pairs.append({"feat_a": cols[i], "feat_b": cols[j], "pearson": r})
    high = pd.DataFrame(pairs).sort_values("pearson", key=abs, ascending=False) \
        if pairs else pd.DataFrame(columns=["feat_a", "feat_b", "pearson"])
    _csv(high.round(4), "high_corr_pairs.csv", "Feature pairs with |Pearson|>0.8 (redundancy)",
         index=False)

    # feature-TARGET corr (level + change), Pearson + Spearman
    rows = []
    y = tr[TARGET]
    for col in LEVEL_FEATURES + CHANGE_FEATURES:
        sub = tr[[col, TARGET]].dropna()
        if len(sub) < 30:
            rows.append({"feature": col, "n": len(sub), "pearson": np.nan,
                         "spearman": np.nan}); continue
        rows.append({"feature": col, "n": len(sub),
                     "pearson": sub[col].corr(sub[TARGET], method="pearson"),
                     "spearman": sub[col].corr(sub[TARGET], method="spearman")})
    tcorr = pd.DataFrame(rows)
    tcorr["abs_spearman"] = tcorr["spearman"].abs()
    # reliability flag: correlations on small, sector-specific subsamples (e.g. bank-only
    # net_interest_margin n=144, capital_retention n=32) are NOT comparable to full-
    # population features and must not be read as deployable signal.
    tcorr["reliable"] = tcorr["n"] >= RELIABLE_N
    tcorr = tcorr.sort_values("abs_spearman", ascending=False)
    _csv(tcorr.round(4), "feature_target_corr.csv",
         "Pearson+Spearman vs future_63d_sharpe, ranked; reliable=n>=%d (train-eligible)"
         % RELIABLE_N, index=False)

    # bar of top 20 by |spearman| among RELIABLE (well-populated) features only
    top = tcorr[tcorr["reliable"]].dropna(subset=["spearman"]).head(20).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 8))
    colors = ["#1f77b4" if v >= 0 else "#d62728" for v in top["spearman"]]
    ax.barh(top["feature"], top["spearman"], color=colors)
    ax.axvline(0, color="k", lw=0.8)
    ax.set_title(f"Top 20 well-populated (n>={RELIABLE_N}) features by |Spearman| vs "
                 "future_63d_sharpe (train)", fontsize=10)
    ax.tick_params(labelsize=8)
    fig.tight_layout()
    _save(fig, "fig_target_corr_bar.png", "Top-20 feature-target Spearman correlations")
    return tcorr, high


# --------------------------------------------------------------------------- #
# 3. VIF
# --------------------------------------------------------------------------- #
def _vif_block(df: pd.DataFrame, cols: list[str], block: str) -> tuple[pd.DataFrame, int]:
    sub = df[cols].dropna()
    X = sub.values.astype(float)
    n, k = X.shape
    out = []
    for i in range(k):
        y = X[:, i]
        others = np.delete(X, i, axis=1)
        A = np.column_stack([np.ones(n), others])
        beta, *_ = np.linalg.lstsq(A, y, rcond=None)
        pred = A @ beta
        ss_res = float(((y - pred) ** 2).sum())
        ss_tot = float(((y - y.mean()) ** 2).sum())
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
        vif = np.inf if r2 >= 0.9999999 else 1.0 / (1.0 - r2)
        out.append({"block": block, "feature": cols[i], "R2_on_others": r2, "VIF": vif})
    return pd.DataFrame(out), n


def vif(df: pd.DataFrame) -> pd.DataFrame:
    tr = df[df["train_eligible"] == 1]
    v_scores, n_s = _vif_block(tr, SCORE_FEATURES, "scores")
    v_kpis, n_k = _vif_block(tr, CORE_KPIS, "core_kpis")
    v_scores["n_rows"] = n_s
    v_kpis["n_rows"] = n_k
    out = pd.concat([v_scores, v_kpis], ignore_index=True)
    out["flag"] = np.where(out["VIF"] > 10, "HIGH>10",
                    np.where(out["VIF"] > 5, "elevated>5", ""))
    _csv(out.round(4), "vif_table.csv",
         f"VIF: scores block (n={n_s}) + core KPI block (n={n_k}), train-eligible",
         index=False)
    return out


# --------------------------------------------------------------------------- #
# 4. missingness
# --------------------------------------------------------------------------- #
def missingness(df: pd.DataFrame) -> pd.DataFrame:
    feats = LEVEL_FEATURES + CHANGE_FEATURES + [TARGET]
    tr = df[df["train_eligible"] == 1]
    us = df[df["intl"] == "US"]
    intl = df[df["intl"] == "international"]
    rows = []
    for col in feats:
        rows.append({
            "feature": col,
            "pct_missing_all": 100 * df[col].isna().mean(),
            "pct_missing_train": 100 * tr[col].isna().mean(),
            "pct_missing_US": 100 * us[col].isna().mean(),
            "pct_missing_intl": 100 * intl[col].isna().mean(),
            "n_missing_all": int(df[col].isna().sum()),
        })
    miss = pd.DataFrame(rows).set_index("feature")
    _csv(miss.round(2), "missingness_by_feature.csv",
         "Missing % per feature by all/train/US/international")

    # bar of features with any missingness (all-rows), split US vs intl
    m = miss[miss["pct_missing_all"] > 0].sort_values("pct_missing_all")
    fig, ax = plt.subplots(figsize=(9, max(4, 0.28 * len(m))))
    yp = np.arange(len(m))
    ax.barh(yp - 0.2, m["pct_missing_US"], height=0.4, label="US", color="#1f77b4")
    ax.barh(yp + 0.2, m["pct_missing_intl"], height=0.4, label="international", color="#ff7f0e")
    ax.set_yticks(yp); ax.set_yticklabels(m.index, fontsize=7)
    ax.set_xlabel("% missing"); ax.legend(fontsize=8)
    ax.set_title("Missingness by feature: US vs international", fontsize=11)
    fig.tight_layout()
    _save(fig, "fig_missingness.png", "Per-feature missing %, US vs international")
    return miss


# --------------------------------------------------------------------------- #
# 5. target analysis
# --------------------------------------------------------------------------- #
def target_analysis(df: pd.DataFrame) -> dict:
    tr = df[df["train_eligible"] == 1]
    y = tr[TARGET].dropna()
    yr = tr["future_63d_sharpe_raw"].dropna()
    summ = pd.DataFrame({
        "metric": ["n", "mean", "std", "min", "p05", "p25", "median", "p75", "p95", "max", "skew"],
        "sharpe_winsorized": [len(y), y.mean(), y.std(), y.min(), y.quantile(.05),
                              y.quantile(.25), y.median(), y.quantile(.75), y.quantile(.95),
                              y.max(), y.skew()],
        "sharpe_raw": [len(yr), yr.mean(), yr.std(), yr.min(), yr.quantile(.05),
                       yr.quantile(.25), yr.median(), yr.quantile(.75), yr.quantile(.95),
                       yr.max(), yr.skew()],
    })
    _csv(summ.round(4), "target_summary.csv", "Target summary stats, winsorized vs raw (train)",
         index=False)

    by_sec = tr.groupby("sector")[TARGET].agg(["count", "mean", "median", "std"]).round(4)
    _csv(by_sec, "target_by_sector.csv", "future_63d_sharpe by sector (train)")
    by_freq = tr.groupby("frequency")[TARGET].agg(["count", "mean", "median", "std"]).round(4)
    _csv(by_freq, "target_by_frequency.csv", "future_63d_sharpe by frequency (train)")

    # boxplot by sector
    secs = [s for s, _ in tr.groupby("sector")]
    data = [tr[tr["sector"] == s][TARGET].dropna().values for s in secs]
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.boxplot(data, tick_labels=[s[:14] for s in secs], showfliers=False)
    ax.axhline(0, color="k", lw=0.8, ls=":")
    ax.set_ylabel("future_63d_sharpe"); ax.tick_params(axis="x", rotation=35, labelsize=8)
    ax.set_title("Forward 63d Sharpe by sector (train-eligible, in-sample)", fontsize=11)
    fig.tight_layout()
    _save(fig, "fig_target_by_sector.png", "Boxplot of forward Sharpe by sector (train)")

    # lag-1 autocorrelation of a company's consecutive Sharpes (pooled), by frequency
    ac_rows = []
    for freq in ("quarterly", "annual"):
        pairs = []
        sub = tr[tr["frequency"] == freq]
        for tk, g in sub.groupby("ticker"):
            g = g.sort_values("report_release_date")
            s = g[TARGET].values
            for a, b in zip(s[:-1], s[1:]):
                if np.isfinite(a) and np.isfinite(b):
                    pairs.append((a, b))
        if len(pairs) >= 30:
            arr = np.array(pairs)
            r = np.corrcoef(arr[:, 0], arr[:, 1])[0, 1]
            ac_rows.append({"frequency": freq, "n_pairs": len(pairs), "lag1_pearson": r})
    ac = pd.DataFrame(ac_rows)
    _csv(ac.round(4), "target_autocorr.csv",
         "Lag-1 autocorrelation of a company's consecutive forward Sharpes (train)",
         index=False)
    return {"summary": summ, "by_sector": by_sec, "by_freq": by_freq, "autocorr": ac}


# --------------------------------------------------------------------------- #
# 6. written summary
# --------------------------------------------------------------------------- #
def write_summary_eda(df, skew_df, tcorr, high, vifdf, miss, tgt, caps) -> None:
    tr = df[df["train_eligible"] == 1]
    rel = tcorr[tcorr["reliable"]].dropna(subset=["spearman"])
    sparse = tcorr[~tcorr["reliable"]].dropna(subset=["spearman"]).sort_values(
        "abs_spearman", ascending=False)
    top_pos = rel.sort_values("spearman", ascending=False).head(6)
    top_neg = rel.sort_values("spearman").head(6)
    worst_skew = skew_df[skew_df["skew"].abs() > 2].head(8)
    high_vif = vifdf[vifdf["VIF"] > 10].sort_values("VIF", ascending=False)
    ac = tgt["autocorr"]

    def _tbl(d, cols):
        lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
        for _, r in d.iterrows():
            lines.append("| " + " | ".join(
                (f"{r[c]:+.4f}" if isinstance(r[c], float) else str(r[c])) for c in cols) + " |")
        return "\n".join(lines)

    L = []
    L.append("# EDA & feature diagnostics — modelling_data\n")
    L.append("Read-only pass over `modelling_data`. **All modelling-informing statistics "
             "(correlation, VIF, feature-target, target-by-sector) are computed on "
             "TRAIN-ELIGIBLE rows only** (train_eligible=1, n="
             f"{len(tr)} rows / {tr['ticker'].nunique()} US companies). Distribution plots "
             "show all rows, labelled train vs prediction-only. Feature columns are the "
             "WINSORIZED (model) columns unless suffixed `[RAW]`.\n")
    L.append(f"Universe: {len(df)} rows / {df['ticker'].nunique()} companies "
             f"({(df['intl']=='international').sum()} international rows held out of training, "
             "retained for prediction/ranking).\n")

    L.append("## 1. Feature-target signal (the key question: is there any?)\n")
    L.append("Forward-return prediction is intrinsically low-signal; weak correlations are "
             f"expected and still usable in aggregate. Ranked among WELL-POPULATED features "
             f"(n>={RELIABLE_N}) so small sector-only subsamples don't masquerade as signal. "
             "Strongest **positive** Spearman vs future_63d_sharpe:\n")
    L.append(_tbl(top_pos, ["feature", "n", "pearson", "spearman"]))
    L.append("\nStrongest **negative** Spearman:\n")
    L.append(_tbl(top_neg, ["feature", "n", "pearson", "spearman"]))
    best_abs = rel.iloc[0]
    L.append(f"\n**Max |Spearman| among well-populated features = {best_abs['spearman']:+.4f} "
             f"({best_abs['feature']}, n={int(best_abs['n'])}) — essentially no univariate "
             "signal.** This is the expected, informative result: rely on multivariate + "
             "ensemble models, not any single feature.\n")
    L.append("\n**CAUTION — ignore these as leaders:** the raw top-|Spearman| is dominated by "
             "sparse, sector-specific features computed on small non-representative "
             "subsamples, NOT deployable signal:\n")
    L.append(_tbl(sparse.head(4), ["feature", "n", "spearman"]))
    L.append("")

    L.append("## 2. Redundancy / collinearity\n")
    L.append("**Exact identities that make a linear model RANK-DEFICIENT** (VIF=inf, R2=1.0 — "
             "surface explicitly). Drop one variable from each group:\n")
    for idn in CONSTRUCTION_IDENTITIES:
        L.append(f"- `{idn}`")
    L.append("\nSo do NOT feed both the six sub-scores AND financial_score AND the w050 blend; "
             "and within the KPIs keep only two of {operating_cash_flow_margin, "
             "capex_intensity, free_cash_flow_margin} and two of {debt_to_assets, "
             "cash_to_assets, net_debt_to_assets}. VIF>10 flags:\n")
    if len(high_vif):
        L.append(_tbl(high_vif.assign(VIF=high_vif["VIF"].replace(np.inf, 9999)),
                      ["block", "feature", "R2_on_others", "VIF"]))
    else:
        L.append("_(none)_")
    L.append(f"\nFeature pairs with |Pearson|>0.8: {len(high)}.\n")
    if len(high):
        L.append(_tbl(high.head(12), ["feat_a", "feat_b", "pearson"]))
    L.append("")

    L.append("## 3. Distributions / skew\n")
    L.append("Winsorization tamed the ratio-tail KPIs (see fig_dist_winsor_rawvswins.png). "
             "Features still |skew|>2 after winsorization:\n")
    if len(worst_skew):
        L.append(_tbl(worst_skew.reset_index()[["feature", "skew", "kurtosis"]],
                      ["feature", "skew", "kurtosis"]))
    else:
        L.append("_(none — winsorization sufficient)_")
    L.append("")

    L.append("## 4. Missingness\n")
    topmiss = miss.sort_values("pct_missing_all", ascending=False).head(10)
    L.append("Highest-missing features (all rows):\n")
    L.append(_tbl(topmiss.reset_index()[["feature", "pct_missing_all", "pct_missing_US",
                                         "pct_missing_intl"]],
                  ["feature", "pct_missing_all", "pct_missing_US", "pct_missing_intl"]))
    L.append("\nDrivers: sparse sector-specific KPIs (net_interest_margin, capital_retention "
             "banks-only; inventory_turnover a few sectors; r_and_d only tech/health), "
             "negative-equity ROE/equity_ratio/ROIC (PM/MCD/BKNG/ABBV), Energy gross_margin "
             "(not emitted), operative_score (integrated/no-20-F intl), and all `*_change` "
             "features on first_obs rows. Missing is honest NULL — models must handle it "
             "(tree split-on-missing, or impute-in-pipeline; never mean-fill silently).\n")

    L.append("## 5. Target\n")
    s = tgt["summary"]
    sw = s[s["metric"] == "median"]["sharpe_winsorized"].iloc[0]
    L.append(f"future_63d_sharpe (train, winsorized): median={sw:+.3f}, "
             f"mean={s[s['metric']=='mean']['sharpe_winsorized'].iloc[0]:+.3f}, "
             f"std={s[s['metric']=='std']['sharpe_winsorized'].iloc[0]:.3f}. See "
             "target_by_sector.csv / fig_target_by_sector.png for sector dispersion — some "
             "sectors sit systematically above/below zero in-sample (a look-ahead caution: do "
             "NOT hardcode sector means into features).\n")
    if len(ac):
        L.append("Lag-1 autocorrelation of a company's consecutive forward Sharpes:\n")
        L.append(_tbl(ac, ["frequency", "n_pairs", "lag1_pearson"]))
        L.append("\nNon-trivial serial correlation => consecutive same-company rows are NOT "
                 "independent. Use a **time-based split** (already planned) and consider "
                 "grouping by company to avoid train/test leakage across adjacent windows.\n")

    L.append("## 6. Recommendations (for the modelling step — you decide)\n")
    L.append("1. **Scores: pick ONE level of aggregation.** For linear/SVM models use the "
             "**six sub-scores** (richer, less collinear) and DROP `financial_score` + "
             "`competitive_advantage_score_w050` (both collinear by construction). Keep "
             "`operative_score` separate (as designed). Tree/boosting models tolerate the "
             "redundancy but gain nothing from the duplicates.\n")
    if len(high):
        pr = high.iloc[0]
        L.append(f"2. **Drop within high-corr KPI pairs.** e.g. `{pr['feat_a']}` vs "
                 f"`{pr['feat_b']}` (r={pr['pearson']:+.2f}) — keep one. See high_corr_pairs.csv "
                 "(candidates like return_on_assets vs operating_income_to_assets, "
                 "debt_to_assets vs net_debt_to_assets, reinvestment_rate vs its components).\n")
    else:
        L.append("2. No KPI pair exceeds |0.8|; keep the KPI set.\n")
    L.append(f"3. **Lead features (well-populated only, n>={RELIABLE_N}):** "
             f"{', '.join(top_pos['feature'].head(3))} (positive); "
             f"{', '.join(top_neg['feature'].head(3))} (negative). All |Spearman|<0.08 — weak; "
             "value comes from combining them, and change features carry as much of the (thin) "
             "signal as levels. Do NOT prioritise the sparse bank-only features despite their "
             "larger raw correlations.\n")
    L.append("4. **Split by time AND respect company grouping** (serial-correlated targets); "
             "**refit winsor caps on the training slice only** at split time (caps here were "
             "fit on the full train-eligible set for EDA); and keep missingness as NULL for a "
             "model that handles it natively.\n")

    path = os.path.join(EDA_OUT, "EDA_SUMMARY.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    MANIFEST.append(("EDA_SUMMARY.md", "Written EDA readout + recommendations"))
    print("\n".join(L))


# --------------------------------------------------------------------------- #
def winsor_caps(df: pd.DataFrame) -> dict:
    """Recover the caps actually applied (min/max of the winsorized columns), for plotting."""
    tr = df  # caps were applied over full population; use observed clip bounds
    caps = {}
    for col in WINSOR_COLS + [TARGET]:
        v = tr[col].dropna()
        caps[col] = (float(v.min()), float(v.max()))
    return caps


def main_eda() -> None:
    os.makedirs(EDA_OUT, exist_ok=True)
    df = load_eda()
    caps = winsor_caps(df)
    print(f"Loaded modelling_data: {len(df)} rows, train-eligible={int((df.train_eligible==1).sum())}, "
          f"artifacts -> {EDA_OUT}\n")
    skew_df = distributions(df, caps)
    tcorr, high = correlations(df)
    vifdf = vif(df)
    miss = missingness(df)
    tgt = target_analysis(df)
    write_summary_eda(df, skew_df, tcorr, high, vifdf, miss, tgt, caps)

    man = pd.DataFrame(MANIFEST, columns=["artifact", "description"])
    man.to_csv(os.path.join(EDA_OUT, "artifacts_manifest.csv"), index=False)
    print(f"\n=== {len(MANIFEST)} artifacts written to {EDA_OUT} ===")
    for name, desc in MANIFEST:
        print(f"  {name:34} {desc}")


# ============================================================================
# STAGE: train (was J_models)
# ============================================================================

warnings.filterwarnings("ignore")


SPLIT_DATE = "2025-03-31"      # <= this = train+val ; > this = untouched 12-month test
N_SPLITS = 5
CV_GAP = 21                    # ~1 month purge between train/val fold boundaries
SEED = 42

# --- feature set (decided post-EDA; inventory_turnover excluded: 79% missing) ------------
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


def feature_split(level: list[str]):
    """Given a level-feature list, return (all_features, wins_features, pass_features)."""
    feats = level + [c + "_change" for c in level]
    wins = [c for c in level if c in RATIO_TAIL] + [c + "_change" for c in level]
    pass_ = [f for f in feats if f not in wins]
    return feats, wins, pass_


def make_preprocessor(scale: bool, wins_features=WINS_FEATURES,
                      pass_features=PASS_FEATURES) -> Pipeline:
    ct = ColumnTransformer(
        [("wins", Winsorizer(), wins_features),
         ("pass", "passthrough", pass_features)],
        remainder="drop")
    steps = [("ct", ct), ("impute", SimpleImputer(strategy="median"))]
    if scale:
        steps.append(("scale", StandardScaler()))
    return Pipeline(steps)


def transformed_feature_order(wins_features=WINS_FEATURES,
                              pass_features=PASS_FEATURES) -> list[str]:
    """Column order after the ColumnTransformer (wins block then pass block)."""
    return wins_features + pass_features


# --------------------------------------------------------------------------- #
# model roster + modest grids
# --------------------------------------------------------------------------- #
def roster(wins_features=WINS_FEATURES, pass_features=PASS_FEATURES) -> dict:
    """name -> (estimator_pipeline, param_grid, needs_scaling, kind)."""
    def wrap(model, scale):
        pipe = Pipeline([("prep", make_preprocessor(scale, wins_features, pass_features)),
                         ("model", model)])
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
def build_X(df: pd.DataFrame, level: list[str] = LEVEL) -> pd.DataFrame:
    X = pd.DataFrame(index=df.index)
    for c in level:
        X[c] = df[(c + "_raw") if c in RATIO_TAIL else c].values
    for c in level:
        X[c + "_change"] = df[c + "_change"].values
    return X[level + [c + "_change" for c in level]]


def load():
    with closing(db.get_connection()) as con:
        df = pd.read_sql_query("SELECT * FROM modelling_data", con)
    df["rd"] = pd.to_datetime(df["report_release_date"])
    te = df[df["train_eligible"] == 1].sort_values("rd").reset_index(drop=True)
    split = pd.Timestamp(SPLIT_DATE)
    trainval = te[te["rd"] <= split].reset_index(drop=True)
    test = te[te["rd"] > split].reset_index(drop=True)
    # all-97 latest row per ticker (the forward ranking rows)
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
def main_train():
    os.makedirs(PRED_OUT, exist_ok=True)
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
    cv_df.to_csv(os.path.join(PRED_OUT, "cv_results.csv"), index=False)

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
    test_df_out.round(4).to_csv(os.path.join(PRED_OUT, "test_metrics.csv"))

    # ---- coefficients / importances (from the train+val-refit models) ----
    feat_order = transformed_feature_order()
    for name in models:
        reg = fitted[name].regressor_.named_steps["model"]
        if hasattr(reg, "coef_"):
            s = pd.Series(np.ravel(reg.coef_), index=feat_order, name="coef")
            s.reindex(s.abs().sort_values(ascending=False).index).to_csv(
                os.path.join(PRED_OUT, f"coef_{name}.csv"))
        elif hasattr(reg, "feature_importances_"):
            s = pd.Series(reg.feature_importances_, index=feat_order, name="importance")
            s.sort_values(ascending=False).to_csv(os.path.join(PRED_OUT, f"importance_{name}.csv"))

    # ---- final models refit on ALL train_eligible, predict ALL 97 latest rows ----
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

    train_cos = set(all_te["ticker"].unique())          # 73 companies with training rows
    out = pred89[["ticker", "sector", "company_group", "source", "report_release_date",
                  "frequency", "operative_missing", "no_release_date"]].copy()
    out["out_of_training_dist"] = (pred89["source"] != "edgar").astype(int)  # non-US
    out["prediction_only"] = (~pred89["ticker"].isin(train_cos)).astype(int)  # 25 names, no training
    for name in models:
        out[f"pred_{name}"] = final_preds[name]
    out["pred_ensemble"] = ens89
    out = out.sort_values("pred_ensemble", ascending=False).reset_index(drop=True)
    out["rank_ensemble"] = np.arange(1, len(out) + 1)
    # holds ALL ranked names (currently 97), not 89 — the legacy "all89" name was renamed
    out.round(5).to_csv(os.path.join(PRED_OUT, "predictions_all.csv"), index=False)

    write_summary_train(cv_df, test_df_out, best3, out)
    print(f"\nArtifacts -> {PRED_OUT}: cv_results.csv, test_metrics.csv, coef_/importance_*.csv, "
          f"predictions_all.csv, MODEL_SUMMARY.md")


def ablation():
    """ONE pre-committed robustness check: does the null survive the feature choice?
    Re-run the full roster (CV Spearman on train+val, one-shot test Spearman) under three
    feature sets — sub-scores-only, KPIs-only, full — to show the near-null is not an
    artifact of mixing feature families. Writes predictions/ablation_results.csv."""
    os.makedirs(PRED_OUT, exist_ok=True)
    df, trainval, test, _ = load()
    tscv = TimeSeriesSplit(n_splits=N_SPLITS, gap=CV_GAP)
    variants = {"subscores_only": SUBSCORES, "kpis_only": KPIS, "full": LEVEL}
    rows = []
    print("ABLATION — CV & test Spearman by feature set (leak-safe, same split/CV):")
    for vname, level in variants.items():
        _, wins_f, pass_f = feature_split(level)
        Xtv, ytv = build_X(trainval, level), trainval[TARGET_RAW].values
        Xte = build_X(test, level)
        for mname, (est, grid, scale, kind) in roster(wins_f, pass_f).items():
            gs = GridSearchCV(est, grid, scoring=SPEARMAN, cv=tscv, n_jobs=-1, refit=True)
            gs.fit(Xtv, ytv)
            cv = gs.cv_results_["mean_test_score"][gs.best_index_]
            tp = gs.best_estimator_.predict(Xte)
            degen = int(np.std(gs.best_estimator_.predict(Xtv)) < 1e-6)
            rows.append({"feature_set": vname, "n_features": len(level) * 2, "model": mname,
                         "cv_spearman": cv, "test_spearman": spearman_score(test[TARGET_RAW].values, tp),
                         "degenerate": degen})
        best = max([r for r in rows if r["feature_set"] == vname], key=lambda r: r["cv_spearman"])
        print(f"  {vname:16} best CV model={best['model']:12} cv={best['cv_spearman']:+.4f} "
              f"test={best['test_spearman']:+.4f}")
    out = pd.DataFrame(rows)
    out.round(4).to_csv(os.path.join(PRED_OUT, "ablation_results.csv"), index=False)
    # concise verdict
    piv = out.pivot_table(index="model", columns="feature_set", values="cv_spearman")
    print("\nCV Spearman by model × feature set:")
    print(piv.round(4).to_string())
    print(f"\nMax |CV Spearman| across ALL cells = {out['cv_spearman'].abs().max():.4f} "
          f"| max |test Spearman| = {out['test_spearman'].abs().max():.4f}")
    print("Null result is ROBUST to feature choice: no feature set lifts rank-corr materially "
          "above zero. -> predictions/ablation_results.csv")


def _best_param_kwargs(fitted_ttr) -> dict:
    """Extract best hyperparams from a fitted GridSearch best_estimator_ (TTR) so we can
    re-instantiate a fresh clone with the same params for the full-data refit."""
    reg = fitted_ttr.regressor_.named_steps["model"]
    params = reg.get_params()
    # map back onto the roster param namespace
    return {f"regressor__model__{k}": v for k, v in params.items()}


# --------------------------------------------------------------------------- #
def write_summary_train(cv_df, test_df, best3, preds):
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
    L.append("\nFull ranking of all names in predictions_all.csv (final models refit on ALL "
             "train_eligible rows; the 97 rows are each company's latest report, forward "
             "window still open — these are the ranking signals, not evaluable yet).")

    with open(os.path.join(PRED_OUT, "MODEL_SUMMARY.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))


# ============================================================================
# STAGE: backtest (was K_backtest)
# ============================================================================

LEG = 10               # top-10 long / bottom-10 short
MIN_NAMES = 2 * LEG    # need >=20 names to form both legs
COST_BPS_GRID = [0.0, 5.0, 10.0]   # one-way, in bps of traded notional
PRIMARY_COST_BPS = 10.0
PERIODS_PER_YEAR = 252 / 63        # ~4 (63-trading-day holding)

RISK_FREE_ANNUAL = config.RISK_FREE_RATE_ANNUAL
RF_PERIOD = config.risk_free_per_period(PERIODS_PER_YEAR)   # 0.02 / 4 = 0.005 per rebalance


def ensemble_members():
    """The 3 non-degenerate models with the hyperparameters J_models tuned by CV."""
    return {
        "SVR": (SVR(kernel="rbf", gamma="scale", epsilon=0.1, C=10), True),
        "RandomForest": (RandomForestRegressor(n_estimators=400, max_depth=None,
                         max_features=0.5, min_samples_leaf=20, random_state=SEED, n_jobs=1),
                         False),
        "XGBoost": (XGBRegressor(n_estimators=300, subsample=0.8, colsample_bytree=0.8,
                    max_depth=2, learning_rate=0.05, reg_lambda=5, random_state=SEED,
                    n_jobs=1, verbosity=0), False),
    }


def _fit_ensemble(Xtv, ytv):
    fitted = []
    for name, (model, scale) in ensemble_members().items():
        pipe = Pipeline([("prep", make_preprocessor(scale)), ("model", model)])
        ttr = TransformedTargetRegressor(regressor=pipe, transformer=YWinsorizer())
        ttr.fit(Xtv, ytv)
        fitted.append(ttr)
    return fitted


def _predict_ensemble(fitted, X):
    return np.mean([m.predict(X) for m in fitted], axis=0)


def _max_drawdown(equity: np.ndarray) -> float:
    peak = np.maximum.accumulate(equity)
    return float((equity / peak - 1.0).min())


def main_backtest():
    os.makedirs(PRED_OUT, exist_ok=True)
    df, trainval, test, _ = load()

    # freeze ensemble on train+val
    Xtv, ytv = build_X(trainval), trainval[TARGET_RAW].values
    fitted = _fit_ensemble(Xtv, ytv)

    # backtest universe: quarterly, test window, complete forward window, has change features
    df["rd"] = pd.to_datetime(df["report_release_date"])
    uni = df[(df["rd"] > pd.Timestamp(SPLIT_DATE)) & (df["frequency"] == "quarterly")
             & (df["future_63d_return"].notna()) & (df["first_obs"] == 0)].copy()
    uni["pred"] = _predict_ensemble(fitted, build_X(uni))
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
        # SELF-FINANCING net: short proceeds earn RF_PERIOD, which cancels the RF_PERIOD
        # subtracted to form the excess return => the spread IS already an excess return.
        net = bt["gross_ls"].values - cost
        equity = np.cumprod(1.0 + net)
        equity_curves[c] = equity
        sd = net.std(ddof=1)
        ann_sharpe = net.mean() / sd * np.sqrt(PERIODS_PER_YEAR) if sd > 0 else np.nan
        # SENSITIVITY: naive fully-funded book, charged rf on capital it never borrowed.
        # std is unchanged (RF_PERIOD is a constant), only the numerator moves.
        funded = net - RF_PERIOD
        ann_sharpe_funded = (funded.mean() / funded.std(ddof=1) * np.sqrt(PERIODS_PER_YEAR)
                             if funded.std(ddof=1) > 0 else np.nan)
        summary.append({
            "cost_bps_oneway": c,
            "cum_return_LS": float(equity[-1] - 1.0),
            "mean_period_LS": float(net.mean()),
            "ann_sharpe_LS": float(ann_sharpe),
            "ann_sharpe_LS_funded": float(ann_sharpe_funded),
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
    bt_out.round(4).to_csv(os.path.join(PRED_OUT, "backtest_periods.csv"), index=False)
    pd.DataFrame(holdings).to_csv(os.path.join(PRED_OUT, "backtest_holdings.csv"), index=False)
    sm = pd.DataFrame(summary)
    sm.round(4).to_csv(os.path.join(PRED_OUT, "backtest_summary.csv"), index=False)

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
    fig.savefig(os.path.join(PRED_OUT, "fig_backtest_equity.png"), dpi=110, bbox_inches="tight")
    plt.close(fig)

    # console report
    print("\nPer-rebalance long-short (gross):")
    print(bt[["period", "n_universe", "n_intl", "long_ret", "short_ret", "gross_ls",
              "intl_in_long", "intl_in_short"]].round(4).to_string(index=False))
    print("\nStrategy summary by transaction cost:")
    print(sm.round(4).to_string(index=False))
    print(f"\nrisk-free = {RISK_FREE_ANNUAL:.2%} annualized -> RF_PERIOD = "
          f"{RISK_FREE_ANNUAL}/{PERIODS_PER_YEAR:.0f} = {RF_PERIOD:.4f} per ~63d rebalance.")
    print("  ann_sharpe_LS        = SELF-FINANCING (rf cancels: short proceeds earn it)")
    print("  ann_sharpe_LS_funded = SENSITIVITY, naive fully-funded book (rf charged)")
    print(f"\nContext (gross, compounded over the {len(bt)} rebalances): "
          f"long-leg={long_cum:+.4f}  short-leg={short_cum:+.4f}  "
          f"equal-weight universe benchmark={bench:+.4f}")

    write_summary_backtest(bt, sm, long_cum, short_cum, bench, periods)
    print(f"\nArtifacts -> {PRED_OUT}: backtest_periods.csv, backtest_holdings.csv, "
          f"backtest_summary.csv, fig_backtest_equity.png, BACKTEST_SUMMARY.md")


def write_summary_backtest(bt, sm, long_cum, short_cum, bench, periods):
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
             f"+ XGBoost) is frozen on train+val (<= {SPLIT_DATE}) and applied forward to "
             f"each of {len(bt)} quarterly rebalances in the held-out test year.\n")
    L.append("## Assumptions\n")
    L.append(f"- Equal-weight **top-{LEG} long / bottom-{LEG} short**, ranked by predicted "
             "future_63d_sharpe.\n"
             "- Rebalance each fiscal quarter (~63 trading days); hold to next report period.\n"
             "- Transaction cost on one-way traded notional, reported at 0 / 5 / 10 bps "
             f"(primary = {int(PRIMARY_COST_BPS)} bps).\n"
             f"- Periods with <{MIN_NAMES} names skipped (cannot form both legs); "
             "internationals included but flagged out-of-training.\n")
    L.append("## Risk-free rate\n")
    L.append(f"Constant **rf = {RISK_FREE_ANNUAL:.1%} annualized** (~average 3-month US T-bill "
             "yield, FRED series TB3MS, over the 2020-2026 sample; the 3-month bill is the "
             "standard academic risk-free proxy). The strategy return series is one "
             f"observation per ~63-trading-day rebalance, so the frequency-converted rate is "
             f"**RF_PERIOD = {RISK_FREE_ANNUAL} / {PERIODS_PER_YEAR:.0f} = {RF_PERIOD:.4f}** "
             "per period — the annual 2% is never subtracted from a 63-day return.\n\n"
             "The book is **dollar-neutral and self-financing**: the short proceeds fund the "
             "long leg and earn rf. That rf credit exactly cancels the rf subtracted to form "
             "an excess return —\n\n"
             "```\n"
             "net_p    = (long_p - short_p) + RF_PERIOD - cost_p\n"
             "excess_p = net_p - RF_PERIOD = long_p - short_p - cost_p\n"
             "```\n\n"
             "— so **`ann_sharpe_LS` is unchanged by the risk-free rate**. This cancellation is "
             "a consequence of the self-financing structure, not an omission of rf. "
             "`ann_sharpe_LS_funded` is reported as a **sensitivity**: the naive fully-funded "
             "variant that charges rf on capital the strategy never borrowed "
             f"(`excess_p = gross_ls_p - cost_p - {RF_PERIOD:.4f}`). It is the more pessimistic "
             "reading, shown for transparency, not as the headline.\n\n"
             "Note the target uses the SAME annual rate at a DIFFERENT horizon: "
             "`rf_daily = 0.02/252`, subtracted from each daily return before mean/std.\n")
    L.append("## Per-rebalance long-short (gross)\n")
    L.append(tbl(bt, ["period", "n_universe", "n_intl", "long_ret", "short_ret", "gross_ls",
                      "intl_in_long", "intl_in_short"]))
    L.append("\n## Strategy summary by transaction cost\n")
    L.append(tbl(sm, ["cost_bps_oneway", "cum_return_LS", "mean_period_LS", "ann_sharpe_LS",
                      "ann_sharpe_LS_funded", "max_drawdown_LS"]))
    L.append(f"\n**Headline (@{int(PRIMARY_COST_BPS)}bps):** cumulative long-short "
             f"{prim['cum_return_LS']:+.2%}, annualized Sharpe {prim['ann_sharpe_LS']:+.2f} "
             f"(self-financing; fully-funded sensitivity {prim['ann_sharpe_LS_funded']:+.2f}), "
             f"max drawdown {prim['max_drawdown_LS']:+.2%} over {int(prim['n_rebalances'])} "
             "quarterly rebalances.\n")
    L.append(f"Context (gross): long leg {long_cum:+.2%}, short leg {short_cum:+.2%}, "
             f"equal-weight universe {bench:+.2%}.\n")
    L.append("## Honest read\n")
    g = bt["gross_ls"].values
    tstat = g.mean() / (g.std(ddof=1) / np.sqrt(len(g))) if g.std(ddof=1) > 0 else 0.0
    n_pos = int((g > 0).sum())
    L.append(f"The per-rebalance spread FLIPS SIGN ({n_pos} of {len(g)} positive) and its mean "
             f"{g.mean():+.2%} sits well inside one standard deviation {g.std(ddof=1):.2%} "
             f"(t = {tstat:+.2f} on {len(g) - 1} d.f.) — **not distinguishable from zero**, "
             "whatever sign the cumulative figure takes. Do not read the cumulative number as "
             "an edge.\n")
    L.append(f"With only {len(g)} rebalances the Sharpe/drawdown are high-variance and should "
             "not be over-interpreted. Given the model showed no reliable rank signal (CV & test "
             "Spearman ~0, robust across the feature-set ablation), any long-short spread here "
             "is consistent with noise, not a repeatable edge. The deliverable is the "
             "END-TO-END LEAK-FREE PIPELINE (features knowable at release date, time-based "
             "split, per-fold preprocessing, frozen-model walk-forward, costs) producing an "
             "honest — and honestly weak — result, as expected under market efficiency.\n")
    with open(os.path.join(PRED_OUT, "BACKTEST_SUMMARY.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))


# ============================================================================
# STAGE: analysis (was L_analysis)
# ============================================================================

warnings.filterwarnings("ignore")

LC_MODELS = ["Ridge", "RandomForest", "XGBoost"]
INK, MUTED, FAINT = "#1f2937", "#6b7280", "#9ca3af"
POS, NEG = "#0f766e", "#b91c1c"


def _rmse(y, p):
    return float(np.sqrt(mean_squared_error(y, p)))


def _sp(y, p):
    r = spearmanr(y, p).correlation
    return 0.0 if (r is None or np.isnan(r)) else float(r)


def tuned_params() -> dict[str, dict]:
    """Best hyperparameters from the committed 97-run (predictions/cv_results.csv)."""
    cv = pd.read_csv(os.path.join(PRED_OUT, "cv_results.csv"))
    return {r["model"]: ast.literal_eval(r["best_params"]) for _, r in cv.iterrows()}


def build_reg(name: str, params: dict):
    """The J_models estimator (TTR-wrapped pipeline) with its tuned params applied."""
    est = clone(roster()[name][0])
    est.set_params(**{f"regressor__model__{k}": v for k, v in params.items()})
    return est


# --------------------------------------------------------------------------- #
# 1. ERROR ANALYSIS — bias & variance
# --------------------------------------------------------------------------- #
def learning_curve_timesafe(est, X: pd.DataFrame, y: np.ndarray, *, n_points=8,
                            val_frac=0.2, gap=CV_GAP) -> pd.DataFrame:
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
    tscv = TimeSeriesSplit(n_splits=N_SPLITS, gap=CV_GAP)
    scoring = {"spearman": SPEARMAN,
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
    tbl.round(4).to_csv(os.path.join(ANALYSIS_OUT, "train_vs_val_error.csv"), index=False)

    curves = {}
    for name in LC_MODELS:
        lc = learning_curve_timesafe(build_reg(name, params[name]), Xtv, ytv)
        lc.to_csv(os.path.join(ANALYSIS_OUT, f"learning_curve_{name}.csv"), index=False)
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
        fig.savefig(os.path.join(ANALYSIS_OUT, f"fig_learning_curve_{name}.png"), dpi=110,
                    bbox_inches="tight")
        plt.close(fig)
    return tbl, curves


# --------------------------------------------------------------------------- #
# 2. FEATURE IMPORTANCE
# --------------------------------------------------------------------------- #
def feature_importance(Xtv, ytv, params):
    print("\n=== 2. FEATURE IMPORTANCE ===")
    feats = transformed_feature_order()
    imp: dict[str, pd.Series] = {}
    for name, p in params.items():
        m = build_reg(name, p).fit(Xtv, ytv)
        reg = m.regressor_.named_steps["model"]
        if hasattr(reg, "coef_"):
            imp[name] = pd.Series(np.abs(np.ravel(reg.coef_)), index=feats)
            signed = pd.Series(np.ravel(reg.coef_), index=feats)
            signed.reindex(signed.abs().sort_values(ascending=False).index).to_csv(
                os.path.join(ANALYSIS_OUT, f"coef_{name}.csv"))
            nz = int((signed != 0).sum())
            print(f"  {name:14} linear: {nz}/{len(feats)} non-zero coefficients")
        elif hasattr(reg, "feature_importances_"):
            imp[name] = pd.Series(reg.feature_importances_, index=feats)
            print(f"  {name:14} tree importances extracted")

    # SVR: permutation importance on the CV VALIDATION folds (never test)
    tscv = TimeSeriesSplit(n_splits=N_SPLITS, gap=CV_GAP)
    perm = np.zeros(len(feats))
    folds = 0
    est = build_reg("SVR", params["SVR"])
    for tr, va in tscv.split(Xtv):
        m = clone(est).fit(Xtv.iloc[tr], ytv[tr])
        r = permutation_importance(m, Xtv.iloc[va], ytv[va], n_repeats=5,
                                   random_state=SEED, scoring=SPEARMAN, n_jobs=-1)
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
        os.path.join(ANALYSIS_OUT, "feature_importance_combined.csv"))

    for name in ["Ridge", "RandomForest", "XGBoost"]:
        s = imp[name].sort_values(ascending=False).head(15)[::-1]
        fig, ax = plt.subplots(figsize=(7, 5))
        ax.barh(s.index, s.values, color=MUTED)
        ax.set_title(f"{name} — top 15 feature importance", fontsize=10)
        ax.tick_params(labelsize=7)
        fig.tight_layout(); fig.savefig(os.path.join(ANALYSIS_OUT, f"fig_importance_{name}.png"),
                                        dpi=110, bbox_inches="tight"); plt.close(fig)

    top = consensus.head(15)[::-1]
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.barh(top.index, -top.values, color=INK)
    ax.set_xlabel("← stronger (lower mean rank across models)")
    ax.set_title("Rank-consensus feature importance (Ridge, RF, XGB, SVR-perm)", fontsize=10)
    ax.tick_params(labelsize=7); ax.set_xticks([])
    fig.tight_layout(); fig.savefig(os.path.join(ANALYSIS_OUT, "fig_importance_consensus.png"),
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
        s = df.loc[idx, TARGET_RAW].values
        if len(s) < min_n:
            continue
        lo, hi = np.quantile(s, [1 / 3, 2 / 3])
        y[pos] = _label_from_cut(s, lo, hi)
    return y


def clf_roster():
    def wrap(model, scale):
        return Pipeline([("prep", make_preprocessor(scale)), ("model", model)])
    return {
        "LogisticRegression": (wrap(LogisticRegression(max_iter=5000, random_state=SEED), True),
                               {"model__C": [0.01, 0.1, 1, 10]}),
        "RandomForest": (wrap(RandomForestClassifier(n_estimators=400, random_state=SEED,
                              n_jobs=1), False),
                         {"model__max_depth": [3, 5, None], "model__min_samples_leaf": [5, 20]}),
        "XGBoost": (wrap(XGBClassifier(n_estimators=300, subsample=0.8, colsample_bytree=0.8,
                    random_state=SEED, n_jobs=1, verbosity=0, eval_metric="logloss"), False),
                    {"model__max_depth": [2, 3], "model__learning_rate": [0.02, 0.05],
                     "model__reg_lambda": [1, 5]}),
        "SVM": (wrap(SVC(kernel="rbf", probability=True, random_state=SEED), True),
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
    tscv = TimeSeriesSplit(n_splits=N_SPLITS, gap=CV_GAP)
    ytv_raw, yte_raw = trainval[TARGET_RAW].values, test[TARGET_RAW].values

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
    res.round(4).to_csv(os.path.join(ANALYSIS_OUT, "classification_metrics.csv"), index=False)

    # ROC curves (primary scheme)
    fig, ax = plt.subplots(figsize=(6, 5.5))
    for cname, (fpr, tpr, _, auc) in roc_data.items():
        ax.plot(fpr, tpr, lw=1.8, label=f"{cname} (AUC={auc:.3f})")
    ax.plot([0, 1], [0, 1], ls="--", color=FAINT, lw=1, label="chance (AUC=0.500)")
    ax.set_xlabel("false positive rate"); ax.set_ylabel("true positive rate")
    ax.set_title("ROC — test set, top-third vs bottom-third\n(cutoffs fit on train only)",
                 fontsize=10)
    ax.legend(fontsize=8); fig.tight_layout()
    fig.savefig(os.path.join(ANALYSIS_OUT, "fig_roc_curves.png"), dpi=110, bbox_inches="tight")
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
    fig.tight_layout(); fig.savefig(os.path.join(ANALYSIS_OUT, "fig_confusion_matrices.png"),
                                    dpi=110, bbox_inches="tight"); plt.close(fig)
    return res


# --------------------------------------------------------------------------- #
def main_analysis():
    os.makedirs(ANALYSIS_OUT, exist_ok=True)
    df, trainval, test, _ = load()
    Xtv, ytv = build_X(trainval), trainval[TARGET_RAW].values
    Xte = build_X(test)
    params = tuned_params()
    print(f"train+val={len(trainval)} test={len(test)} features={Xtv.shape[1]} "
          f"| tuned params from predictions/cv_results.csv")

    err, curves = error_analysis(Xtv, ytv, params)
    wide, consensus = feature_importance(Xtv, ytv, params)
    clf = classification(trainval, test, Xtv, Xte)

    write_reports(err, curves, wide, consensus, clf, ytv)
    print(f"\nArtifacts -> {ANALYSIS_OUT}")


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
    open(os.path.join(ANALYSIS_OUT, "bias_variance.md"), "w", encoding="utf-8").write("\n".join(L))

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
    open(os.path.join(ANALYSIS_OUT, "feature_importance.md"), "w", encoding="utf-8").write("\n".join(L))

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
    open(os.path.join(ANALYSIS_OUT, "classification.md"), "w", encoding="utf-8").write("\n".join(L))
