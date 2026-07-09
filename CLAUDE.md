# CLAUDE.md — Financial Instruments quant-equity pipeline

Read this fully before doing anything. It is the source of truth for project state,
conventions, and what has already been decided. Files in `src/` are the ground truth
for behavior; this file is the ground truth for *intent*. The full assignment-level
plan (17 steps, all signal formulas, scoring rubric, backtest spec) lives in
`docs/PROJECT_SPEC.md` — read that before any modelling-phase work; do NOT inline it
here.

================================================================================
## MILESTONE — FINAL UNIVERSE = 97 (98 mandated − GOOG, a DOCUMENTED dedup).
## Supersedes the "89 companies" / "98" statements below where they conflict.
================================================================================
The assignment mandates a FIXED 98-stock universe; we had trimmed 9 for data quality, which
the task does NOT authorize, so all 9 were re-added ADDITIVELY (the original 89's
`financial_facts` / `daily_prices` rows proven byte-identical by content-hash before/after).
**Then GOOG was deliberately dropped again → the working universe is 97.**

### GOOG DROPPED — a STATED, DOCUMENTED deviation (97 of 98), NOT a silent drop
- **Rationale:** GOOG (Alphabet Class C) and GOOGL (Class A) are the SAME issuer, one SEC
  filer, one CIK (0001652044) → **byte-identical fundamentals**. Keeping both would double-
  weight Alphabet in every sector-percentile peer group, in training, and in the long/short
  book, while adding zero information (identical features; only the share-class price, hence
  the target, differs marginally). Dropping the duplicate class is **deliberate deduplication
  of dual share classes**, consistent with how other multi-listing cases were handled.
- **We keep GOOGL, drop GOOG.** This MUST be stated in the report/presentation as a documented
  deviation from the mandated list (97 of 98 analysed), with the dedup rationale.
- Mechanics: removed from `A_config` (COMPANIES / COMPANY_NAMES / SECTOR_BY_TICKER /
  ACTIVE_TICKERS / COMPANY_GROUPS['CommA']) and DELETED from all 7 tables. Backup at
  `data/financials.db.bak_before_goog_drop`.
- **Verified surgical:** the other 97 names' rows are byte-identical (md5) in the five
  ticker-INDEPENDENT tables (financial_facts, daily_prices, kpi_values, target_63d,
  operative_scores). `scores` legitimately CHANGED **for Communication names only** (the
  sector-percentile peer group shrank 8→7); every other sector's scores are byte-identical.
  `modelling_data` + `predictions/` + `analysis/` were regenerated on 97.

### The 9 re-added + per-name outcome (diagnostic-driven, data in hand):
- **GOOG** (EDGAR, CIK = GOOGL's 0001652044, CommA): re-added, then **DROPPED as the Alphabet
  dedup — see the block above.** Not in the universe.
- **GEV** (EDGAR, CIK 0001996810, IndA): GE Vernova, spun off 2024 → short history; cleared
  the uniform floor-6 (6 train rows) so it TRAINS. Operative falls back (no LITELLM_API_KEY
  at rebuild time; can be LLM-scored later).
- **TCEHY, 9988.HK, ALV.DE** (yfinance): usable but thin → prediction/ranking-only
  (train_eligible=0, below floor). ALV.DE is an insurer: OCF/capex absent → cash-flow /
  investment KPIs drop-and-renormalize (like banks lacking efficiency KPIs).
- **MC.PA, CBA.AX, NESN.SW, RHHBY** (yfinance) — BLOCKED for targets: yfinance returns NO
  usable report-release date (MC.PA/CBA.AX zero; NESN/RHHBY semi-annual, none matched). Per
  decision: prediction/ranking-only. They get KPIs + sector scores (rankable) but NO target,
  `target_missing=1`, `train_eligible=0`, `no_release_date=1`. Release dates were NOT
  synthesized (that would fabricate the look-ahead anchor).

### Keying rule for NULL-release rows (the 4 blocked + ALV.DE's 1 unmatched period)
`report_release_date` is NULL in `financial_facts`, so DOWNSTREAM they are keyed on
`fiscal_period_end_date` (a KEY SURROGATE only — never a target t=0). Implemented in
`E_kpis.load_reports` (COALESCE(release, period_end); the `WHERE release IS NOT NULL` filter
removed — only the 5 new NULL-having names are affected, 89 identical). `price_target` still
filters `release IS NOT NULL`, so blocked names get no target. `H_modelling` adds a
`no_release_date` flag (from financial_facts rows with NULL release) and LEFT-joins target
(absent → target_missing). New config: `A_config` GOOG/GEV; `yf_ingest.UNIVERSE` +7 non-US
(with `FIN`/`STAP` position lists + `NO_RELEASE_DATE_NAMES`).

### 97-state table coverage (rebuild order: kpi_values → scores → target_63d → operative →
### modelling_data → predictions/ → analysis/). ALL COHERENT AT 97:
financial_facts 26,500 / daily_prices 156,666 / kpi_values 40,996 / scores 1,712 /
modelling_data 1,712 — all **97 tickers**; target_63d 1,690 (93 tickers; 4 blocked names have
no targets); operative_scores 1,597 (82 tickers; US 10-K/20-F only).
modelling_data: **1,314 train_eligible across 72 companies** (70 US + GOOGL + GEV),
398 prediction-only. predictions_all.csv (renamed from the legacy predictions_all89) holds all **97**.

### Final universe: 89 companies, TWO sources in one `financial_facts` table
NOTE: superseded — universe is now 97 (98 mandated − GOOG; see the milestone above). Original 89 detail:
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
  calendar). future_63d_sharpe = mean(daily ret − rf_daily)/std·√252 — an EXCESS Sharpe over
  a CONSTANT risk-free rate (see the RISK-FREE RATE block below; superseded the old rf=0).
  1,573 real targets + 89 NULL (each company's most-recent report, forward window incomplete —
  fill naturally on idempotent re-run). At rf=2%: 1,599 real + 91 NULL on the 97, Sharpe
  median +0.657, range −5.60…+7.32 (was median +0.740 / −5.56…+7.49 at rf=0).
  CAUTION for modelling: extreme Sharpe tails may be low-vol-window artifacts —
  consider winsorizing the target tails and sanity-check a couple of extremes for
  near-zero-std denominators.

