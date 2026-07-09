# Financial Instruments — Quant-Equity Strategy

A university "Financial Instruments" quantitative equity-strategy pipeline. For each company
report it extracts financial signals from SEC filings, turns them into sector-relative KPI
scores and an LLM-derived competitive-advantage ("operative") score, uses those signals to
predict the company's **forward 63-trading-day risk-adjusted return (excess Sharpe, risk-free
= 2%)**, ranks the universe into a long (top-10) / short (bottom-10) book, and backtests it
under strict look-ahead controls.

**Universe: 97 companies** across 9 economic sectors, from **two data sources** (US EDGAR
filers + non-US names via yfinance) unified in one database. 97 = the assignment's mandated 98
minus GOOG, a documented Alphabet dual-class dedup (GOOGL is kept; both share one SEC filer
with byte-identical fundamentals).

**The headline finding is a null result, and that is the deliverable.** Report fundamentals
show no reliable, generalizable signal for the forward 63-day Sharpe on this universe/period
(cross-validated rank-correlation ≈ 0, robust across a feature-set ablation and the universe
changes). That is what market efficiency predicts; the deliverable is the **leak-free,
end-to-end, reproducible methodology**, not alpha. Do not tune it into a positive result.

> **Intent & decisions** live in [`CLAUDE.md`](CLAUDE.md). The full 17-step assignment plan
> (signal formulas, scoring rubric, backtest spec) lives in
> [`docs/PROJECT_SPEC.md`](docs/PROJECT_SPEC.md); the lecturer's brief is
> [`docs/TASK.txt`](docs/TASK.txt).

## Quick start

```bash
pip install -r requirements.txt          # Python 3.11  (conda environment.yaml also provided)

python run_pipeline.py --offline         # recompute everything from the committed database
streamlit run dashboard/app.py           # explore the results (reads the DB + artifacts)
```

`--offline` runs the eight local stages (KPIs → scores → target → modelling table → EDA →
train → backtest → analysis) from the raw data already in `data/financials.db`. It needs no
network and no API key, and reproduces the committed numbers exactly.

## The pipeline — one command

```bash
python run_pipeline.py                    # every stage: fetch latest data, then retrain
python run_pipeline.py --offline          # local stages only (no network / API key)
python run_pipeline.py --list             # print the 12-stage plan and exit
python run_pipeline.py --from kpis --to backtest      # run a contiguous slice
python run_pipeline.py --verify           # run the invariant suite only (read-only)
python run_pipeline.py --force            # keep a content-identical DB rewrite (no restore)
```

Stages, in dependency order (`[net]` = needs the internet / an API key, skipped by `--offline`):

| # | Stage | Kind | Produces |
|---|---|---|---|
| 1 | `sec_facts`  | `[net]` | `financial_facts` (US EDGAR) |
| 2 | `yf_facts`   | `[net]` | `financial_facts` (non-US, yfinance) |
| 3 | `prices`     | `[net]` | `daily_prices` |
| 4 | `kpis`       | local | `kpi_values` |
| 5 | `scores`     | local | `scores` (6 sub-scores + `financial_score`) |
| 6 | `operative`  | `[net]` | `operative_scores` (LLM, new filings only) |
| 7 | `target`     | local | `target_63d` (forward 63-day excess Sharpe) |
| 8 | `modelling`  | local | `modelling_data` (features joined to target) |
| 9 | `eda`        | local | `eda/` |
| 10 | `train`     | local | `predictions/` (CV, ensemble, ablation) |
| 11 | `backtest`  | local | `predictions/` (walk-forward long/short) |
| 12 | `analysis`  | local | `analysis/` (bias-variance, importance, classification) |

**Ingestion is append-only and idempotent.** A re-fetch upserts on the fundamentals' unique
key and never drops a table: historical rows — including the non-US yfinance rows and any
adjudicated value — are never deleted. Restatements are overwritten **and logged** old→new;
rows a re-fetch no longer produces are kept **and reported** as orphans.

**The LLM stage is key-guarded.** `operative` reads its key from the `LITELLM_API_KEY`
environment variable (never hardcode it). With no key and new filings it warns and skips them
(they fall back to the financial score), so a run still completes.

```bash
export LITELLM_API_KEY=<your key>        # only needed to score NEW filings live
```

