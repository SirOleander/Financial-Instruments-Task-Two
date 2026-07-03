---
name: operative-scores
description: Operative (qualitative competitive-advantage) LLM score — src/G_operative.py + operative_scores table, US 10-K/10-Q + intl 20-F
metadata:
  type: project
---

The operative (qualitative) score layer is DONE. `src/G_operative.py` scores each report's
filing narrative with an LLM into NEW table `operative_scores` (PK (ticker,report_release_date,
accession_number); cols: source, form, operative_score_raw 1-5, operative_score=(raw-1)/4 [0,1],
raw_scores JSON, model, prompt_version, truncated, mdna_source, status). Additive; never touches
financial_facts/daily_prices/target_63d/kpi_values/scores (all proven unchanged before/after).

**Rubric (prompt_version op-v2-compadv):** ONE 1-5 competitive-advantage score across six
evidence-weighted dimensions (pricing power, innovation/IP, customer stickiness, margin
resilience, market leadership, brand strength). Evidence-ONLY + issuer-anonymized + look-ahead
locked (score only from THIS filing's text; ignore outside/after-the-fact knowledge). NOT tone/
sentiment (an earlier tone rubric was rejected — it scored measured incumbents low, upbeat
turnarounds high). Measures competitive advantage from filing evidence, not company reputation.

**Machinery:** LiteLLM endpoint (base https://litellm.s.studiumdigitale.uni-frankfurt.de),
model qwen3.5-122b-a10b, temp 0, key from env LITELLM_API_KEY (NEVER hardcode; user sources
C:\Users\fynne\litellm_key.sh). requests-based (no openai pkg). N_VOTES=1 (single call, cache
freezes). Cache by accession (skip status='scored'), idempotent upsert, resumable. Concurrency 16
(endpoint per-call latency ~130s is the limiter; saturates >16). MD&A-dominant payload cap 50k
(MD&A whole, Risk 10k, Business 4k). MD&A required: if unextractable -> status='missing' (never
score on Risk/Business alone). mdna_source = primary / primary_title / ex13 / none.

**Coverage:** US EDGAR 10-K/10-Q (Stage 1): 1521 rows, 1491 scored / 30 missing. Intl 20-F
(Stage 2, since 2020): 76 rows, 55 scored / 21 missing. TOTAL 1597 rows, 1546 scored. 79/89
tickers scored; 3 integrated-report 20-F filers (ASML.AS/SHEL.L/SAN.MC) all-missing (Item 5 only
in cross-ref table, not reliably isolable — bespoke extraction too fragile, honest missing
chosen); 7/89 have NO operative (000660.KS/005930.KS/HSBA.L/RY.TO/SHOP.TO/SIE.DE/TD.TO — not in
the 11 20-F filers). 20-F filings located on EDGAR by CIK resolved from ADR ticker via SEC
company_tickers.json (ADR_MAP in G_operative); report_release_date = 20-F filingDate.

Downstream: competitive_advantage_score = w*financial_score + (1-w)*strategic_score, where
strategic_score = operative_score; falls back to financial_score where operative is missing.
Related: [[scores-table]], [[kpi-values-table]].
