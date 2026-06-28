# CLAUDE.md — Financial Instruments quant-equity pipeline

Read this fully before doing anything. It is the source of truth for project state,
conventions, and what has already been decided. Files in `src/` are the ground truth
for behavior; this file is the ground truth for *intent*. The full assignment-level
plan (17 steps, all signal formulas, scoring rubric, backtest spec) lives in
`docs/PROJECT_SPEC.md` — read that before any modelling-phase work; do NOT inline it
here.

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
- **debug.py** — the validator (this is `validate_data.py`). Run after a pipeline
  run. Writes `validation_flags.csv` + `concept_map.csv`.

Scripts use flat imports (`import A_config`), so run them from inside `src/`:
```
cd src
python D_pipeline.py    # full rebuild — DESTRUCTIVE, see cautions
python debug.py         # validate, writes the two CSVs
```

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

## The validator (debug.py) — four layers

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

One-off jobs (like re-validating the retrievals) live as prompts or slash commands
under `.claude/commands/` so this file stays durable standing context. See
`.claude/commands/revalidate.md` for the re-validation routine.
