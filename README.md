# Financial Instruments — Quant-Equity Strategy

A university "Financial Instruments" quantitative equity-strategy pipeline. For each company
report it extracts financial signals from SEC filings, turns them into sector-relative KPI
scores and an LLM-derived competitive-advantage ("operative") score, uses those signals to
predict the company's **forward 63-trading-day risk-adjusted return (Sharpe)**, ranks the
universe to form a long (top) / short (bottom) portfolio, and backtests under strict
look-ahead controls. Universe: **89 companies** across 9 economic sectors, from **two data
sources** (US EDGAR filers + non-US names via yfinance) unified in one database.

> **Intent & decisions** live in [`CLAUDE.md`](CLAUDE.md); the full 17-step assignment plan
> (signal formulas, scoring rubric, backtest spec) lives in
> [`docs/PROJECT_SPEC.md`](docs/PROJECT_SPEC.md).

## Pipeline at a glance

Modules in `src/` use flat imports and an `A_`/`B_`/… prefix that encodes load order.

| Step | Module | Reads | Produces |
|---|---|---|---|
| Config | `A_config.py` | — | universe, concept maps, paths (imported everywhere) |
| DB layer | `B_database.py` | — | `financial_facts` schema + read/write helpers |
| SEC client | `C_client.py` | SEC EDGAR (network) | standardized facts for `D_pipeline` |
| EDGAR extract | `D_pipeline.py` | A/B/C | **`financial_facts`** (US, `source='edgar'`) |
| Non-US ingest | `yf_ingest.py` | yfinance | **`financial_facts`** (non-US, `source='yfinance'`) |
| Prices | `price_ingest.py` | yfinance | **`daily_prices`** |
| Target | `price_target.py` | `daily_prices` + `financial_facts` | **`target_63d`** |
| KPIs | `E_kpis.py` | `financial_facts` | **`kpi_values`** |
| Scores | `F_scores.py` | `kpi_values` | **`scores`** (6 sub-scores + `financial_score`) |
| Operative | `G_operative.py` | SEC filings (LLM) | **`operative_scores`** |

Release-date integrity is checked (read-only) by `src/verify_release_dates.py`.

## Database tables (`data/financials.db`, SQLite)

- **financial_facts** — long-format fundamentals, one row per (ticker, filing, position); both sources.
- **daily_prices** — adjusted daily close per (ticker, date), each series in its own listing currency.
- **target_63d** — per (ticker, report release date): forward 63-trading-day return, volatility, Sharpe.
- **kpi_values** — raw per-report KPI ratios (long format) with a `computable` flag.
- **scores** — sector-percentile sub-scores (profitability, growth, cash_flow, leverage, efficiency, investment) + `financial_score`.
- **operative_scores** — LLM competitive-advantage score (1–5, rescaled 0–1) per filing; US 10-K/10-Q + international 20-F.

`data/financials.db` is the canonical, **versioned** dataset and is tracked in git.

### `data/ohlc_display.db` — rebuildable, NOT tracked

A **separate** SQLite file holding raw (unadjusted) OHLC, used solely to draw the dashboard's
Company Detail price chart. It is **git-ignored**: a display cache, not canonical data.

```
python dashboard/fetch_ohlc.py            # regenerate (yfinance, 2020-01-01 → today)
python dashboard/fetch_ohlc.py --report   # coverage only, writes nothing
```

It is **firewalled from the modelling pipeline** and must stay that way:

- Nothing in `src/` reads it. No feature, target or score derives from it.
- It is a separate *file*, not a table in `financials.db`, so the modelling database is never
  opened for writing — its file hash is provably unchanged by the fetch.
- `daily_prices` (**adjusted** close, in `financials.db`) remains the target's price source.
  The OHLC store is **unadjusted** on purpose, because a chart should show prices as traded.
  The two series differ numerically **by design** — do not "reconcile" them, or you corrupt
  `future_63d_sharpe`.

Without this file the dashboard degrades gracefully: the detail page falls back to the
`daily_prices` adjusted-close line, then to a caption. It never errors.

## Setup

- **Python 3.11**
- Install dependencies:
  ```
  pip install -r requirements.txt
  ```
  (A conda `environment.yaml` is also provided.)
- The operative score (`G_operative.py`) calls a LiteLLM endpoint and reads its API key from
  the **`LITELLM_API_KEY`** environment variable (never hardcode it):
  ```
  export LITELLM_API_KEY=<your key>
  ```

## Running

Pipeline scripts run from inside `src/` (flat imports). Most take `--write` (they are
read-only/dry-run without it) and are idempotent:

```
cd src
python D_pipeline.py                       # EDGAR extract -> financial_facts  (DESTRUCTIVE rebuild, network)
python yf_ingest.py --write                # non-US fundamentals -> financial_facts
python price_ingest.py --write             # daily_prices
python price_target.py --write             # target_63d
python E_kpis.py --write                   # kpi_values
python F_scores.py --write                 # scores
python G_operative.py --write --concurrency 16          # operative_scores (US 10-K/10-Q)
python G_operative.py --intl-write --concurrency 16 --since-year 2020   # operative_scores (intl 20-F)
python verify_release_dates.py             # read-only release-date check
```

> **Caution:** `D_pipeline.py` drops and rebuilds `financial_facts` from SEC on every run —
> see the rebuild cautions in `CLAUDE.md` before running it.

Diagnostics/utilities in `tools/` run from the **repo root**:

```
python tools/viewdatabase.py   # export financial_facts to outputs/financials_database_export.xlsx
python tools/price_probe.py    # read-only price-coverage probe
python tools/yf_probe.py       # read-only yfinance statement probe
```

## Status

The **data + feature layer is complete**: 89 companies across two sources, with all six
tables populated (fundamentals, prices, target, KPIs, sector-percentile scores, and the
operative LLM score for US filings + international 20-Fs). **Modelling** — assembling the
change features + training/evaluating models to predict the 63-day Sharpe, then
ranking/backtesting — is the next phase (see `docs/PROJECT_SPEC.md`).

## Repository layout

```
src/       pipeline modules (A_config … G_operative, price_ingest, price_target, yf_ingest,
           verify_release_dates)
dashboard/ Streamlit app (read-only) + fetch_logos.py, fetch_ohlc.py
tools/     non-pipeline diagnostics/utilities (run from repo root)
docs/      PROJECT_SPEC.md, WORKFLOW.txt, TASK.txt, revalidate.archived.md
data/      financials.db     (the versioned dataset; tracked in git)
           ohlc_display.db   (rebuildable display cache; git-ignored — see above)
outputs/   generated exports (git-ignored)
CLAUDE.md  project state, conventions, and decisions
```