================================================================================
## RISK-FREE RATE — rf = 2% CONSTANT. Applied to BOTH Sharpes, at DIFFERENT frequencies.
================================================================================
**Single definition: `A_config.RISK_FREE_RATE_ANNUAL = 0.02`** + `A_config.risk_free_per_period
(periods_per_year)`. Imported by `price_target.py` and `K_backtest.py`. Never redefine locally.

- **Source/rationale (state in the report):** ≈ the average 3-month US Treasury bill yield
  (FRED series TB3MS, https://fred.stlouisfed.org/series/TB3MS) over the 2020–2026 sample,
  rounded to a clean 2%. The 3-month bill is the standard academic risk-free proxy. A CONSTANT
  (not a time-varying series) is a stated simplification.
- **FREQUENCY CONVERSION is the whole correctness risk.** The rate is quoted ANNUALIZED; it
  must be converted to the horizon of each Sharpe. The raw 2% is NEVER subtracted from a daily
  or a 63-day return. Both consumers annualize ARITHMETICALLY (`mean·N / std·√N`), so the
  per-period rf is the SIMPLE division `rf/N`, **not** geometric `(1+rf)^(1/N)−1`:
    * **Target** (`price_target.py`): `rf_daily = 0.02/252 = 0.000079365`, subtracted from
      EACH daily return before mean/std. `sharpe = mean(r − rf_daily)/std(r)·√252`. Consistency
      check: `mean_d/std_d·√252 == (252·mean_d)/(std_d·√252) == ann_return/ann_vol`, so
      subtracting rf/252 per day yields exactly `(ann_return − rf)/ann_vol`.
    * **Backtest** (`K_backtest.py`): the return series is one obs per ~63-trading-day
      rebalance, so `PERIODS_PER_YEAR = 252/63 = 4` and `RF_PERIOD = 0.02/4 = 0.005`.
- **`std(excess) ≡ std(raw)`** — subtracting a constant cannot change dispersion. So
  `future_63d_volatility` and `future_63d_return` (a RAW price return, never excess) are
  UNCHANGED by rf, and the target change collapses to the AUDIT IDENTITY:

      sharpe_rf = sharpe_rf0 − RISK_FREE_RATE_ANNUAL / ann_vol      (ann_vol = vol_d·√252)

  Verified to 1.78e-15 across all 1,599 rows. Persisted for audit: new `target_63d` columns
  `future_63d_sharpe_rf0` (pre-rf value) and `risk_free_annual` (added by guarded ALTER TABLE).
- **THE SHIFT IS NOT CONSTANT — do NOT claim "a constant shift preserves ranks".** The penalty
  is `−rf/ann_vol`, i.e. inversely proportional to volatility, so LOW-vol names are penalized
  HARDER: TD.TO (ann_vol 0.09) shifts −0.222 while APP (ann_vol 1.11) shifts −0.018 — a 12×
  spread. Range −0.222…−0.018, median −0.075. The target is therefore NOT a monotone transform
  of the rf=0 target: Spearman(old,new) = 0.99984, and 1,465 of 1,599 rows changed global rank.
  This is CORRECT Sharpe behaviour (a low-vol name clears the same 2% hurdle with less vol to
  divide by). The null survives because there was never signal — NOT because ranks are preserved.
- **BACKTEST: rf CANCELS on the long-short book, by construction.** The book is dollar-neutral
  and self-financing — the short proceeds fund the long leg and earn rf. That credit exactly
  offsets the rf subtracted to form an excess return:

      net_p    = (long_p − short_p) + RF_PERIOD − cost_p
      excess_p = net_p − RF_PERIOD = long_p − short_p − cost_p

  ⇒ **`ann_sharpe_LS` is UNCHANGED by rf.** This cancellation is a RESULT of the structure, not
  an omission. `ann_sharpe_LS_funded` is reported alongside as a SENSITIVITY only (naive
  fully-funded book, `excess_p = gross_ls_p − cost_p − 0.005`); it is strictly more pessimistic
  and is NOT the headline. Equity curves compound the self-financing net.
- Firewall proven at the change: backup `data/financials.db.bak_before_rf` (pre-change db md5
  `60aa6798…`); table-by-table hash showed **only `target_63d` changed** (then `modelling_data`
  on rebuild). `daily_prices` / `financial_facts` / `kpi_values` / `scores` / `operative_scores`
  byte-identical. `ohlc_display.db` never opened; `daily_ohlc` absent from financials.db.

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
  every first_obs / target_missing US row). All 97 companies remain in the table.
- **CAVEAT — winsor caps refit at split (leakage).** Caps are currently fit on the FULL
  population. At the time-based train/test split they MUST be refit on the TRAINING rows
  ONLY (train_eligible=1, pre-split) and re-applied — otherwise the test set leaks into the
  caps. This is the NEXT step's responsibility, not done here.