**A no-op run leaves the tracked database byte-clean.** Because every write is
`INSERT OR REPLACE` (which resets `id`/`created_at`), a content-identical rerun would still
rewrite the 30 MB file. The pipeline snapshots the DB before the run and restores it
byte-for-byte when the post-run content is unchanged (`--force` keeps the rewrite instead).
The snapshot doubles as a rolling backup at `data/financials.db.bak_auto` (git-ignored).

## Database tables (`data/financials.db`, SQLite, git-tracked)

- **financial_facts** — long-format fundamentals, one row per (ticker, filing, position); both sources.
- **daily_prices** — adjusted daily close per (ticker, date), each series in its own listing currency.
- **target_63d** — per (ticker, report release date): forward 63-day excess Sharpe (rf = 2%), return, volatility.
- **kpi_values** — raw per-report KPI ratios (long format).
- **scores** — sector-percentile sub-scores (profitability, growth, cash_flow, leverage, efficiency, investment) + `financial_score`.
- **operative_scores** — LLM competitive-advantage score (1–5, rescaled 0–1) per filing; US 10-K/10-Q + international 20-F.

`data/financials.db` is the canonical, **versioned** dataset.

### `data/ohlc_display.db` — rebuildable, NOT tracked, firewalled

A **separate** SQLite file holding raw (unadjusted) OHLC, used solely to draw the dashboard's
Company Detail price chart. It is **git-ignored** — a display cache, not canonical data — and
**firewalled from the modelling pipeline**:

- Nothing in `src/` reads it; no feature, target or score derives from it (an invariant the
  proof harness enforces).
- It is a separate *file*, not a table in `financials.db`, so the modelling DB is never opened
  for writing during the fetch — its file hash is provably unchanged.
- `daily_prices` (**adjusted** close) remains the target's price source. The OHLC store is
  **unadjusted** on purpose (a chart shows prices as traded); the two series differ by design.
  Do not reconcile them, or you corrupt the target.

```bash
python dashboard/fetch_ohlc.py            # regenerate (yfinance, 2020-01-01 → today)
python dashboard/fetch_ohlc.py --report   # coverage only, writes nothing
```

Without this file the dashboard degrades gracefully to the `daily_prices` line, then a caption.

## Where results land

- `eda/` — feature→target correlation, distributions, VIF, missingness.
- `predictions/` — CV & test metrics, coefficients/importances, `predictions_all.csv` (the full
  97-name ranking), the backtest, `MODEL_SUMMARY.md`.
- `analysis/` — the slide-24 grading items: bias-variance & learning curves, feature
  importance, the classification lens.

The Streamlit dashboard reads the database plus these three directories and **writes nothing**.

## Proof harness — reproducibility you can check

The pipeline is deterministic (fixed seeds), so behavior can be verified, not assumed:

```bash
python src/fi/verify.py --check proofs/baseline.json   # content of all 7 tables + all
                                                        # artifacts vs a recorded baseline
python src/fi/verify.py                                 # the load-bearing invariants only
```

`verify.py` fingerprints every table (excluding volatile `id`/`created_at`) and every generated
artifact, and asserts the project's invariants: the 97-universe + GOOG dedup, look-ahead safety,
the rf = 2% audit identity, the OHLC firewall, the long/short sign convention, append-only
ingest, and the near-null result itself. `run_pipeline.py` runs the invariants at the end of
every run.

## Repository layout

```
run_pipeline.py   the single entry point (thin shim into fi.pipeline)
src/fi/           the pipeline package:
                    config, concepts   universe, sector maps, us-gaap/iXBRL concept tables
                    db                 SQLite schema + read/write helpers
                    sec, market        network ingest (EDGAR + yfinance)
                    operative          the LLM competitive-advantage score (only paid stage)
                    features           KPIs, sector scores, target, modelling table
                    modelling          EDA, training, backtest, slide-24 analysis
                    pipeline           the stage registry + CLI
                    verify             the proof harness (fingerprints + invariants)
dashboard/        Streamlit app (read-only) + fetch_logos.py, fetch_ohlc.py
tools/            non-pipeline diagnostics (run from repo root): viewdatabase, price_probe,
                  yf_probe, verify_release_dates
docs/             PROJECT_SPEC.md, TASK.txt; archive/ (superseded notes)
proofs/           baseline.json — the recorded content fingerprint
data/             financials.db (versioned) · ohlc_display.db (rebuildable, git-ignored)
CLAUDE.md         project state, conventions, and decisions
```
