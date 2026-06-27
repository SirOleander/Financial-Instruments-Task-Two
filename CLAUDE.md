# CLAUDE.md — Financial Instruments quant-equity pipeline

Read this fully before doing anything. It is the source of truth for project state,
conventions, and what has already been decided. Files in `src/` are the ground truth
for behavior; this file is the ground truth for *intent*.

## What this project is

A university "Financial Instruments" quantitative equity strategy. The pipeline:
extract financial signals from SEC filings → compute sector-specific KPI scores →
predict a forward 63-trading-day Sharpe → rank companies long (top 10) / short
(bottom 10) → backtest. The data work (extraction + validation) is effectively
closed; the next phase is modelling.

Universe: 72 tickers across 13 groups, 7 fiscal years fetched, latest period
~2026-05-31. A clean validator run currently produces ~700 flags, almost all
pre-adjudicated as benign (see the ledger below).

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

## What's left (MODELLING stage — not extraction code)

1. **Negative book equity** — MCD (−1,286), PM (−9,279), BKNG (−8,724), ABBV (−6,656),
   all real. Floor the denominator or exclude ROE/equity_ratio for these names at
   scoring time.
2. **HealthA / pharma gross margin** — amortization-in-COGS. Either compute
   gross_profit = revenue − cost consistently for HealthA, or drop gross_margin for
   HealthA (as already done for Energy/Banks). Note ABBV's old gross_profit FAILs were
   the selector bug (now fixed), so re-check on clean numbers before deciding.
3. **Off-calendar fallback names** (ACN/COST/CSCO/INTU/KLAC/LRCX/PG) — eyeball that
   OCF/capex now read as single quarters post-de-cumulation.
4. Optional: reclassify baseline-orphan long-duration rows as their own validator
   category so they stop reading as anomalies.
5. Optional: add a YoY step-change flag (>~35%) to catch basis breaks like AXP loans
   that slip under the 50× scale-jump.

Modelling design (already decided): one pooled cross-sectional model (NOT
per-company); time-based split (never random); uniform minimum-observations floor for
all names (the rule that dropped GEV must also govern young names PLTR/APP/UBER/NOW);
buffer year used only as the YoY base, excluded from training; change features =
current − prior, with each company's first observation dropped.

## Working style

Be confident and decisive; lead without waiting for confirmation, but sequence safely
(read-only diagnostics before destructive writes; all config edits before a single
rebuild). State informed cautions once, then respect the user's decision — the user
makes final calls and owns them. Be explicit about which file each change goes in.
Prefer targeted patches over whole-file rewrites.

---

## CURRENT TASK — re-validate the SEC retrievals

Goal: confirm the companies were retrieved correctly, the same way it was done before.
"Validated" here means **every flag is accounted for** (on the benign ledger above or
freshly investigated and explained) and no new/unexpected family appears — not "zero
flags."

Do this, read-only first:

1. From `src/`, run `python debug.py` against the current `data/financials.db`. (Only
   run a full `D_pipeline.py` rebuild if the DB is stale or a config/client change
   requires it — and if you do, heed the rebuild cautions above.)
2. Summarize `validation_flags.csv` by check × severity. Compare the counts to the
   expected shape: ~406 net_income REVIEWs, ~117 concept-drift, ~66 duration-band
   (all 10-Q baseline orphans), ~68 scale-jump FAILs, ~23 frozen, ~14 heavy-fallback,
   plus the small margin/identity FAILs.
3. Reconcile every FAIL and REVIEW against the known-benign ledger. **Surface only
   what does NOT map to a known family** — that's the signal. Expect the lone LRCX
   restructuring-charge identity break as the one residual.
4. Confirm the extraction-bug families are clean: zero 10-K duration-band rows, and no
   ABBV/KLAC gross_profit or ABBV operating-margin FAILs.
5. Spot-check via `concept_map.csv`: off-calendar names (ACN/COST/CSCO/INTU/KLAC/
   LRCX/PG) OCF/capex look like single quarters; the fixed positions (ABBV/KLAC
   gross_profit, GE cost_of_revenue) show `extraction_method = calculated` with sane
   values; AXP total_loans = 220,259M with card_member_loans = 207,247M.
6. If a prior `financials.db` snapshot is available, diff the two on key
   (ticker, accession_number, position), ignoring `id`/`created_at`, and report only
   rows whose value/selection_status/extraction_method/duration changed.

Report findings concisely: what's clean, what (if anything) is new and needs a human
call, and whether the retrieval looks correct. Do not "fix" anything on the benign
ledger.
