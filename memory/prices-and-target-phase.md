---
name: prices-and-target-phase
description: Daily-price ingest + forward-63d Sharpe target phase — new tables, 89-ticker universe, key decisions
metadata:
  type: project
---

The price + target phase (after fundamentals + release-date work) is DONE. Three new
`src/` scripts, all additive, none touch `financial_facts`:
- `price_probe.py` — read-only Stage-1 probe (per-ticker Yahoo currency/coverage/gap check).
- `price_ingest.py` — Stage-2 ingest into NEW table `daily_prices`
  (ticker, date, adjusted_close, currency, source; PK (ticker,date); `INSERT OR REPLACE`,
  idempotent). Adjusted close = `history(auto_adjust=True)['Close']`, native listing
  currency, never converted. Uniform start 2020-01-01 (earliest release 2020-09-15), end today.
- `price_target.py` — Stage-3 forward 63-trading-day target into NEW table `target_63d`
  (PK (ticker, report_release_date); carries fiscal_period_end_date, source). t+1 = first
  price row STRICTLY after release_date on that stock's OWN calendar; window t+1..t+63.
  future_63d_sharpe = mean(daily ret)/std(ret)*sqrt(252), **risk-free = 0**. Sharpe is the target.

**Why (universe decisions, human calls — not derivable from code):** user trimmed the
universe to **89 distinct tickers** (71 edgar + 18 yfinance) by dropping GOOG (kept GOOGL),
0700.HK (Tencent), 9988.HK (Alibaba) from config, then rebuilding clean: EDGAR
`D_pipeline.py` (wipes table) FIRST, then `yf_ingest.py --write` (re-adds 18 non-US) —
order is critical or the yfinance rows are lost. **TSM stays the US ADR (USD prices), NOT
local 2330.TW**, because its fundamentals were ingested under ticker 'TSM'.

**How to apply:** 5 non-US names have price-currency != fundamentals reporting_currency
(AZN/HSBA/SHEL report USD but trade GBp; NOVN USD/CHF; SHOP USD/CAD) — BENIGN, returns are
unitless and each series is internally single-currency. Target has 1573 real rows + 89 NULL
(status='insufficient_window' = each company's most-recent report, <63 fwd days as of the
run). Sharpe dist: min -5.56, median +0.74, max +7.49.
