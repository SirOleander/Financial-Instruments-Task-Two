# CLAUDE.md — Financial Instruments quant-equity pipeline

Read this fully before doing anything. It is the source of truth for project state,
conventions, and what has already been decided. Files in `src/` are the ground truth
for behavior; this file is the ground truth for *intent*. The full assignment-level
plan (17 steps, all signal formulas, scoring rubric, backtest spec) lives in
`docs/PROJECT_SPEC.md` — read that before any modelling-phase work; do NOT inline it
here.

================================================================================
## MILESTONE — data-acquisition phase COMPLETE (append/update; supersedes older
## "72 tickers / EDGAR-only" statements below where they conflict)
================================================================================

### Final universe: 89 companies, TWO sources in one `financial_facts` table
- **71 EDGAR** (US, `source='edgar'`) + **18 yfinance** (non-US, `source='yfinance'`).
- Dropped from earlier lists: **GOOG** (kept GOOGL — same company, identical
  fundamentals, avoided double-counting Alphabet), **0700.HK (Tencent)** and
  **9988.HK (Alibaba)** (too little usable history). Also never included:
  RHHBY, ALV.DE, MC.PA, NESN.SW, CBA.AX, GEV (insufficient data / no release dates).
- `financial_facts` ≈ 25,686 rows. EDGAR portion verified unchanged across the
  yfinance/price work (23,898 rows / 71–72 tickers baseline).
- The two sources are UNIFIED for scoring: non-US names rank inside the SAME sector
  peer groups as US names. `source` is provenance only, not a grouping key.

### yfinance ingest (src/yf_ingest.py) — separate retrieval, own rules
- All KPIs are ratios and the target uses returns, so **no FX conversion anywhere**;
  each row stores its native `reporting_currency`.
- **No de-cumulation** on yfinance rows (yfinance quarterly is already discrete, not
  YTD — unlike EDGAR 10-Qs).
- Capex normalized to POSITIVE to match EDGAR convention.
- `total_debt` added as a DATA position (schema has short/long debt but no total_debt);
  leverage KPIs use total_debt when present else short+long. Tencent (dropped) was the
  only name using the lease-debt short/long lines.
- Missing positions marked `selection_status='missing'` (never fabricated 0).
- Idempotent upsert via synthetic accession `YF-<ticker>-<A|Q>-<period_end>`.
- Non-US history is SHALLOW: ~4 annual + ~5 quarterly per name, so most have only
  1–3 change-eligible quarters → non-US is effectively an ANNUAL-frequency contribution.
- Banks: yfinance does NOT expose noninterest_expense (summed), total_loans,
  total_deposits, allowance_for_credit_losses for ANY of the 5 non-US banks. Decision:
  score the WHOLE bank sector (US + non-US) on the common set both sources have
  (ROA, ROE, NIM, revenue/NI growth, equity_to_assets, capital_retention); efficiency_
  ratio / loan_growth / deposit_growth / provision_coverage are DROPPED from the bank
  framework and noted as a limitation. 4 names (0700 dropped, HSBA, 8306, SAN) have no
  quarterly cash flow → quarterly OCF/capex/dividends missing (rows still created).

### Release dates — VERIFIED look-ahead-safe for both sources (t=0 for the target)
- EDGAR: `report_release_date` was already populated for all rows; a fresh SEC pull
  (us_release_dates.py) confirmed 1,542/1,542 match SEC filingDate EXACTLY, 0
  mismatches. US release dates are proven correct.
- yfinance: release date = earnings-announcement date from get_earnings_dates, matched
  as the earliest announcement strictly AFTER each period-end (pre-period-end match
  structurally impossible); 100% coverage on kept periods.
- `fiscal_period_end_date` is period-end and is NOT the target's t=0 — always use
  `report_release_date`.

### Two NEW tables (additive; `financial_facts` untouched by both)
- **daily_prices** (ticker, date, adjusted_close, currency, source; PK (ticker,date)).
  src/price_ingest.py. 144,632 rows across 89 tickers, uniform start 2020-01-01 → today,
  yfinance auto_adjust=True. Each series in its OWN listing currency, never converted,
  never mixed. TSM kept as the ADR ticker 'TSM' (USD) — local 2330.TW has weaker
  yfinance coverage. London names are in GBp (pence): harmless for returns (cancels),
  but do NOT mix GBp price with GBP share counts if any market-cap/price-level KPI is
  ever built.