### FEATURE SET — DECIDED post-EDA (src/I_eda.py, artifacts in eda/, readout eda/EDA_SUMMARY.md)
**REGENERATED ON THE FINAL 97** (eda/ was previously stale at the 89-run while predictions/ and
analysis/ had moved to 97; `python I_eda.py` re-ran read-only on the DB). Current numbers:
EDA runs on TRAIN-ELIGIBLE rows only (**n=1314 / 72 companies** — was 1308/71 at 89). It is
READ-ONLY (writes only `eda/` figures+CSVs, dashboard-consumable; the Streamlit app consumes
them). Signal is weak by nature: max |Spearman| among well-populated (n≥800) features vs
future_63d_sharpe is **~0.078** (net_margin_change; was ~0.075 at 89) — this is a
MULTIVARIATE/ensemble problem, not a single-feature one. The conclusion is UNCHANGED by the
regeneration. `python I_eda.py` regenerates all artifacts. The feature choices below are a
SELECTION of existing modelling_data columns (NOT a schema change):

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
- **NULL HOLDS ON THE 97 AT rf=2%** (retrained on the excess-Sharpe target; these are the
  CURRENT numbers): train+val 1025 rows / 72 companies, test 289, 48 features. CV Spearman ∈
  [−0.032,+0.012] (Lasso/EN still degenerate to the constant/null model); ensemble test
  Spearman (pooled) −0.022, per-period +0.012; ablation max |CV|=0.034, max |test|=0.062.
  predictions_all.csv (renamed from the legacy predictions_all89) holds all **97** with flags
  out_of_training_dist / prediction_only (25) / no_release_date (5).
- **BACKTEST P&L FLIPPED SIGN under the rf change — and THAT IS THE POINT. Do NOT present the
  new positive number as an edge.** Per-rebalance LS +17.7%/−4.7%/−11.6%/+13.6%, cum **+12.6%
  gross (+11.4% @10bps)**, ann Sharpe **+0.49** (self-financing; fully-funded sensitivity
  +0.42), maxDD −16.3%. The rf=0 run gave cum **−2.4% / Sharpe ~0.05** on the SAME universe,
  features, split and code. A target perturbation of **Spearman 0.9998** swung the cumulative
  P&L by ~14 points because the ensemble refit → different top-10/bottom-10 books. That
  instability is DIRECT EVIDENCE the backtest P&L carries no information. Statistically:
  mean quarterly spread +3.75% vs sd 14.14%, **t = +0.53 on 3 d.f. (p ≈ 0.66)**, 95% CI on the
  mean spread [−19.1%, +26.0%] — contains zero; the sign still FLIPS 2-of-4. Both legs rose
  (+64% long / +44% short) in a bull market (universe +42%). rf CANCELS on the LS book, so the
  Sharpe change is entirely the reordered target, not the rf arithmetic.
- **The MODEL null is unmoved:** CV/test Spearman ≈ 0, Lasso/EN still select 0/48 features,
  ablation flat, classification still at chance (test AUC 0.449–0.542, CV AUC 0.474–0.523).
  The null is robust to the 89→98 expansion, the GOOG dedup, AND the rf=0→2% target change.
- **TEST-SET TOUCH #3.** The regression touched the test set once; the classification lens a
  second time; this rf retrain is a THIRD touch. All under the SAME pre-committed protocol
  (features, models, grids, metrics, split fixed before looking) — no iterative tuning against
  test, and the rf change was mandated externally, not chosen after seeing a result. The
  expected outcome (null holds) was stated in writing BEFORE the retrain was run. Keep
  disclosing the touch count.
- Numbers below are the ORIGINAL 89-run (kept for reference; superseded by the 97 line above).
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
  ablation_results, coef_/importance_*, predictions_all, backtest_periods/holdings/summary,
  fig_backtest_equity.png, MODEL_SUMMARY.md, BACKTEST_SUMMARY.md.

### SLIDE-24 GRADING ITEMS — DONE, regenerated on the FINAL 97 model (src/L_analysis.py → `analysis/`)
Additive + read-only (DB and `predictions/` untouched). Same leak-safe protocol as J_models
(time split 2025-03-31, TimeSeriesSplit(5, gap=21), all preprocessing refit per fold).

**1. Error analysis — bias & variance. THE ASSUMED "high-bias/low-variance everywhere" READING
WAS WRONG; the data shows TWO failure modes with one identical outcome. Do NOT restate the
old assumption — use this:**
- **Underfit / high-bias, ~ZERO variance:** Lasso & ElasticNet regularize EVERY coefficient to
  exactly 0 → they literally ARE the mean-predictor (train RMSE 1.947 ≈ val 1.960, train ρ =
  val ρ = 0).
- **Overfit / HIGH variance, zero payoff:** SVR train ρ **+0.923** vs val −0.001; XGBoost
  +0.842/−0.011; RandomForest +0.631/−0.014 (train RMSE 0.85–1.74 vs val 1.98–2.16). They
  memorize the training rows and generalize at zero — the capacity is spent fitting NOISE.
  Ridge in between (train ρ +0.296, val −0.032). Calling these "low-variance" is FALSE.
  (Numbers regenerated on the rf=2% excess-Sharpe target; the pattern is unchanged.)
- **Learning curves are FLAT in training size** (RF val RMSE 1.807→1.837, XGB 2.007→1.957 as
  rows 119→799; target std ≈1.98). If variance were the binding constraint validation error
  would FALL with more data — it does not.
