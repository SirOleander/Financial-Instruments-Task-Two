"""
data.py — cached, READ-ONLY data access for the Signal Desk dashboard.

Reads data/financials.db (and later the eda/ + predictions/ artifacts). Computes nothing,
never writes. Stage 1 only needs the company universe for the sidebar.
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


@st.cache_data(show_spinner=False)
def logo_uris() -> dict[str, str]:
    """ticker -> base64 data URI for every cached logo in dashboard/logos/. Tickers with
    no file simply aren't in the dict (the UI falls back to the styled badge). Encoded once
    (cached), served inline so no static-file server / network is needed at render time."""
    out: dict[str, str] = {}
    if LOGO_DIR.exists():
        for p in sorted(LOGO_DIR.glob("*.png")):
            b64 = base64.b64encode(p.read_bytes()).decode("ascii")
            out[p.stem] = f"data:image/png;base64,{b64}"
    return out


@st.cache_data(show_spinner=False)
def load_ranking() -> pd.DataFrame:
    """The model's predicted forward-63d-Sharpe ranking (predictions_all89.csv), joined to
    company name + logo, sorted best-to-worst. Read-only; computes nothing new."""
    df = pd.read_csv(PRED_DIR / "predictions_all89.csv")
    names = load_companies().set_index("ticker")["name"]
    df["name"] = df["ticker"].map(names)
    df = df.sort_values("rank_ensemble").reset_index(drop=True)
    n = len(df)
    df["basket"] = ["LONG" if r <= 10 else "SHORT" if r > n - 10 else ""
                    for r in df["rank_ensemble"]]
    return df


@st.cache_data(show_spinner=False)
def load_cv() -> pd.DataFrame:
    return pd.read_csv(PRED_DIR / "cv_results.csv")


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


def eda_fig(name: str) -> str:
    """Absolute path to an eda/ figure PNG (for st.image)."""
    return str(EDA_DIR / name)


@st.cache_data(show_spinner=False)
def universe_meta() -> dict:
    """Small headline facts for the header band."""
    df = load_companies()
    return {
        "n_companies": int(df["ticker"].nunique()),
        "n_sectors": int(df["sector"].nunique()),
        "n_intl": int(df["is_intl"].sum()),
    }
