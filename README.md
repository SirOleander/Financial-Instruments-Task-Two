# SIGNAL DESK — Quant Equity Strategy
### Financial Instruments · Task 2 — Report-Signal Stock Selection

A leak-free pipeline that tests whether fundamental and qualitative signals extracted from
company reports can predict forward risk-adjusted returns (63-trading-day Sharpe), ranks the
mandated universe into a long/short book, and backtests it under strict out-of-sample controls.

**Headline finding:** across every angle — feature correlations, out-of-sample model
performance, a feature-set ablation, a classification cross-check, and a walk-forward backtest
— there is **no reliable, exploitable signal**. This near-null result is reported honestly and
is consistent with market efficiency. **The deliverable is the leak-free methodology, not
alpha.**

---

## Quick start

### 1. Environment
Requires **Python 3.11**.

```bash
pip install -r requirements.txt
```

### 2. Reproduce the committed results (recommended first step — fast, no network)
The repository ships with the verified dataset (`data/financials.db`). This command re-runs the
full compute chain against it and reproduces every result **byte-for-byte**, with no data fetch:

```bash
python run_pipeline.py --offline
```

Expected output: `RESULT: ALL GREEN`, all invariants pass, database unchanged. Runs in a few
minutes.

### 3. View the dashboard
```bash
streamlit run dashboard/app.py
```
Opens an interactive dashboard (Ranking · Model · Data · Backtest · per-company detail) at
`http://localhost:8501`.

### 4. (Optional) A fresh live build from scratch
To rebuild the entire project from live data (fetches the latest SEC/yfinance data, re-scores,
retrains, updates the ranking):

```bash
python run_pipeline.py
```

**Note:** this requires internet access and an LLM API key (see below), takes **~3–4 hours**
(dominated by the LLM scoring stage), and produces **updated results** because live data has
moved since the committed build. Use `--offline` if you want to reproduce the committed
numbers instead.

---

## The LLM API key (only needed for a live run)

The qualitative "competitive-advantage" scoring stages call an LLM via a LiteLLM endpoint. To
run these stages live, set an environment variable pointing to your own key:

```bash
export LITELLM_API_KEY="your-key"      # bash / git-bash
# or PowerShell:  $env:LITELLM_API_KEY = "your-key"
```

If the key is **not** set, the pipeline still completes: the operative stages log a warning and
fall back to the financial score for un-scored filings (graceful degradation, no crash). The
committed `data/financials.db` already contains the operative scores, so **`--offline` needs no
key.**

---

## What the pipeline does (stage by stage)

`python run_pipeline.py --list` prints the ordered plan. The stages, in order:

| Stage | What it does |
|-------|--------------|
| `sec_facts` | Ingest US fundamentals from SEC EDGAR (10-K / 10-Q), append-only |
| `yf_facts` | Ingest international fundamentals via yfinance |
| `prices` | Ingest daily adjusted prices (all names) |
| `kpis` | Compute financial KPIs (margins, returns, growth, leverage, …) |
| `scores` | Sector-relative percentile scores (six sub-scores + aggregate) |
| `operative` | LLM competitive-advantage score for US filings |
| `operative_intl` | LLM competitive-advantage score for international 20-F filings |
| `target` | Forward-63-trading-day Sharpe, strictly after report release |
| `modelling` | Assemble the leak-safe modelling table |
| `eda` | Exploratory analysis (distributions, correlations, VIF, missingness) |
| `train` | Train + tune the models, produce the ranking |
| `backtest` | Walk-forward long-short backtest |
| `analysis` | Error analysis, feature importance, classification metrics |

Useful flags:
- `--offline` — skip network stages; recompute from the existing database (reproduces results)
- `--from <stage> --to <stage>` — run a slice of the pipeline
- `--list` — print the stage plan without running
- `--verify` — run the structural + integrity invariants only
- `--force` — rewrite outputs unconditionally (bypass skip-if-unchanged)

---

## Method summary

- **Universe:** 97 of the 98 mandated stocks. The one deviation is a documented deduplication —
  GOOG (Alphabet Class C) removed, GOOGL (Class A) kept, as they are the same company / economic
  exposure. All 97 are processed and ranked.
- **Target:** the Sharpe ratio of each stock over the 63 trading days **after** a report's
  release. Excess return uses a constant risk-free rate of **2%** (≈ average 3-month US Treasury
  bill yield over the sample, FRED series TB3MS), converted to the daily horizon.
- **Features:** six sector-relative sub-scores + an LLM competitive-advantage score (kept
  separate — the model learns their relative importance, no weight is hardcoded) + de-duplicated
  financial KPIs + same-frequency *change* features.
- **Models:** Ridge, Lasso, ElasticNet, RandomForest, XGBoost, SVR — combined into an
  **ensemble** (unweighted mean of the best three non-degenerate models: SVR + XGBoost +
  RandomForest). The ensemble produces the final ranking and drives the backtest.
- **Leak-safety (central to the project):** look-ahead-safe release dates; a time-based train /
  test split (test touched once); `TimeSeriesSplit` cross-validation with a purge gap; all
  preprocessing (winsorization, scaling, imputation) refit **inside each fold**; the newest
  reports correctly receive no target until their 63-day forward window completes.
- **Backtest:** equal-weight top-10 long / bottom-10 short, ~63-day hold, quarterly rebalance,
  transaction costs (0 / 5 / 10 bps), walk-forward, strictly out-of-sample.

### Result
- Out-of-sample rank correlation ≈ 0 (max single-feature |Spearman| ≈ 0.08).
- Robust across feature-set ablations.
- Classification cross-check (top- vs bottom-third Sharpe): AUC ≈ 0.52 (chance).
- Backtest long-short spread not statistically distinguishable from zero.

All consistent, all pointing to the same honest near-null conclusion.

---

## Repository layout

```
run_pipeline.py        Single pipeline entry point (thin shim → src/fi/pipeline.py)
src/fi/                The pipeline package
  config.py            All constants: universe, sectors, risk-free rate, paths
  concepts.py          US-GAAP / iXBRL concept maps (data)
  db.py                Database connection, schema, upsert, skip-if-unchanged
  sec.py               SEC EDGAR client + fundamentals extraction
  market.py            yfinance fundamentals + daily prices
  operative.py         LLM competitive-advantage scoring
  features.py          KPIs, scores, target, modelling table
  modelling.py         EDA, training, backtest, analysis
  pipeline.py          Stage registry, ordering, logging, CLI
  verify.py            Proof harness + integrity invariants
dashboard/             Read-only Streamlit dashboard (presentation layer)
tools/                 Standalone diagnostics
docs/                  Project spec, task brief, archived notes
data/
  financials.db        The versioned, verified dataset (tracked)
  ohlc_display.db      Rebuildable price-chart cache (gitignored; rebuild via
                       dashboard/fetch_ohlc.py)
predictions/           Model outputs (ranking, metrics, backtest)
eda/                   EDA figures + tables
analysis/              Error analysis, feature importance, classification
```

---

## Notes for evaluation

- **Every result is reproducible** from the committed database via `python run_pipeline.py
  --offline` — no network or key required.
- **The dashboard reads artifacts only** — it computes nothing and never modifies the pipeline
  data.
- **The stock-price charts** in the company-detail view read a separate, firewalled database
  (`ohlc_display.db`) that never touches the modelling data. If it is absent (e.g. a fresh
  clone), those charts fall back gracefully to the adjusted-close line.
- **The result is intentionally near-null** and reported straight; it is not tuned toward a
  positive outcome.