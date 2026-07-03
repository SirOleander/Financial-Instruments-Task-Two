================================================================================
## MILESTONE — data-acquisition phase COMPLETE (append/update; supersedes older
## "72 tickers / EDGAR-only" statements above where they conflict)
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

### Modelling-stage handling still pending (unchanged from before)
- Negative book equity (MCD/PM/BKNG/ABBV): exclude ROE/equity_ratio or floor denom.
- HealthA pharma gross margin (ABBV amortization-in-COGS): decide rev−cost consistent
  vs drop gross_margin for HealthA — applies to the non-US pharma (AZN/NOVN/NOVO) too,
  since they rank in the same Healthcare pool.