- **target_63d** (PK (ticker, report_release_date); has fiscal_period_end_date, source).
  src/price_target.py. t+1 = first trading day strictly AFTER release on each stock's
  OWN calendar (count 63 ROWS forward in that stock's own series — never a shared US
  calendar). future_63d_sharpe = mean(daily ret t+1..t+63)/std·√252, risk-free = 0
  (stated simplification; negligible effect on within-period rankings). 1,573 real
  targets + 89 NULL (each company's most-recent report, forward window incomplete —
  fill naturally on idempotent re-run). Sharpe median +0.74, range −5.56…+7.49.
  CAUTION for modelling: extreme Sharpe tails may be low-vol-window artifacts —
  consider winsorizing the target tails and sanity-check a couple of extremes for
  near-zero-std denominators.

### STATUS: data acquisition DONE. Next = the ANALYTICAL pipeline (none built yet)
1. **KPIs** from raw fundamentals (ratios per PROJECT_SPEC §2.3). Zero-denominator /
   missing rule: treat `selection_status=='missing'` as NOT-COMPUTABLE — never
   `value==0`, never mean-fill.
2. **Sector-percentile scoring** → 6 sub-scores → financial_score, drop-and-renormalize
   for missing KPIs (this is what yields NO-NaN scores WITHOUT imputation). Orient
   higher=better, sign-flip inverse KPIs.
