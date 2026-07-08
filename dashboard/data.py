"""
data.py — cached, READ-ONLY data access for the Signal Desk dashboard.

Reads data/financials.db plus the eda/, predictions/ and analysis/ artifacts. Computes
nothing, never writes.

Universe = 97 (the mandated 98 minus GOOG, a documented Alphabet dual-class dedup). The
count is never hard-coded: it is derived from the data via `universe_meta()`.
"""
from __future__ import annotations

import base64
import re
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


ASSETS_DIR = Path(__file__).resolve().parent / "assets"


ALPHA_FLOOR = 24     # ignore near-transparent halo pixels when trimming / measuring
DARK_INK_LUMA = 95   # mean luminance below this = dark artwork, invisible on the navy theme


def _trim_transparent(raw: bytes) -> tuple[bytes, bool]:
    """Crop transparent padding (PRESERVING aspect ratio, unlike _normalize_logo which squares
    the canvas and would letterbox a wide wordmark), and report whether the artwork is dark.

    Trims on an alpha THRESHOLD, not `alpha > 0`: exported PNGs routinely carry a sub-visible
    halo across the whole canvas, so a plain getbbox() returns the full canvas and trims
    nothing — which is why the logo first rendered at 73px wide inside a 40px-tall holder.

    Returns (png_bytes, is_dark_ink)."""
    try:
        import io
        from PIL import Image
    except ImportError:
        return raw, False
    try:
        im = Image.open(io.BytesIO(raw)).convert("RGBA")
        alpha = im.getchannel("A")
        bbox = alpha.point(lambda a: 255 if a > ALPHA_FLOOR else 0).getbbox()
        if not bbox:
            return raw, False
        cropped = im.crop(bbox)
        px = [(r, g, b) for r, g, b, a in cropped.getdata() if a > ALPHA_FLOOR]
        luma = (sum(0.299 * r + 0.587 * g + 0.114 * b for r, g, b in px) / len(px)) if px else 255
        buf = io.BytesIO()
        cropped.save(buf, format="PNG")
        return buf.getvalue(), luma < DARK_INK_LUMA
    except Exception:
        return raw, False


def _logo_sig() -> tuple:
    """(exists, mtime, size) for each candidate logo file — the cache key below.

    Keying on file identity rather than nothing keeps the original promise (drop a new
    logo.png in and it appears without a restart) while making the expensive part cacheable."""
    out = []
    for name in ("logo.png", "logo_dark.png"):
        p = ASSETS_DIR / name
        out.append((p.stat().st_mtime_ns, p.stat().st_size) if p.exists() else None)
    return tuple(out)


@st.cache_data(show_spinner=False)
def _app_logo_uri_cached(mode: str, _sig: tuple) -> tuple[str | None, bool]:
    if mode == "dark":
        dark_variant = ASSETS_DIR / "logo_dark.png"
        if dark_variant.exists():
            png, _ = _trim_transparent(dark_variant.read_bytes())
            return f"data:image/png;base64,{base64.b64encode(png).decode('ascii')}", False

    p = ASSETS_DIR / "logo.png"
    if not p.exists():
        return None, False
    png, is_dark_ink = _trim_transparent(p.read_bytes())
    uri = f"data:image/png;base64,{base64.b64encode(png).decode('ascii')}"
    return uri, (mode == "dark" and is_dark_ink)


def app_logo_uri(mode: str = "dark") -> tuple[str | None, bool]:
    """(data_uri, whiten) for the header logo, or (None, False) if no logo.png exists yet
    (the UI then falls back to the SIGNAL·DESK wordmark placeholder).

    A dark-ink logo is invisible on the navy dark theme. Two escapes, in order:
      1. drop an `assets/logo_dark.png` — a light-ink variant, used verbatim in dark mode;
      2. otherwise, if the artwork measures dark, the UI whitens it with a CSS filter.
    Light mode always uses logo.png untouched.

    CACHED ON FILE IDENTITY. The trim + per-pixel luminance measurement cost ~27 ms on EVERY
    rerun of EVERY page. The cache key is (mtime, size) of both candidate files, so dropping in
    a new logo still takes effect immediately — no restart, which was the reason this was
    originally left uncached."""
    return _app_logo_uri_cached(mode, _logo_sig())


