"""
data.py — cached, READ-ONLY data access for the Signal Desk dashboard.

Reads data/financials.db plus the eda/, predictions/ and analysis/ artifacts. Computes
nothing, never writes.

Universe = 97 (the mandated 98 minus GOOG, a documented Alphabet dual-class dedup). The
count is never hard-coded: it is derived from the data via `universe_meta()`.
"""
from __future__ import annotations

import base64
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "financials.db"
EDA_DIR = ROOT / "eda"
PRED_DIR = ROOT / "predictions"
ANALYSIS_DIR = ROOT / "analysis"
LOGO_DIR = Path(__file__).resolve().parent / "logos"


@st.cache_data(show_spinner=False)
def load_companies() -> pd.DataFrame:
    """One row per ticker: name, sector, company_group, source, is_intl. Sorted by sector."""
    with sqlite3.connect(DB_PATH) as con:
        df = pd.read_sql_query(
            """
            SELECT ticker,
                   MAX(company_name)  AS name,
                   MAX(sector)        AS sector,
                   MAX(company_group) AS company_group,
                   MAX(source)        AS source
            FROM financial_facts
            GROUP BY ticker
            ORDER BY sector, ticker
            """,
            con,
        )
    df["is_intl"] = df["source"] != "edgar"
    return df.reset_index(drop=True)


LOGO_BOX = 128      # normalized canvas (px)
LOGO_MARGIN = 0.06  # breathing room around the trimmed mark, as a fraction of the box