3. **Operative LLM score** (greenfield): per (ticker, report), feed MD&A/Business/Risk
   of THAT filing to an API, return 1–5 → (score−1)/4 = strategic_score. Hard rules:
   look-ahead (only that filing's text, forbid outside knowledge), reproducibility
   (temp 0, record model version, cache by accession), persist score+rationale+
   confidence; missing sections → competitive_advantage_score falls back to
   financial_score.
4. **Change features** (current − prior absolute, drop each company's first obs).
5. **Assemble modelling table** joining features + target on (ticker, report_release_date).
6. **Uniform min-observations floor** (governs young US names PLTR/APP/UBER/NOW too),
   then time-based split (test set untouched), then train/evaluate/ensemble/rank/backtest.
7. Resolve the OPEN DECISIONS in PROJECT_SPEC (regression vs classification; the
   competitive_advantage weight w; free_cash_flow_after_capex_margin definition).

### MODELLING TABLE — BUILT (src/H_modelling.py → table `modelling_data`, 1662 rows/89 tickers)
Additive-only (six source tables proven UNCHANGED). One row per (ticker,
report_release_date); features joined to target STRICTLY on that key (spine = `scores`,
whose key set is proven identical to `target_63d`). `python H_modelling.py` = STEP-1
dry-run/report; `--write --floor=6` = build. Idempotent (INSERT OR REPLACE on the PK).
Settled decisions baked in:
- **Regression** on `future_63d_sharpe` (no classification labels).
- `financial_score` and `operative_score` are SEPARATE features (model learns their
  weight). `competitive_advantage_score_w050` = 0.5·fin + 0.5·op is a REPORTING column
  ONLY (falls back to financial_score where operative missing) — NOT a model feature.
- **Operative join = look-ahead-safe.** US names: exact same-date match. The 8
  conventional internationals (TSM/SAP/7203.T/6758.T/AZN/NOVN/NOVO/8306.T): as-of match to
  the most recent 20-F operative filed ON OR BEFORE the report release date (their yfinance
  scoring dates never coincide with the 20-F filing date; strict same-date would orphan all
  56 recovered rows). Integrated 20-F (ASML/SHEL/SAN, status=missing) and no-20-F names
  stay NULL + `operative_missing=1`. Coverage: 1496 exact / 56 asof_20f / 110 NULL.
  Provenance stored per row: `operative_match`, `operative_asof_date`.
- **Change features = same-FREQUENCY prior** (annual diffs prior annual, quarterly prior
  quarterly) because financial_score is a WITHIN-frequency percentile — cross-freq diffs
  would mix ranking populations. `first_obs=1` = no same-freq prior (178 rows = 2×89);
  their change features are NULL.
- **Winsorization** of ratio-tails (ROIC, cash_conversion, *_growth_yoy) and target
  (future_63d_sharpe) at 1st/99th pct; BOTH `_raw` and clipped columns kept.
- **`train_eligible` flag = the min-obs floor, applied as RETAIN-NOT-DELETE.** Floor=6
  train-usable rows (target AND same-freq change) per company. **71 US names qualify →
  1308 train_eligible rows.** The **18 internationals are RETAINED** in modelling_data
  (all rows `train_eligible=0`, 141 rows) so the trained model can still SCORE them for the
  final ranking — held out of TRAINING only, because their 4–5-row histories are too thin
  and structurally annual-only. 354 rows total are train_eligible=0 (internationals +
  every first_obs / target_missing US row). All 89 companies remain in the table.
- **CAVEAT — winsor caps refit at split (leakage).** Caps are currently fit on the FULL
  population. At the time-based train/test split they MUST be refit on the TRAINING rows
  ONLY (train_eligible=1, pre-split) and re-applied — otherwise the test set leaks into the
  caps. This is the NEXT step's responsibility, not done here.

### FEATURE SET — DECIDED post-EDA (src/I_eda.py, artifacts in eda/, readout eda/EDA_SUMMARY.md)
EDA ran on TRAIN-ELIGIBLE rows only (n=1308 / 71 US names). It is READ-ONLY (writes only
`eda/` figures+CSVs, dashboard-consumable; a later Streamlit app consumes them). Signal is
weak by nature: max |Spearman| among well-populated (n≥800) features vs future_63d_sharpe is
~0.075 (net_margin_change) — this is a MULTIVARIATE/ensemble problem, not a single-feature
one. `python I_eda.py` regenerates all artifacts. The feature choices below are a SELECTION
of existing modelling_data columns (NOT a schema change):

**USE as model features:**
- **The six sub-scores** (profitability/growth/cash_flow/leverage/efficiency/investment) —
  NOT financial_score.
- **operative_score** (kept separate; model learns fin-vs-operative weight).
- **De-duplicated KPIs (17, broadly populated):** gross_margin, operating_margin,
  return_on_assets, return_on_equity, revenue_growth_yoy, operating_income_growth_yoy,
  net_income_growth_yoy, operating_cash_flow_growth_yoy, operating_cash_flow_margin,
  cash_conversion, debt_to_assets, cash_to_assets, equity_ratio, asset_turnover,
  capex_intensity, r_and_d_intensity, ROIC.
- **The *_change** of each retained sub-score/operative/KPI (same-frequency change; already
  in the table). Change features carry as much of the (thin) signal as levels.
- **Sector-specific, only where computable:** inventory_turnover (Disc/Staples/Ind).

**DROP as model features (columns stay in the table, just unused):**
- `financial_score` and `competitive_advantage_score_w050` — the latter stays a REPORTING
  column only.
- **5 exact by-construction identities** (VIF=inf; drop the derived one): financial_score =
  mean(6 sub-scores); cas_w050 = 0.5·fin+0.5·op; free_cash_flow_margin =
  operating_cash_flow_margin − capex_intensity; net_debt_to_assets = debt_to_assets −
  cash_to_assets; reinvestment_rate = r_and_d_intensity + capex_intensity. (All verified to
  machine-epsilon residual.)
- **>0.8 redundant pairs (drop one):** operating_income_to_assets (~0.96 with ROA →
  keep ROA); net_margin (~0.90 with operating_margin → keep operating_margin).
- **Unreliable sparse bank-only KPIs — RETAINED but NOT primary features:**
  net_interest_margin (n=144), capital_retention (n=32). Their large raw target correlations
  are small-subsample artifacts, not deployable signal.

**Cautions for modelling:**
- **Sub-score/KPI overlap:** the six sub-scores ARE percentile aggregations of these KPIs, so
  the sub-score block and KPI block structurally overlap. Prefer regularized (ridge/lasso) or
  tree models, and/or run a sub-scores-only vs KPIs-only ablation; do NOT read linear
  coefficients naively.
- **Sector is NOT a predictive feature.** Forward-Sharpe medians differ IN-SAMPLE across
  sectors (Banks +1.27 vs Financial Services/Healthcare ≈ +0.31/+0.32 median). That is
  in-sample dispersion, not a look-ahead-safe signal — do NOT feed sector identity, sector
  one-hots, or sector means to the model. Sector stays a GROUPING key for scoring only.
- **Winsor caps refit train-only at split** (caps in the table were fit on the full
  train-eligible set for EDA/assembly) — already flagged in the modelling-table block.

### MODELLING + BACKTEST RESULT — NEAR-NULL AND ROBUST (src/J_models.py, src/K_backtest.py)
**The honest finding: report fundamentals show NO reliable, generalizable signal for the
forward 63-day Sharpe on this universe/period. This is the RESULT, not a bug — do NOT try to
tune it into a positive one.** It is exactly what market efficiency predicts, and the
DELIVERABLE is the leak-free end-to-end methodology, not alpha. Preserve this conclusion.
- **Pipeline (J_models.py):** time split at 2025-03-31 (train+val 1023 rows ≤ split; untouched
  12-month test 285 rows > split, touched once). TimeSeriesSplit CV (5 folds, purge gap=21) on
  train+val. ALL preprocessing refit per fold inside a Pipeline (ratio-tail + change
  winsorization from train-fold caps — NOT the table's full-pop caps; median impute; z-scale
  for linear/SVR; per-fold target winsor via TransformedTargetRegressor). Roster: Ridge, Lasso,
  ElasticNet, RandomForest, XGBoost, SVR with modest regularization-focused grids. Selection
  metric = Spearman (ranking task).
- **Numbers:** EDA max |Spearman| ~0.075. CV Spearman ∈ [−0.038,+0.011] (std ~0.07–0.10 ≫
  means) = indistinguishable from zero. Test Spearman ~0 to slightly negative. Top-vs-bottom
  realized-Sharpe spreads FLIP SIGN across models. Lasso/ElasticNet regularize to the
  CONSTANT/null model (flagged, excluded from ensemble). Ensemble = best-3 non-degenerate
  (SVR+RF+XGB); does not beat individuals.
- **Ablation (the one pre-committed robustness check, `--ablation`):** sub-scores-only vs
  KPIs-only vs full. Across all 18 cells max |CV Spearman|=0.041, max |test Spearman|=0.092 —
  no feature family lifts rank-corr above noise. Null is robust to feature choice.
- **Backtest (K_backtest.py):** ensemble frozen on train+val, walked forward over 4 quarterly
  rebalances (top-10 long / bottom-10 short, equal weight, ~63d hold, costs 0/5/10bps,
  internationals included+flagged). Per-rebalance long-short +0.15/−0.05/−0.21/+0.13 (sign-
  flipping); cumulative LS ≈ −2.1% gross (−3.3% @10bps), ann Sharpe ~0.07, maxDD ~−25%. Both
  legs rose ~+50% in a bull market (universe +43%); the strategy adds no spread. 4 rebalances
  ⇒ high-variance, do not over-interpret.
- Artifacts (dashboard-consumable) in `predictions/`: cv_results, test_metrics,
  ablation_results, coef_/importance_*, predictions_all89, backtest_periods/holdings/summary,
  fig_backtest_equity.png, MODEL_SUMMARY.md, BACKTEST_SUMMARY.md.

### Modelling-stage handling still pending (unchanged from before)
- Negative book equity (MCD/PM/BKNG/ABBV): exclude ROE/equity_ratio or floor denom.
- HealthA pharma gross margin (ABBV amortization-in-COGS): decide rev−cost consistent
  vs drop gross_margin for HealthA — applies to the non-US pharma (AZN/NOVN/NOVO) too,
  since they rank in the same Healthcare pool.
- **Winsorize ratio-tail KPIs at modelling time**: ROIC, cash_conversion, and the
  *_growth_yoy KPIs carry extreme ±1000s outliers from near-zero denominators (invested
  capital / net income / prior-year base ≈ 0) — clip their tails before training or they
  dominate the model. (Same rationale as the target-winsorization caution above.)
- **free_cash_flow is a LEVEL in native currency** (KRW/JPY/EUR trillions for non-US
  names): use free_cash_flow_MARGIN cross-sectionally, NEVER the raw level. The level is
  not in any sub-score today; this matters only if it ever becomes a model feature.

## What this project is

A university "Financial Instruments" quantitative equity strategy. The pipeline:
extract financial signals from SEC filings → compute sector-specific KPI scores →
predict a forward 63-trading-day Sharpe → rank companies long (top 10) / short
(bottom 10) → backtest. Two phases:
  - **Extraction + validation** — effectively CLOSED (this file's main subject).
  - **Modelling** — the active next phase; see `docs/PROJECT_SPEC.md` and the
    "Modelling phase" section below.

Universe: 72 tickers across 13 implementation groups (= 9 economic sectors), 7 fiscal
years fetched, latest period ~2026-05-31. A clean validator run currently produces
~700 flags, almost all pre-adjudicated as benign (see the ledger below).

## Repo layout (modules live in `src/`)

- **A_config.py** — companies, CIKs, sectors, `COMPANY_GROUPS` (TechA–D, BankA,
  FinA, CommA, DiscA, StapA, HealthA, IndA, EnergyA, EnergyB),
  `FINANCIAL_ITEMS_BY_GROUP` (us-gaap concepts), `INLINE_FINANCIAL_ITEMS_BY_TICKER`
  (iXBRL fallbacks), `CALCULATED_FINANCIAL_ITEMS`, `FINANCIAL_POSITION_SIGN_RULES`,
  `FISCAL_YEARS_TO_FETCH = 7`, `validate_config()`.
  `DATABASE_PATH = BASE_DIR/data/financials.db`, where `BASE_DIR` is the parent of
  `src/`. `DECUMULATE_YTD_TICKERS` is now **dead/unused** — leave or delete.
- **B_database.py** — SQLite at `data/financials.db`; one `financial_facts` table,
  long format (one row per ticker/filing/position). `get_connection()` uses
  `sqlite3.Row`. Unique index = (ticker, accession_number, position,
  extraction_method). Missing values are stored as `0`, but
  `selection_status == 'missing'` is what marks a real gap — never infer "missing"
  from `value == 0`.
- **C_client.py** — SEC fetch/parse. Year-based, FYE-aware accession selection;
  `select_best_fact`; `apply_calculated_financial_items`; `build_standardized_rows`.
  Contains the annual-duration floor fix (see "The ABBV/KLAC/GE fix" below).
- **D_pipeline.py** — orchestration. `main()` calls
  `create_tables(drop_existing=True)`, so **every run rebuilds the entire table**.
  `TARGET_GROUPS` must list every group you want to keep or the rest get wiped; it
  currently lists all 13.
- **verify_release_dates.py** (formerly `debug.py`) — read-only release-date verifier:
  confirms each EDGAR `report_release_date` == SEC filingDate against `us_release_dates.csv`.
  The old 4-layer *data* validator has been **RETIRED** now the data phase is closed
  (see "The validator — RETIRED" below); it no longer writes `validation_flags.csv` /
  `concept_map.csv` (those files were deleted).
- **Analytical modules** (built after extraction; details in `docs/PROJECT_SPEC.md`):
  `E_kpis.py` (raw KPIs → `kpi_values`), `F_scores.py` (sector-percentile sub-scores →
  `scores`), `G_operative.py` (LLM competitive-advantage score → `operative_scores`;
  US 10-K/10-Q + intl 20-F), `price_ingest.py` (`daily_prices`), `price_target.py`
  (`target_63d`).
- **tools/** — non-pipeline diagnostics/utilities, OUTSIDE the flat-import path (each
  adds a `sys.path` shim to reach `src/`): `price_probe.py`, `yf_probe.py`,
  `viewdatabase.py` (Excel export → `outputs/`, uses `A_config.DATABASE_PATH`).
- **docs/** — `PROJECT_SPEC.md`, `WORKFLOW.txt`, `TASK.txt`, and
  `revalidate.archived.md` (the RETIRED re-validation routine, archived for reference).

Scripts use flat imports (`import A_config`), so run pipeline scripts from inside `src/`:
```
cd src
python D_pipeline.py            # full rebuild — DESTRUCTIVE, see cautions
python verify_release_dates.py  # read-only release-date check (needs us_release_dates.csv)
```
(`tools/` scripts run from the repo root, e.g. `python tools/viewdatabase.py`.)

## CRITICAL cautions

1. `main()` is `drop_existing=True` → a full 13-group rebuild every run. Make **all**
   config edits *before* a single rebuild. Confirm `TARGET_GROUPS` still lists all 13
   groups before running.
   **Finality:** `TARGET_GROUPS` matters *only* at rebuild time, and any group not in
   it when `D_pipeline.py` runs is dropped from the DB with **no warning and no
   recovery short of re-fetching**. Never narrow `TARGET_GROUPS` for a "focused" run —
   a single-group rebuild silently nukes the other 12. To work on one group, rebuild
   all 13 and filter downstream.
2. Re-confirm the **AXP `total_loans`** value survives any rebuild (see Adjudications).
   It has been silently wiped by a rebuild before.
3. Prefer read-only diagnostics before any destructive write. Prefer targeted patches
   over whole-file replacements. Always be explicit about which file a change goes in
   (pipeline vs config vs client vs validator).
4. Network: a full rebuild fetches from SEC. The validator and any DB diff are offline.

## The validator — RETIRED (was `debug.py`; four layers, kept for reference)

**RETIRED:** the 4-layer *data* validator has been retired now the extraction/data phase
is closed. `debug.py` is now `verify_release_dates.py` (release-date check only), and no
file writes `validation_flags.csv` / `concept_map.csv` anymore (both deleted). The four
layers are documented here so the benign-flag ledger below stays interpretable and a
validator can be regenerated from the ledger + per-name adjudications if a future EDGAR
rebuild needs re-validation.

1. **Coverage** — missing (ticker, position) via `selection_status`.
2. **Identities** — gross_profit = rev − cost (FAIL); net_income ≈ pretax − tax
   (REVIEW); operating ≤ gross; margins in [0,1]; debt ≤ assets; equity_ratio ≤ 1;
   cash ≤ assets; total_loans = sum(components).
3. **Anomalies** — scale jump 50× median (FAIL); duration bands 10-K 300–450 /
   10-Q 70–120 (REVIEW); value frozen across ≥4 filings (REVIEW).
4. **Concept audit** — concept drift >1 concept (REVIEW); heavy fallback >50%
   (REVIEW). Also writes `concept_map.csv` for an eyeball plausibility check.

Tolerances: `REL_TOL=0.01`, `ABS_TOL=100_000`, `SCALE_JUMP_FACTOR=50`,
`FROZEN_MIN_FILINGS=4`, `ANNUAL_DURATION=(300,450)`, `QUARTERLY_DURATION=(70,120)`.

## De-cumulation (DONE — do not redo)

`decumulate_ytd_flows` in D_pipeline.py converts YTD 10-Q income-statement and
cash-flow values into discrete quarters (Q2 = YTD_Q2 − YTD_Q1, Q3 = YTD_Q3 − YTD_Q2),
from original snapshots. It is FYE-aware (reads each ticker's own 10-K period-end
month, so non-calendar filers like V/MU/AAPL/retailers group correctly) and
position-agnostic (selects by form == '10-Q', statement_type in income/cash-flow,
`duration_days > 130 (QUARTER_MAX_DAYS)`, so it catches OCF and capex without a
position list). It runs for **every** ticker; duration does the gating. A discrete
quarter is ≤ ~98 days even in a 53-week quarter, so genuine single quarters are never
touched and you cannot double-de-cumulate. Cumulative Q2/Q3 with a missing same-year
baseline are set to `missing` (these become the baseline-orphan rows below).

**Ordering invariant (do not reorder):** in `process_ticker`, de-cumulation MUST run
*after* `apply_calculated_financial_items` (so calculated positions are present and get
de-cumulated too) and *before* the zero-fill of missing values (so baseline orphans
become `missing` rather than being differenced against a zero). The current call order
in D_pipeline.py reflects this; a refactor that moves either step breaks it silently.

**52/53-week drift fix (DONE this session — verified).** Bug: `decumulate_ytd_flows`
derived the fiscal quarter from the period-end's calendar MONTH
(`_q = ((month - FYE - 1) % 12)//3 + 1`) and only de-cumulated quarters labelled 2 or 3.
52/53-week ("4-4-5") filers have quarter-ends that drift across month boundaries year to
year, so a drifted quarter got the wrong label (e.g. AVGO's August quarter → "Q4") and was
SKIPPED — its cash-flow-statement YTD `operating_cash_flow`/`capital_expenditure` (270-day)
was kept as if quarterly, inflating FCF / FCF-margin / OCF-margin / cash_conversion /
OCF-growth. (Income-statement flows were unaffected — they arrive as discrete 90-day
quarters, so de-cumulation never needed them.) Footprint: 60 rows across 13 filers (AAPL,
AMAT, AMD, AVGO, CSCO, DIS, HD, INTC, KO, MU, NVDA, TJX, TMO), OCF+capex only. Fix: replaced
the month→quarter labelling with **ordering-based de-cumulation** — within each
(position, fiscal_year), sort by period-end and difference each cumulative row against the
immediately-preceding YTD row; if an intermediate quarter is absent (gap > QUARTER_MAX_DAYS)
or there is no baseline, mark `missing`. Drift-proof, and proven byte-identical to the old
logic for clean calendar filers (JPM). Verified after rebuild: 0 residual YTD-not-decumulated
OCF/capex rows; AVGO FCF-margin 0.36–0.52 (was 1.07–1.46); release-date fingerprint,
AXP total_loans, and the ABBV/KLAC/GE annual fix all unchanged.

## The ABBV/KLAC/GE fix (DONE this session — verified)

Bug: `select_best_fact`'s annual fallback accepted a ~91-day Q4 fact as the annual
value when no 300–450-day fact carried the filing's exact period-end date. A quarter
got stamped as the year.

Fix: `ANNUAL_MIN_DAYS = 300` floor in both 10-K branches of `select_best_fact`. When
the longest available fact is sub-annual, return `None, "missing"` rather than the
quarter; the row becomes an honest coverage gap and is refilled downstream as
`gross_profit = revenue − cost` from sound full-year revenue/cost.

Verified by row-level DB diff: exactly **15** rows changed across 23,898 (everything
else byte-identical, no regressions): ABBV gross_profit 10-K ×5, GE cost_of_revenue
10-K ×4, GE gross_profit 10-K ×4 (downstream recompute), KLAC gross_profit 10-K ×1,
KLAC operating_income 10-K ×1. The GE/KLAC downstream rows were *silently wrong*
before (calculated values whose identity check passed on a quarter of cost) — the fix
corrected them too.

## Known-benign flag ledger — DO NOT "fix" these

- **net_income ≈ pretax − tax REVIEWs** everywhere (~406, the largest chunk): correct
  NCI / minority-interest / equity-method / discontinued-ops accounting.
- **concept-drift REVIEWs** (~117): equivalent-tag churn (Revenues vs
  RevenueFromContractWithCustomer; NetIncomeLoss vs ProfitLoss; CECL-era allowance
  tags). Same economic line.
- **frozen short_term_debt** at round numbers (GOOG 1,000M, NVDA 1,250M, TXN 500M):
  commercial-paper programs rolled flat.
- **negative gross margins**: BA (defense charges) and MU 2023 (memory downturn) —
  real.
- **ACN long_term_debt** 53M → 5,034M: real debut bond issuance.
- **NEE income_tax 5M** Q3-2024 scale-jump: real utility tax-credit quarter.
- **SPGI short_term_debt** scale-jump: known lumpy, accepted.
- **short_term_debt** is the weakest field universe-wide (inconsistent concepts);
  accepted where it only feeds total-debt / level ratios. ABBV short_term_debt spikes
  (1.6–12.6B) are real current maturities of Allergan debt.
- **baseline-orphan long-duration 10-Q rows** (~66): off-calendar OCF/capex pairs
  whose same-fiscal-year prior quarter is `missing`, so de-cumulation had no baseline.
  Genuine coverage gaps, NOT errors.
- **scale-jumps that are below median** (small single quarters): benign.

The single residual FAIL worth an eyeball (not yet adjudicated): **LRCX gross_profit =
rev − cost**, 2023-03-26 10-Q, ~4% off — a `CostOfGoodsAndServicesSold` vs
`CostOfGoodsAndServicesSoldExcludingRestructuringCharges` concept split, not a wrong
magnitude.

## Per-name adjudications (resolved — do not relitigate)

- **MU**: latest revenue 41,456 / gross 35,056 / operating 33,318 (~80% op margin) is
  a **real HBM upcycle peak**, confirmed against the filing. August FYE. Do NOT
  de-cumulate further; its 272-day flags are only on old 2021–2023 filings.
- **GE**: `operating_income` calc removed (conglomerate/insurance line-classification
  produced nonsense). GE has no operating_income — exclude it from operating-margin
  scoring at the modelling stage.
- **AXP**: stopped splitting loans from receivables Q1-2026 →
  card_member_loans = 207,247M, total_loans = 220,259M (~42% jump = reporting-basis
  change, not real growth). User chose to keep the 207B value and owns it. NOT a code
  change. Harmless if total_loans only feeds level-based ratios; distorts
  loan_growth_yoy on the live scoring row. Confirm it survives every rebuild.

================================================================================
## MODELLING PHASE — read docs/PROJECT_SPEC.md first
================================================================================

`docs/PROJECT_SPEC.md` is the authoritative 17-step plan (signal formulas, scoring
rubric, per-sector signal sets, target math, backtest). The notes here are only the
load-bearing invariants and the gaps between the spec and what the pipeline currently
produces. When spec and this file disagree on extraction facts, this file wins; on
modelling design, the spec wins.

### Non-negotiable modelling invariants
- **Look-ahead control (the cardinal rule):** features may use only information public
  at the **report RELEASE date**, never the fiscal-period-end date. Targets are
  computed from t+1 (first trading day AFTER release) over the next 63 trading days on
  adjusted-close prices.
- **Target:** `future_63d_sharpe = mean(daily ret t+1..t+63) / std(daily ret) * sqrt(252)`.
  Simple version assumes risk-free = 0 (state it). Also store 63d return and 63d vol.
- **Six-sub-score architecture:** every sector is scored on the SAME six sub-scores —
  profitability, growth, cash_flow, leverage, efficiency, investment — but the KPIs
  feeding each are sector-specific (full per-sector KPI sets in PROJECT_SPEC.md §2.5).
  Each sub-score = mean of its oriented, percentile-ranked KPIs; financial_score = mean
  of the six; `competitive_advantage_score = w*financial_score + (1−w)*strategic_score`
  (w TBD).
- **Sector-relative scoring:** rank each KPI cross-sectionally **within sector group AND
  within the same report period**, to a percentile in [0,1]. **Orient so higher = better
  BEFORE ranking** — sign-flip every "inverse" KPI (leverage, efficiency_ratio,
  assets_to_equity, cost_to_income, all std-dev/stability metrics). Strategic 1–5 →
  (score−1)/4.
- **Missing-KPI rule (not zero):** if a KPI can't be computed, DROP it and renormalize
  the sub-score over the remaining KPIs — never feed 0. Since missing values are stored
  as 0 in the DB, "can't be computed" = `selection_status=='missing'` OR a guarded
  denominator, NOT a naive `value==0` test.
- **Change features:** absolute `current − prior` per signal (and per sub-score and
  score); NO improvement dummies; drop each company's first observation (no prior).
  Buffer year exists only as the YoY base and is excluded from training.
- **Split:** time-based only, never random; hold the latest reports as an untouched
  test set.
- **Model:** one pooled cross-sectional model over all company-report rows (NOT
  per-company); keep models simple/explainable; compare levels-only vs levels+changes.
- **Min-observations floor:** one uniform rule for all names — the same floor that
  dropped GEV must also govern young names (PLTR/APP/UBER/NOW).

### Sector mapping (13 impl. groups → 9 spec sectors)
Tech A–D → Technology; CommA → Communication; DiscA → Consumer Discretionary;
StapA → Consumer Staples; HealthA → Healthcare; BankA → Banks; FinA → Financial
Services; IndA → Industrials; EnergyA + EnergyB → Energy, Materials & Utilities.

### Spec-vs-current GAPS — reconcile before building features (don't assume these away)
1. **Company count:** spec says 98 companies; current universe is 72 tickers. Reconcile
   (trimmed universe vs original target) — a human call, not a silent fix.
2. **Report release date:** the spec's timing/look-ahead rules require the filing/
   acceptance date. `financial_facts` stores period-end (`fact_end_date`), not clearly
   the release date. VERIFY the pipeline captures filing date (it's in the SEC
   submissions JSON) before any target construction — this is the highest-risk gap.
3. **KPIs needing data not yet in `financial_facts`:** noninterest expense & interest
   income, loans & deposits, CET1/Tier1, provisions/NPLs (banks); inventory (Disc/
   Staples/Industrials — partly present); acquisitions CF (FinServ); content/network
   investment (Comm); dividends/retained earnings (capital_retention). Per the spec's
   missing-KPI rule these can be dropped-and-renormalized, but where a sub-score leans
   on them (esp. bank leverage/efficiency/investment) they should be retrieved. Don't
   assume the columns exist.
4. **Strategic 1–5 scores are a separate, not-yet-built extraction** (LLM-from-report
   evidence with a confidence level), distinct from the numeric pipeline. The numeric
   half is done; the strategic half is greenfield.
5. **Price data** (daily adjusted close) is a separate ingest not in `financial_facts`
   — needed only for targets/backtest, not features.
6. **Adding the missing-data KPIs loops back into EXTRACTION.** The spec's "data still
   to retrieve" (noninterest expense & interest income, loans/deposits, CET1/Tier1,
   provisions/NPLs, inventory, acquisitions CF, content/network investment, dividends/
   retained earnings) means new positions in config → a full 13-group rebuild with all
   the rebuild cautions above. It is NOT a modelling-only change; sequence it as
   extraction work.

### OPEN DECISIONS — ASK the user, do not invent answers (full text in PROJECT_SPEC.md)
1. Definition of `free_cash_flow_after_capex_margin` (Energy) — ambiguous; FCF is
   already OCF − capex.
2. Confirm "if available" = drop-and-renormalize (vs a fixed proxy), esp. bank capital
   ratios and content/network intensity.
3. Bank `cash_flow_score` / `investment_score` are proxies needing explicit definitions
   before they're computable.
4. Regression vs classification framing (Sharpe level vs top/bottom quantile) — sets
   the eval metrics.
5. Scoring weight `w` in competitive_advantage_score (spec leaves it TBD; not assumed
   0.5).

## Working style

Be confident and decisive; lead without waiting for confirmation, but sequence safely
(read-only diagnostics before destructive writes; all config edits before a single
rebuild). State informed cautions once, then respect the user's decision — the user
makes final calls and owns them. Be explicit about which file each change goes in.
Prefer targeted patches over whole-file rewrites.

---

One-off jobs live as prompts/notes so this file stays durable standing context. The old
re-validation routine (formerly `.claude/revalidate.md`) is **RETIRED** and archived at
`docs/revalidate.archived.md` — it documents the retired 4-layer validator and is NOT a
live routine.