@st.cache_data(show_spinner=False)
def display_tickers() -> dict[str, str]:
    """real ticker -> DISPLAY ticker (exchange suffix stripped).

    DISPLAY ONLY. The real ticker stays the key everywhere: session state, row-click routing,
    logo lookup, DB queries, predictions joins. Never feed a display string back into a lookup.

    Only the exchange suffix after a DOT is stripped, so 'SHEL.L' -> 'SHEL' and '005930.KS' ->
    '005930', while 'BRK-B' and 'NOVO-B.CO' -> 'NOVO-B' keep their hyphenated share class.

    COLLISION GUARD: if two tickers would collapse to the same display string (a hypothetical
    US 'SAN' alongside 'SAN.MC'), BOTH keep their full ticker, so every displayed ticker stays
    unique. Currently there are no collisions in the 97 — see `display_ticker_collisions()`."""
    tickers = load_companies()["ticker"].tolist()
    base = {t: t.split(".")[0] for t in tickers}
    counts: dict[str, int] = {}
    for b in base.values():
        counts[b] = counts.get(b, 0) + 1
    return {t: (b if counts[b] == 1 else t) for t, b in base.items()}


@st.cache_data(show_spinner=False)
def display_ticker_collisions() -> dict[str, list[str]]:
    """{collapsed_base: [tickers that collide]} — empty when every stripped ticker is unique.
    Those tickers retain their full suffix in `display_tickers()`."""
    tickers = load_companies()["ticker"].tolist()
    groups: dict[str, list[str]] = {}
    for t in tickers:
        groups.setdefault(t.split(".")[0], []).append(t)
    return {b: ts for b, ts in groups.items() if len(ts) > 1}


@st.cache_data(show_spinner=False)
def logo_uris() -> dict[str, str]:
    """ticker -> base64 data URI for every cached logo in dashboard/logos/.

    These are TradingView symbol logos: **vector SVG**, a full-bleed square with the brand
    colour as background, meant to be clipped to a circle (the UI does that). Vector means one
    cached asset renders crisply at 26px in the table and 58px in the hero — no rasterization,
    no per-size normalization (which is why the old PNG trim/centre step is gone).

    `Path.stem` strips only the LAST suffix, so 'SAN.MC.svg' -> 'SAN.MC' and '8306.T.svg' ->
    '8306.T' — ticker names containing dots survive intact.

    Tickers with no file simply aren't in the dict; the UI falls back to a round, sector-
    coloured initials badge. Encoded once (cached) and served inline, so no static-file server
    or network access is needed at render time. Regenerate with dashboard/fetch_logos.py."""
    out: dict[str, str] = {}
    if LOGO_DIR.exists():
        for p in sorted(LOGO_DIR.glob("*.svg")):
            b64 = base64.b64encode(p.read_bytes()).decode("ascii")
            out[p.stem] = f"data:image/svg+xml;base64,{b64}"
    return out


_SVG_OPEN = re.compile(rb"(<svg\b[^>]*>)", re.I)


def _round_svg(raw: bytes) -> bytes:
    """Clip an SVG's contents to a circle, in the SVG source itself.

    Everywhere we render logos in our own HTML we round them with `border-radius:50%`. The
    Backtest holdings table is the exception: it is `st.dataframe`'s ImageColumn, drawn on a
    canvas grid that CSS cannot reach, so the icon would render square there and break the
    uniform round style. Wrapping the markup in a clipped <g> makes the ASSET round, so it is
    round no matter who paints it. Falls back to the original bytes if the shape is unexpected.
    """
    m = _SVG_OPEN.search(raw)
    if not m:
        return raw
    open_tag = m.group(1)
    body = raw[m.end():]
    end = body.rfind(b"</svg>")
    if end == -1:
        return raw
    inner, tail = body[:end], body[end:]
    # TradingView marks are a 56x56 viewport; clip to the inscribed circle.
    defs = (b'<defs><clipPath id="sd-rc"><circle cx="28" cy="28" r="28"/></clipPath></defs>'
            b'<g clip-path="url(#sd-rc)">')
    return open_tag + defs + inner + b"</g>" + tail


@st.cache_data(show_spinner=False)
def logo_uris_round() -> dict[str, str]:
    """Like `logo_uris()` but the circle is baked into the SVG — for `st.dataframe`'s canvas
    ImageColumn, which no stylesheet can round."""
    out: dict[str, str] = {}
    if LOGO_DIR.exists():
        for p in sorted(LOGO_DIR.glob("*.svg")):
            b64 = base64.b64encode(_round_svg(p.read_bytes())).decode("ascii")
            out[p.stem] = f"data:image/svg+xml;base64,{b64}"
    return out


@st.cache_data(show_spinner=False)
def logo_manifest() -> pd.DataFrame:
    """Per-ticker provenance for the cached logos (ticker, logoid, source, bytes)."""
    m = LOGO_DIR / "_manifest.csv"
    return pd.read_csv(m) if m.exists() else pd.DataFrame(
        columns=["ticker", "logoid", "source", "bytes"])


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
def load_skew() -> pd.DataFrame:
    """Skew/kurtosis of every level feature + the target (train-eligible)."""
    return pd.read_csv(EDA_DIR / "skew_table.csv")


