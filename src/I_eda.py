"""
I_eda.py — analytical phase, step 6: EDA + feature diagnostics on `modelling_data`.

READ-ONLY on the DB (reads `modelling_data` only). Writes artifacts (PNG figures + CSV
tables + a markdown summary) to the repo-root `eda/` folder for a later Streamlit dashboard
to consume. Modifies NO table.

SCOPING RULES (from the task brief):
- All statistics that INFORM MODELLING (correlations, VIF, feature<->target relationships,
  target-by-sector) are computed on TRAIN-ELIGIBLE rows ONLY (train_eligible=1) so the
  prediction-only international rows never influence feature choices. Descriptive
  distribution plots show ALL rows but LABEL train vs prediction-only.
- Diagnostics use the WINSORIZED feature columns (what the model will see); raw vs
  winsorized is shown side-by-side for the six ratio-tail KPIs and the target.

USAGE (run from inside src/):
    python I_eda.py           # compute + save all artifacts to ../eda/, print the summary
"""
from __future__ import annotations

import os
from contextlib import closing

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import B_database

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE_DIR, "eda")

# --------------------------------------------------------------------------- #
# feature groups (winsorized/model columns are the base names)
# --------------------------------------------------------------------------- #
SUBSCORES = ["profitability_score", "growth_score", "cash_flow_score",
             "leverage_score", "efficiency_score", "investment_score"]
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
    path = os.path.join(OUT, name)
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)
    MANIFEST.append((name, desc))


def _csv(df: pd.DataFrame, name: str, desc: str, index: bool = True) -> None:
    df.to_csv(os.path.join(OUT, name), index=index)
    MANIFEST.append((name, desc))


# --------------------------------------------------------------------------- #
# load
# --------------------------------------------------------------------------- #
def load() -> pd.DataFrame:
    with closing(B_database.get_connection()) as con:
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
def write_summary(df, skew_df, tcorr, high, vifdf, miss, tgt, caps) -> None:
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

    path = os.path.join(OUT, "EDA_SUMMARY.md")
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


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    df = load()
    caps = winsor_caps(df)
    print(f"Loaded modelling_data: {len(df)} rows, train-eligible={int((df.train_eligible==1).sum())}, "
          f"artifacts -> {OUT}\n")
    skew_df = distributions(df, caps)
    tcorr, high = correlations(df)
    vifdf = vif(df)
    miss = missingness(df)
    tgt = target_analysis(df)
    write_summary(df, skew_df, tcorr, high, vifdf, miss, tgt, caps)

    man = pd.DataFrame(MANIFEST, columns=["artifact", "description"])
    man.to_csv(os.path.join(OUT, "artifacts_manifest.csv"), index=False)
    print(f"\n=== {len(MANIFEST)} artifacts written to {OUT} ===")
    for name, desc in MANIFEST:
        print(f"  {name:34} {desc}")


if __name__ == "__main__":
    main()