- **Conclusion:** total error dominated by **irreducible noise + bias**, not variance. More
  data / more capacity / more tuning cannot fix this — **only a genuinely more informative
  feature set could.** The near-zero result is itself stable (fold spread straddles zero;
  reproduces across the ablation and the 89→98 expansion).

**2. Feature importance — the models are NOT black boxes.**
- **Lasso & ElasticNet select 0 / 48 features** (all coefficients exactly zero) — the cleanest
  statement of the null: no linear combination beats the intercept.
- Ridge: 48/48 non-zero but tiny; RF/XGB importances spread thinly (no dominant split var);
  SVR explained via permutation importance on VALIDATION folds (never test).
- Rank-consensus top-5 (rf=2% run): growth_score_change, operating_margin_change,
  profitability_score, net_income_growth_yoy_change, capex_intensity — mostly CHANGE features.
  **Magnitudes are trivial; this ranks near-noise**, and the membership churns between runs,
  which is itself a symptom of noise-ranking. Interpretability CONFIRMS the null, it does not
  rescue it.

**3. Classification lens — near-chance, confirms the regression null.**
- Label = top-third vs bottom-third realized future_63d_sharpe (middle dropped), matching the
  long/short framing. **LEAK CONTROL: tercile cutoffs fit on TRAIN ROWS ONLY** — per CV fold
  from that fold's train rows; from train+val for the one-shot test. Test outcomes never
  inform any cutoff; no cutoff fit on the pooled data.
- Test AUC 0.449–0.542 (chance 0.500); CV AUC 0.474–0.523, mostly BELOW 0.5 → sign
  disagreement = noise. SVM is BELOW chance on test (0.449).
- **Majority baseline acc = 0.572** (train-fitted cutoff + higher test-regime Sharpes leave the
  test set 57.2% one class), so raw accuracy (0.493–0.532) is at/below that baseline. Read AUC
  and balanced accuracy (~0.5). Balanced within-period variant (50/50) reproduces: AUC
  0.437–0.539. (rf=2% run; same verdict as rf=0.)
- Verdict: a classification framing gives the SAME answer — cannot separate future winners from
  losers better than chance.