@st.cache_data(show_spinner=False)
def load_high_corr() -> pd.DataFrame:
    """Feature pairs with |Pearson| > 0.8 — the redundancy that drove de-duplication."""
    return pd.read_csv(EDA_DIR / "high_corr_pairs.csv")


@st.cache_data(show_spinner=False)
def load_target_summary() -> pd.DataFrame:
    """Target summary stats, winsorized vs raw (train)."""
    return pd.read_csv(EDA_DIR / "target_summary.csv")


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
def risk_free_annual() -> float:
    """The rf actually used to build the target, read back from target_63d (DERIVED, never a
    literal — a pipeline rerun at a different rf cannot leave the narrative stale)."""
    with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as con:
        row = con.execute(
            "SELECT DISTINCT risk_free_annual FROM target_63d "
            "WHERE risk_free_annual IS NOT NULL"
        ).fetchone()
    return float(row[0]) if row else 0.0


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


# ------------------------------------------------------- DISPLAY-ONLY OHLC (firewalled) --- #
# A SEPARATE database file. It holds raw (unadjusted) OHLC purely to draw the Company Detail
# price chart. It is NOT part of the modelling pipeline: nothing in src/ reads it, no feature,
# target or score derives from it, and it is never joined to financials.db. The target's price
# source remains `daily_prices` (ADJUSTED close) inside financials.db — a different, and
# deliberately different, series. See dashboard/fetch_ohlc.py for the full firewall note.
OHLC_DB = ROOT / "data" / "ohlc_display.db"


@st.cache_data(show_spinner=False)
def company_ohlc(ticker: str) -> pd.DataFrame:
    """Raw OHLC for the detail chart, or an empty frame if this ticker has no cache.

    Opened READ-ONLY (`mode=ro`), and against the OHLC file only — this function is
    structurally incapable of touching the modelling database."""
    if not OHLC_DB.exists():
        return pd.DataFrame(columns=["date", "open", "high", "low", "close"])
    uri = f"file:{OHLC_DB.as_posix()}?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True) as con:
            df = pd.read_sql_query(
                "SELECT date, open, high, low, close FROM daily_ohlc "
                "WHERE ticker = ? ORDER BY date", con, params=[ticker])
    except sqlite3.Error:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close"])
    if len(df):
        df["date"] = pd.to_datetime(df["date"])
    return df


@st.cache_data(show_spinner=False)
def company_ohlc_weekly(ticker: str) -> pd.DataFrame:
    """Weekly OHLC bars for the detail chart, aggregated from the daily cache.

    ~1,640 daily rows -> ~340 weekly rows. This is a real weekly bar, not a sampled point:
    open = first open of the week, high = max high, low = min low, close = last close, and
    `date` is the LAST ACTUAL TRADING DAY in that week (not a synthetic week-end), so the
    tooltip always names a day the stock really traded. Hover values stay exact — they are
    aggregates of real prices, never interpolated.

    Why downsample: the hover hit-target needs one invisible mark per datum, so 1,640 points
    meant thousands of SVG nodes hit-tested on every mousemove. The period-change badge is
    still computed from the DAILY frame, so it is unaffected by this aggregation."""
    df = company_ohlc(ticker)
    if df.empty:
        return df
    g = df.groupby(df["date"].dt.to_period("W"))
    out = g.agg(date=("date", "last"), open=("open", "first"), high=("high", "max"),
                low=("low", "min"), close=("close", "last")).reset_index(drop=True)
    return out.dropna(subset=["close"])


@st.cache_data(show_spinner=False)
def ohlc_chart_spec(ticker: str, mode: str) -> dict:
    """Vega-Lite spec for a company's price chart, built ONCE per (ticker, theme).

    Building the Altair chart and serializing it cost ~85 ms on EVERY Streamlit rerun (47 ms
    to construct, 38 ms in `to_dict`), for a spec that only depends on the ticker and the
    palette. Caching the finished spec removes that from the rerun path entirely; the caller
    renders it with `st.vega_lite_chart`, which skips Altair's serialization step too."""
    import charts                       # local import: charts imports ui, not data
    df = company_ohlc_weekly(ticker)
    return charts.ohlc_price_line(df, mode, date_title="Week ending").to_dict()


def period_change(df: pd.DataFrame, col: str = "close") -> float | None:
    """First -> last % change over the loaded window. None if not computable."""
    if len(df) < 2:
        return None
    first, last = df[col].iloc[0], df[col].iloc[-1]
    if not first:
        return None
    return float(last / first - 1.0)


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