def _normalize_logo(raw: bytes) -> bytes:
    """Trim a logo's transparent padding, re-center it on a square canvas with a small
    uniform margin, and scale it to fill.

    The fetched PNGs are wildly inconsistent: GS/HSBA fill their whole 128x128 canvas while
    JPM's mark is 16x16 inside it (2% fill) and AXP's is 32x32 (6%). CSS `background-size`
    scales the CANVAS, so without trimming those marks render as ~4px specks in a 40px tile
    — the enlarged tile alone cannot fix it. Normalizing here (not by rewriting the committed
    PNGs) keeps the fix with the consumer and survives a logo re-fetch.

    Aspect ratio is preserved: a wide wordmark stays wide, it just fills the width. Falls
    back to the raw bytes if Pillow is unavailable or the image has no alpha content."""
    try:
        import io
        from PIL import Image
    except ImportError:
        return raw
    try:
        im = Image.open(io.BytesIO(raw)).convert("RGBA")
        bbox = im.getchannel("A").getbbox()
        if not bbox:
            return raw
        mark = im.crop(bbox)
        inner = int(LOGO_BOX * (1 - 2 * LOGO_MARGIN))
        w, h = mark.size
        scale = inner / max(w, h)
        mark = mark.resize((max(1, round(w * scale)), max(1, round(h * scale))),
                           Image.LANCZOS)
        canvas = Image.new("RGBA", (LOGO_BOX, LOGO_BOX), (0, 0, 0, 0))
        canvas.paste(mark, ((LOGO_BOX - mark.width) // 2, (LOGO_BOX - mark.height) // 2), mark)
        buf = io.BytesIO()
        canvas.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return raw


@st.cache_data(show_spinner=False)
def logo_uris() -> dict[str, str]:
    """ticker -> base64 data URI for every cached logo in dashboard/logos/, each normalized
    to a consistent square canvas. Tickers with no file simply aren't in the dict (the UI
    falls back to the styled sector badge). Encoded once (cached), served inline so no
    static-file server / network is needed at render time."""
    out: dict[str, str] = {}
    if LOGO_DIR.exists():
        for p in sorted(LOGO_DIR.glob("*.png")):
            b64 = base64.b64encode(_normalize_logo(p.read_bytes())).decode("ascii")
            out[p.stem] = f"data:image/png;base64,{b64}"
    return out


@st.cache_data(show_spinner=False)
def load_ranking() -> pd.DataFrame:
    """The model's predicted forward-63d-Sharpe ranking (predictions_all89.csv — filename
    retained for continuity; it holds all 97), joined to company name, sorted best-to-worst.

    Adds a `confidence` column from the pipeline's provenance flags. NOTE:
    `out_of_training_dist` and `prediction_only` are identical by construction (a name held
    out of training is exactly a name we can only predict on), so they are surfaced as ONE
    confidence tier, not two. `no_release_date` is a strictly smaller subset (5 names with no
    usable yfinance release date -> no target could ever be built) and is called out
    separately, because it is a stronger caveat than mere out-of-training status."""
    df = pd.read_csv(PRED_DIR / "predictions_all89.csv")
    names = load_companies().set_index("ticker")["name"]
    df["name"] = df["ticker"].map(names)
    df = df.sort_values("rank_ensemble").reset_index(drop=True)
    n = len(df)
    df["basket"] = ["LONG" if r <= 10 else "SHORT" if r > n - 10 else ""
                    for r in df["rank_ensemble"]]

    def _conf(r) -> str:
        if r["no_release_date"]:
            return "No release date"
        if r["out_of_training_dist"]:
            return "Prediction-only"
        return "Train-eligible"

    df["confidence"] = df.apply(_conf, axis=1)
    return df


@st.cache_data(show_spinner=False)
def flag_counts() -> dict:
    """Headline counts of the three provenance flags, derived (never hard-coded)."""
    df = load_ranking()
    return {
        "n": len(df),
        "prediction_only": int(df["out_of_training_dist"].sum()),
        "no_release_date": int(df["no_release_date"].sum()),
        "train_eligible": int((df["confidence"] == "Train-eligible").sum()),
        "operative_missing": int(df["operative_missing"].sum()),
    }


@st.cache_data(show_spinner=False)
def load_cv() -> pd.DataFrame:
    return pd.read_csv(PRED_DIR / "cv_results.csv")


def best_real_cv(cv: pd.DataFrame) -> pd.Series:
    """Best CV Spearman among NON-DEGENERATE models.

    Lasso/ElasticNet regularize every coefficient to exactly zero — they ARE the mean
    predictor. A naive idxmax() over cv_spearman_mean picks ElasticNet (+0.012) and
    advertises the null/constant model as "best", which is meaningless (its rank
    correlation is an artifact of a constant prediction, not of learned signal). Restrict
    to models that actually predict something, then take the max."""
    real = cv[cv["degenerate_constant"] == 0]
    return real.loc[real["cv_spearman_mean"].idxmax()]


@st.cache_data(show_spinner=False)
def load_test_metrics() -> pd.DataFrame:
    return pd.read_csv(PRED_DIR / "test_metrics.csv")


@st.cache_data(show_spinner=False)
def load_ablation() -> pd.DataFrame:
    return pd.read_csv(PRED_DIR / "ablation_results.csv")


@st.cache_data(show_spinner=False)
def load_feature_target() -> pd.DataFrame:
    return pd.read_csv(EDA_DIR / "feature_target_corr.csv")


@st.cache_data(show_spinner=False)
def load_vif() -> pd.DataFrame:
    return pd.read_csv(EDA_DIR / "vif_table.csv")


@st.cache_data(show_spinner=False)
def load_target_by_sector() -> pd.DataFrame:
    return pd.read_csv(EDA_DIR / "target_by_sector.csv")


@st.cache_data(show_spinner=False)
def load_backtest_periods() -> pd.DataFrame:
    return pd.read_csv(PRED_DIR / "backtest_periods.csv")


@st.cache_data(show_spinner=False)
def load_backtest_summary() -> pd.DataFrame:
    return pd.read_csv(PRED_DIR / "backtest_summary.csv")


@st.cache_data(show_spinner=False)
def load_backtest_holdings() -> pd.DataFrame:
    return pd.read_csv(PRED_DIR / "backtest_holdings.csv")


@st.cache_data(show_spinner=False)
def company_history(ticker: str) -> pd.DataFrame:
    """Per-report timeseries for one company from modelling_data (scores, KPIs, target)."""
    with sqlite3.connect(DB_PATH) as con:
        df = pd.read_sql_query(
            "SELECT * FROM modelling_data WHERE ticker = ? ORDER BY report_release_date",
            con, params=[ticker])
    if len(df):
        df["rd"] = pd.to_datetime(df["report_release_date"])
    return df


@st.cache_data(show_spinner=False)
def company_prices(ticker: str) -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as con:
        df = pd.read_sql_query(
            "SELECT date, adjusted_close FROM daily_prices WHERE ticker = ? ORDER BY date",
            con, params=[ticker])
    if len(df):
        df["date"] = pd.to_datetime(df["date"])
    return df


# ---------------------------------------------------------------- analysis/ (slide-24) --- #
@st.cache_data(show_spinner=False)
def load_train_vs_val() -> pd.DataFrame:
    """Bias-variance table: train vs validation RMSE / Spearman per model."""
    return pd.read_csv(ANALYSIS_DIR / "train_vs_val_error.csv")


@st.cache_data(show_spinner=False)
def load_learning_curve(model: str) -> pd.DataFrame:
    """Expanding-prefix learning curve for one of Ridge / RandomForest / XGBoost."""
    return pd.read_csv(ANALYSIS_DIR / f"learning_curve_{model}.csv")


LEARNING_CURVE_MODELS = ["Ridge", "RandomForest", "XGBoost"]


@st.cache_data(show_spinner=False)
def load_feature_importance() -> pd.DataFrame:
    """Per-model importances + the rank-consensus column. The unnamed index column in the
    CSV is the feature name."""
    df = pd.read_csv(ANALYSIS_DIR / "feature_importance_combined.csv")
    return df.rename(columns={df.columns[0]: "feature"})


@st.cache_data(show_spinner=False)
def load_classification() -> pd.DataFrame:
    """Classification-lens metrics under both labelling schemes."""
    return pd.read_csv(ANALYSIS_DIR / "classification_metrics.csv")


# must mirror J_models.py: TARGET_RAW is what CV actually scores against, and the
# train+val slice is everything on or before SPLIT_DATE. Getting either wrong silently
# changes the "mean-predictor RMSE" reference line on the learning curves.
SPLIT_DATE = "2025-03-31"
TARGET_RAW = "future_63d_sharpe_raw"


@st.cache_data(show_spinner=False)
def target_std() -> float:
    """std of the RAW target over the train+val rows — the RMSE a mean-predictor achieves,
    and the reference line on the learning curves. Derived from the DB (not copied out of
    bias_variance.md) so it can never drift from the artifacts. Reproduces the 1.986 that
    L_analysis.py reports."""
    with sqlite3.connect(DB_PATH) as con:
        s = pd.read_sql_query(
            f"SELECT {TARGET_RAW} FROM modelling_data "
            f"WHERE train_eligible = 1 AND report_release_date <= ?", con, params=[SPLIT_DATE])
    return float(s[TARGET_RAW].std())


def eda_fig(name: str) -> str:
    """Absolute path to an eda/ figure PNG (for st.image)."""
    return str(EDA_DIR / name)


def analysis_fig(name: str) -> str:
    """Absolute path to an analysis/ figure PNG (for st.image)."""
    return str(ANALYSIS_DIR / name)


@st.cache_data(show_spinner=False)
def universe_meta() -> dict:
    """Small headline facts for the header band. All derived — the 97 is never hard-coded."""
    df = load_companies()
    return {
        "n_companies": int(df["ticker"].nunique()),
        "n_sectors": int(df["sector"].nunique()),
        "n_intl": int(df["is_intl"].sum()),
    }