**HONEST CAVEAT (keep stating it):** the test set was already used once by the regression; this
classification evaluation touches it a SECOND time, under a PRE-COMMITTED protocol (labels,
models, grids, metrics all fixed before looking). The rf=0→2% retrain is a THIRD touch, same
protocol, externally mandated. No iterative tuning against test.

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
(bottom 10) → backtest. Both phases are now **COMPLETE**:
  - **Extraction + validation** — CLOSED (much of this file's detail).
  - **Modelling** — CLOSED. The honest finding is a **near-null result** (report fundamentals
    do not reliably predict the forward 63-day Sharpe on this universe/period); that is the
    deliverable, not alpha. See the MODELLING + BACKTEST and slide-24 sections above.
The whole thing now runs from one command — `python run_pipeline.py` (see Repo layout).

Universe: **97 tickers** across 13 implementation groups (= 9 economic sectors), 6 fiscal
years fetched, latest period ~2026-05-31. (The old 4-layer data validator is RETIRED now the
extraction phase is closed — see "The validator — RETIRED" below; the benign-flag ledger it
produced is kept for interpretability.)

## Repo layout — the `fi/` package (post-refactor)

The code was consolidated from 16 flat, letter-prefixed `src/` modules into one package,
`src/fi/`, run by a single entry point. **Old-name → new-home map** (old names appear
throughout this file's history; they all resolve to `fi.*` now):

| Old flat module | Now in | Notes |
|---|---|---|
| `A_config` | `fi.config` (+ `fi.concepts`) | the ~2,300 lines of us-gaap/iXBRL concept tables split into `fi.concepts`; `fi.config` is the part you read |
| `B_database` | `fi.db` | |
| `C_client` + `D_pipeline` | `fi.sec` | SEC client + EDGAR extraction, merged |
| `yf_ingest` + `price_ingest` | `fi.market` | yfinance fundamentals + daily prices, merged |
| `G_operative` | `fi.operative` | the only paid/LLM stage; kept separate |
| `E_kpis` + `F_scores` + `price_target` + `H_modelling` | `fi.features` | KPIs, scores, target, modelling table |
| `I_eda` + `J_models` + `K_backtest` + `L_analysis` | `fi.modelling` | EDA, train, backtest, slide-24 analysis; the old `import J_models as J` cross-import is gone |
| — | `fi.pipeline` | NEW: the stage registry + CLI |
| — | `fi.verify` | NEW: the proof harness (fingerprints + invariants) |
| `verify_release_dates` | `tools/verify_release_dates.py` | read-only diagnostic, moved out of the pipeline |

Load-bearing details that survive the move:
- **`fi.config`** — companies, CIKs, sectors, `COMPANY_GROUPS` (TechA–D, BankA, FinA, CommA,
  DiscA, StapA, HealthA, IndA, EnergyA, EnergyB), sign rules, `RISK_FREE_RATE_ANNUAL = 0.02`,
  `FISCAL_YEARS_TO_FETCH = 6` (the value the DB was built on; earlier "7" was a doc error),
  `validate_config()`, `DATABASE_PATH = BASE_DIR/data/financials.db`. The us-gaap concept maps
  (`FINANCIAL_ITEMS_BY_GROUP`, `INLINE_FINANCIAL_ITEMS_BY_TICKER`, `CALCULATED_*`) live in
  `fi.concepts` and are re-exported. (`DECUMULATE_YTD_TICKERS` was dead — defined, never read
  — and has been **removed**; de-cumulation runs for every ticker, gated by duration.)
- **`fi.db`** — one `financial_facts` table, long format (one row per ticker/filing/position).
  `get_connection()` uses `sqlite3.Row`. Unique index = (ticker, accession_number, position,
  extraction_method). Missing values are stored as `0`, but `selection_status == 'missing'` is
  what marks a real gap — never infer "missing" from `value == 0`.
- **`fi.sec`** — FYE-aware accession selection; `select_best_fact`;
  `apply_calculated_financial_items`; `build_standardized_rows`; the annual-duration floor fix
  (see "The ABBV/KLAC/GE fix"). Its `main()` is now **APPEND-ONLY** — see the cautions below.
- **tools/** — non-pipeline diagnostics, each with a `sys.path` shim to reach `src/` and
  importing `fi.*`: `price_probe.py`, `yf_probe.py`, `viewdatabase.py`,
  `verify_release_dates.py` (EDGAR `report_release_date` == SEC filingDate check).
- **docs/** — `PROJECT_SPEC.md`, `TASK.txt`; `docs/archive/` holds superseded notes
  (`WORKFLOW.txt`, `revalidate.archived.md`).

### Running — ONE command

```
python run_pipeline.py --offline   # recompute all local stages from the committed DB
python run_pipeline.py             # every stage: fetch latest data (append-only), retrain
python run_pipeline.py --list      # the 12-stage plan
python run_pipeline.py --verify    # invariants only (read-only)
python src/fi/verify.py --check proofs/baseline.json   # fingerprint vs the recorded baseline
```
(`tools/` scripts still run from the repo root, e.g. `python tools/viewdatabase.py`.)

## CRITICAL cautions

1. **Ingestion is APPEND-ONLY (as of the step-7 refactor).** `fi.sec.main()` calls
   `create_tables(drop_existing=False)` and UPSERTS on the unique key — it NEVER drops
   `financial_facts`. The old `drop_existing=True` full-rebuild is gone, and with it the
   `TARGET_GROUPS` footgun (a run that omitted a group used to silently wipe it) and the risk
   of a re-fetch wiping the yfinance non-US rows. Restatements are overwritten AND logged
   old→new; orphans (rows a re-fetch no longer produces) are kept AND reported. See
   `find_restatements` / `find_orphans` in `fi.sec`.
2. The **AXP `total_loans`** adjudication (see Adjudications) is now safe by construction:
   append-only never deletes it. It only changes if SEC itself restates it — in which case
   the restatement is logged old→new, never silent.
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
- **Target:** `future_63d_sharpe = mean(daily ret t+1..t+63 − rf_daily) / std(daily ret) *
  sqrt(252)`, `rf_daily = RISK_FREE_RATE_ANNUAL/252`. See the RISK-FREE RATE block above —
  rf = 2% constant (superseded the earlier rf=0). Also store 63d return and 63d vol.
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
1. **Company count: RESOLVED.** Spec mandates 98; the working universe is **97** (98 − GOOG,
   the documented Alphabet dual-class dedup — see the milestone at the top). No longer an open
   gap; kept here for history.
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

## DASHBOARD (dashboard/, Streamlit) — READ-ONLY presentation layer, on the 97

`streamlit run dashboard/app.py` from the repo root. Reads `data/financials.db` +
`predictions/` + `analysis/` + `eda/`. **Writes nothing.** Modules: `app.py` (views),
`ui.py` (palette/CSS), `charts.py` (Altair), `data.py` (cached loaders).

- **Nav = four standalone pills beside the search box**: Ranking · Model · Data · Backtest.
  Not a segmented group. **`Company Detail` has NO nav item** — it is a drill-down, reached
  only by clicking a company in the left watchlist or a Ranking row.
- **`view` is plain session state, NOT a widget key** (segmented_control owned it before), so
  callers assign `st.session_state["view"]` directly. The old `_pending_view` deferral hack is
  gone; do not reintroduce it.
- **Model vs Data is a SOURCE split, and it is load-bearing.** `Model` = `predictions/` +
  `analysis/` (CV/test performance, bias-variance + learning curves, feature importance,
  classification). `Data` = `eda/` only (feature→target correlation, distributions,
  correlation + VIF, target + missingness). Model *diagnostics* (importance, classification,
  bias-variance) belong under Model even though they describe features — do not migrate them
  to Data. The feature→target correlation chart is the one thing that moved the other way.
- **Watchlist is flush-left**: `.block-container` drops its centering `max-width` and its left
  gutter (`padding-left: .85rem`), putting the first ticker tile ~14px from the window edge.
  Restoring `max-width:1680px` re-centers everything and undoes this.
- **The Ranking table is a hand-rolled HTML grid, NOT `st.dataframe`** — and it has to be.
  `st.dataframe` draws its row-selection checkbox column *inside the canvas grid* (unreachable
  from CSS) and that column only exists because `on_select` is enabled, so "no checkbox" and
  "clickable rows" are mutually exclusive there. Each row is a grid div with a **transparent
  full-row `st.button` overlaid** (`rkbtn_*`), which keeps the click in-session. A
  query-param `<a href>` was tested and REJECTED: it full-reloads the page and resets
  session_state (theme + view). Two CSS facts are load-bearing, both discovered by measuring
  the DOM, not by looking at a screenshot:
    1. the row container needs `flex:0 0 44px !important` — Streamlit makes it a column-flex
       item with `flex:1 1 0%`, and a `flex-basis:0%` **beats `height`**, collapsing rows to
       27px so the overlay covers only part of the row;
    2. `.sd-rt-row` needs a fixed px height (not `100%`) — an unnamed emotion wrapper between
       `stMarkdown` and `stMarkdownContainer` collapses to content height, so a percentage
       never resolves.
  Trade-off accepted: **column-header sorting is gone** (st.dataframe gave it for free). The
  table is rank-ordered, which is the point. `predictions_all.csv` order is authoritative.
- **NO per-row confidence/provenance column on Ranking.** A per-row "prediction-only" flag
  contradicted the ranking by marking the very rows it recommends. The disclosure lives once,
  at tab level, in `ui.scope_note()` with DERIVED counts (72 trained / 97 ranked / 25
  out-of-sample). Do not reintroduce a per-row flag. The per-company `confidence` tier is
  still shown on **Company Detail**, where it describes one name rather than the whole book.
  A separate one-line note under the baskets reports how much of the ACTUAL BOOK is
  out-of-sample ("6 of the 20 picks") — that is summary-level, not per-row, and is kept.
- **Two scroll containers, deliberately: `.stMain` (the page) and `.st-key-colist` (the
  watchlist).** The RANKING TABLE has none — that is the invariant to protect. The watchlist is
  a CONTAINED sticky panel (height = viewport below the header) so it stays visible while the
  main column scrolls. (This reverses an earlier "watchlist scrolls with the page" iteration;
  don't flip it back without being asked.)
- **`stLayoutWrapper` is the recurring trap.** Streamlit inserts one between a keyed
  `st.container` and its children. Consequences, all found by measuring the DOM:
    1. **Sticky must go on the wrapper.** A sticky element is confined to its containing block,
       so `position:sticky` on `.st-key-topbar` stuck for 73px (the wrapper's height) and then
       scrolled away. Rules target `[data-testid="stLayoutWrapper"]:has(> .st-key-topbar)` and
       `...:has(> .st-key-watchlist)`, which ARE children of the tall page/column blocks.
       Requires `:has()` (Chrome 105+, Safari 15.4+, Firefox 121+).
    2. **`>` child combinators silently miss.** `.st-key-navgroup > [data-testid=
       "stHorizontalBlock"]` never matched — use descendant selectors inside keyed containers.
    3. **A flex chain breaks at the wrapper.** The wrapper is `flex:0 1 auto; min-height:auto`,
       so it sizes to content: `.st-key-colist`'s `overflow-y:auto` did nothing until the
       wrapper itself got `flex:1 1 auto; min-height:0`.
- **`flex:1 1 0%` beats `height` — guard every clickable row.** Streamlit gives element
  containers `flex:1 1 0%`; inside a height-constrained flex column that collapses rows and
  click targets stop covering the visible row (this bit the ranking overlay). `.st-key-colist
  [data-testid="stElementContainer"]` is pinned to `flex:0 0 auto` for exactly this reason.
  After ANY layout change here, re-probe click targets with `elementFromPoint`.
- **Header:** logo | centred (search + 4 nav items, `NAV_GAP`=19px ≈ 0.5cm) | theme toggle.
  Nav is **plain text** (white on dark / black on light, `P['nav_text']`) with **NO
  active-state highlight** — outline + tint on hover only. Every nav button is `secondary`;
  passing `type="primary"` would reintroduce the purple pill because Streamlit fills primary
  buttons with `theme.primaryColor`. The active view is named by the page's own title, not the
  nav. No divider under the header. The logo is a click-home target (transparent `logobtn`
  overlay -> Ranking) and works whether or not a logo file exists.
- **OHLC price chart is FIREWALLED from the pipeline.** `dashboard/fetch_ohlc.py` caches raw
  (unadjusted) OHLC for the 97 into **`data/ohlc_display.db`** — a SEPARATE DATABASE FILE, not
  a table in `financials.db`. This is deliberate and stronger than a separate table: the
  modelling DB is never opened for writing, so its **file md5 is provably unchanged**
  (`60aa6798…` before and after the fetch; all 7 tables byte-identical, `daily_ohlc` absent).
  Rules, do not relax them:
    * Nothing in `src/` reads `ohlc_display.db`, and nothing ever should. No feature, target
      or score derives from it. It exists only to draw the Company Detail price chart.
    * `daily_prices` (ADJUSTED close, in financials.db) remains the TARGET's price source —
      `src/price_target.py` builds `future_63d_sharpe` from it. The OHLC store is
      **unadjusted** on purpose (a chart should show prices as traded). The two series differ
      numerically BY DESIGN; mixing them would silently corrupt the target. Do not reconcile.
    * `fetch_ohlc.py` and `data.company_ohlc()` open their databases with `mode=ro` URIs, so
      they are structurally incapable of writing the modelling DB.
    * 97/97 tickers cached, 0 failures. A ticker with no cache falls back to the
      `daily_prices` adjusted-close line, then to a caption — a missing chart never errors.
  Chart: close-price line (no area — `mark_area` implies `y2=0` and would drag the domain to
  zero, overriding `zero=False`; a truncated baseline is correct for a LINE, which encodes
  position, and is only an anti-pattern for BARS, which encode length), hover crosshair
  (vertical + horizontal dashed rules), tooltip with Date/Close/Open/High/Low, and a
  green/red period-change badge (colour is earned here — it IS direction — and the sign is in
  the text). No volume bars.
- **Detail-page PERFORMANCE — three traps, all measured, do not undo:**
    1. **`opacity=alt.condition(sel, …)` renders a mark for EVERY datum and merely hides it.**
       Used for the crosshair rule it produced 1,644 invisible SVG nodes, hit-tested on every
       mousemove. Both crosshair rules now sit behind `transform_filter(hover)`, so each draws
       exactly ONE mark. SVG elements: **4,971 -> 724**; chart hover cost **98 -> 18 ms/move**
       (measured against a selenium baseline, old code run from a git worktree).
    2. **The chart is DOWNSAMPLED to weekly** (`company_ohlc_weekly`, ~1,640 -> ~341 rows) —
       real OHLC bars (open=first, high=max, low=min, close=last, date = last real trading day
       of the week), verified against the raw daily rows. The hover is therefore exact, not
       interpolated. The period-change badge still uses the DAILY frame: weekly-first-close
       would give +31.0% where the true first->last is +33.4%.
    3. **`ohlc_chart_spec()` caches the finished Vega spec per (ticker, mode)** and the caller
       uses `st.vega_lite_chart`. Building + `to_dict`-ing the Altair chart cost ~85 ms on
       every rerun; spec payload **180 KB -> 40 KB**. Also `app_logo_uri()` is now cached on
       file identity `(mtime, size)` — it was doing ~27 ms of Pillow trim + per-pixel luminance
       on EVERY rerun of EVERY page, while still allowing a dropped-in logo to appear with no
       restart. Median detail-open **879 -> 459 ms**.
  NOTE: `company_ohlc` was ALREADY `@st.cache_data`-cached and was never the bottleneck
  (0.1 ms warm); and hovering triggers no Streamlit rerun at all (no Vega selection is bound
  back to Python). Profile before assuming the loader is at fault.
- **Watchlist sort = pure alphabetical by the DISPLAYED ticker, numbers first.** Not
  sector-grouped (it used to be, via `ORDER BY sector, ticker`). The sort lives in
  `app.watchlist()` as a `.sort_values("_disp")`, NOT in `data.load_companies()`, because
  sorting on the display ticker needs `display_tickers()`, which itself calls
  `load_companies()` — putting it in the loader would be circular. (Every other consumer of
  `load_companies()` is order-independent: dict lookups, boolean filters, unique CSS
  selectors — so the loader's `ORDER BY sector, ticker` is retained and harmless.)
  The six numeric tickers (6758, 7203, 8306, 9988, 000660, 005930) are pushed to the END,
  after the letters, via a leading `_num` sort key. A plain string sort puts digits FIRST
  (ASCII), so that key deliberately overrides it: `sort_values(["_num", "_disp"])`.
- **Display tickers are STRIPPED; the real ticker is always the key.** `data.display_tickers()`
  maps `SHEL.L -> SHEL`, `005930.KS -> 005930` (only the dot-suffix; `BRK-B` and `NOVO-B` keep
  their share class). Used ONLY for rendered text in the Watchlist, the Ranking table and the
  basket chips. Widget keys, `session_state["selected"]`, row-click routing, logo lookup and
  every DB/predictions join stay on the REAL ticker — a display string is not a valid key
  (all 22 stripped names fail a `logo_uris()` lookup). **Company Detail always shows the full
  exchange-qualified ticker** (`.tkfull`), so the exact symbol remains available.
  `display_ticker_collisions()` guards the transform: if two tickers would collapse to the
  same string (a US `SAN` alongside `SAN.MC`), BOTH keep their full suffix. No collisions in
  the current 97; the guard is verified against a synthetic collision.
- **Company icons: TradingView symbol logos, ROUND, vector.** `dashboard/fetch_logos.py`
  resolves each ticker to TradingView's `logoid` via their public symbol-search endpoint and
  caches `dashboard/logos/{TICKER}.svg` (+ `_manifest.csv`). **97/97 coverage, 0 fallbacks.**
  Rationale, evaluated for this universe: the SVGs are purpose-built 56×56 full-bleed squares
  with the brand colour as background, meant to be clipped to a circle — one vector asset is
  crisp at 26px (table), 40px (watchlist) and 58px (hero). The PREVIOUS source was
  DuckDuckGo/Google favicons: 16–64px browser-tab icons, blurry when scaled, square,
  inconsistently padded. `logo.dev` was rejected — HTTP 401 without an API token, so a
  credential + runtime dependency for a one-time static fetch. Clearbit is retired.
    * `Path.stem` strips only the last suffix, so `SAN.MC.svg` -> `SAN.MC` survives.
    * Rounding is `border-radius:50%` on our own HTML, but the **Backtest holdings** table is
      `st.dataframe`'s ImageColumn — a canvas grid CSS cannot reach — so `data.logo_uris_round()`
      clips the circle into the SVG source itself for that one surface.
    * TradingView serves a PARENT-GROUP mark for two names, and we keep it because that is
      what TradingView shows: SK hynix (000660.KS) -> `sk-telecom`, MUFG (8306.T) ->
      `mitsubishi-group`. Verified against their search API; pin alternatives in
      `LOGOID_OVERRIDES`. Missing logos fall back to a round sector-coloured initials badge of
      the same size, so a gap never breaks the layout.
- **Logo:** drop `dashboard/assets/logo.png` (any aspect ratio; auto-detected, no restart).
  `data.app_logo_uri(mode)` trims transparent padding on an ALPHA THRESHOLD (a plain
  `getbbox()` returns the full canvas — exported PNGs carry a sub-visible halo — which
  rendered the mark tiny), measures the artwork's luminance, and whitens dark ink on the navy
  theme via a CSS filter so it stays legible. To keep brand colour in dark mode instead, supply
  a light-ink `dashboard/assets/logo_dark.png`; it is used verbatim and bypasses the filter.

- **Every headline number is DERIVED from an artifact** — universe size, ablation max, the
  per-rebalance LS sequence, target std, VIF counts, and the **risk-free rate**
  (`data.risk_free_annual()` reads `target_63d.risk_free_annual` back from the DB). Nothing
  about "97" or "2%" is hard-coded, so a pipeline rerun cannot leave the narrative stale. Do
  NOT reintroduce literals. (The Backtest header used to hard-code "risk-free = 0"; the rf
  change made that string FALSE. That is exactly the failure this rule exists to prevent.)
- **NARRATIVE PROSE MUST BE SIGN-SAFE, not just numerically derived.** Two Backtest captions
  asserted "— no edge" / "the strategy adds no spread" against a then-negative cumulative LS.
  The rf retrain flipped the cumulative to **+11.4%** and both sentences became lies while
  every *number* around them stayed correct. They now derive the sign-flip count and a t-stat
  (`t = mean/(sd/√n)` on the per-rebalance spread) and say "not distinguishable from zero,
  whatever sign the cumulative figure takes". **Never let a conclusion depend on the sign of a
  number a rerun can move.** The evidence for the null is the flip + the t-stat, NOT the sign.
- **Confidence tiers** replace the old raw OOD flag. `out_of_training_dist` and
  `prediction_only` are IDENTICAL by construction (25 names) — surface them as ONE tier, not
  two. `no_release_date` (5) is a strict subset and a stronger caveat. Partition: 72 + 20 + 5.
- **`data.best_real_cv()` excludes degenerate models.** A naive `idxmax(cv_spearman_mean)`
  picks ElasticNet, which regularizes to a constant — advertising the null model as "best".
- **`data.target_std()` must mirror J_models**: RAW target (`future_63d_sharpe_raw`), rows
  `<= SPLIT_DATE`. Using the winsorized column or all train rows silently moves the
  mean-predictor reference line on the learning curves.
- **Palette is derived, not eyeballed.** Navy + indigo/purple accent; green/red RESERVED for
  performance semantics (never chrome, never reference lines, never metrics that hug zero).
  The 9 sector hues are one shared hue set stepped per mode, chosen to maximise the minimum
  ALL-PAIRS Machado protan/deutan ΔE (18.6 dark / 17.4 light, target ≥12). The OLD palette
  failed: Industrials read gray (chroma 0.029) and Communication↔Industrials was ΔE 3.9.
- **`.streamlit/config.toml` MUST track ui.py's DARK palette.** Streamlit renders
  `st.dataframe` on a canvas grid and styles its widgets from its own theme object — CSS
  cannot reach either. The light/dark toggle therefore calls `_apply_native_theme()`
  **inside the button handler before `st.rerun()`** (the theme ships in NewSession, emitted
  at the START of a run — calling it from `main()`'s body applies one run late).
- **Logos are normalized at load** (`data._normalize_logo`): the fetched PNGs have wildly
  inconsistent padding (JPM's mark is 16×16 in a 128×128 canvas = 2% fill), so CSS
  `background-size` alone renders them as specks. Trimmed + re-centered in memory; the
  committed PNGs are untouched.
- **Charts never dramatise the null.** Near-zero metrics get neutral fills + a prominent
  reference rule. Classification AUC is plotted as **AUC − 0.5** off a zero baseline (raw AUC
  bars on a truncated [0.40,0.60] axis would exaggerate differences between models that are
  all at chance). Labels carry the true AUC.

### DASHBOARD — DISCLOSED CAVEATS (accepted, not bugs; do not "discover" them again)
1. **The sector palette is NOT tritan-safe.** It was optimised (and gates) on protan/deutan,
   which is what the reference validator gates on — tritan is reported for information only.
   Shipping tritan ΔE is low: **2.9 (dark) / 4.0 (light)**, all-pairs. Accepted because the
   sector badge NEVER encodes performance and always sits beside the ticker text with a
   sector-name hover title, so identity is never colour-alone (the skill's relief rule).
   If a future view ever encodes sector by colour ALONE, this must be revisited.
2. **`_apply_native_theme()` uses `st._config`, a PRIVATE Streamlit API.** It is the only way
   to reach `st.dataframe`'s canvas grid and Streamlit's own widgets, which ignore injected
   CSS. It is wrapped in try/except: if a Streamlit upgrade breaks it, our components stay
   correctly themed and only the native widgets fall back to `.streamlit/config.toml` (which
   is why that file must keep tracking the DARK palette). Verified working on Streamlit 1.58.
3. **Palette validation is reproduced in Python, not Node.** The dataviz skill ships
   `validate_palette.js`; no Node in this environment, so the six checks were ported. The port
   is verified against the reference palette's documented output (light 24.2 / dark 10.3) —
   it initially disagreed until the gating was corrected to protan+deutan only. Any future
   palette change must re-run that check, not eyeball ΔE.

## Working style

Be confident and decisive; lead without waiting for confirmation, but sequence safely
(read-only diagnostics before destructive writes; all config edits before a single
rebuild). State informed cautions once, then respect the user's decision — the user
makes final calls and owns them. Be explicit about which file each change goes in.
Prefer targeted patches over whole-file rewrites.

---

One-off jobs live as prompts/notes so this file stays durable standing context. The old
re-validation routine (formerly `.claude/revalidate.md`) is **RETIRED** and archived at
`docs/archive/revalidate.archived.md` — it documents the retired 4-layer validator and is NOT a
live routine.
