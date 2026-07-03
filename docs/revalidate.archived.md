> **⚠️ RETIRED — ARCHIVED FOR REFERENCE ONLY.** The 4-layer validator this routine
> describes (`debug.py` writing `validation_flags.csv` / `concept_map.csv`) has been
> **retired** now that the extraction/data phase is closed. `src/debug.py` is now
> `src/verify_release_dates.py` (a release-date verifier only), and the two CSVs no
> longer exist. This document is kept solely to show how the retired validator worked —
> it is NOT a live routine. If a future EDGAR rebuild needs re-validation, a validator
> can be regenerated from the benign-flag ledger + per-name adjudications in CLAUDE.md.

# Re-validate the SEC retrievals

Confirm the companies were retrieved correctly, the same way it was done before.
"Validated" means **every flag is accounted for** — on the known-benign ledger in
CLAUDE.md or freshly investigated and explained — and no new/unexpected family
appears. It does NOT mean zero flags. Do not "fix" anything on the benign ledger.

Work read-only first:

1. From `src/`, run `python debug.py` against the current `data/financials.db`.
   Only run a full `D_pipeline.py` rebuild if the DB is stale or a config/client
   change requires it — and if so, heed the rebuild cautions in CLAUDE.md
   (especially TARGET_GROUPS finality and the AXP total_loans check).
2. Summarize `validation_flags.csv` by check × severity. Compare to the expected
   shape: ~406 net_income REVIEWs, ~117 concept-drift, ~66 duration-band (all 10-Q
   baseline orphans), ~68 scale-jump FAILs, ~23 frozen, ~14 heavy-fallback, plus the
   small margin/identity FAILs.
3. Reconcile every FAIL and REVIEW against the known-benign ledger. Surface ONLY what
   does not map to a known family — that is the signal. Expect the lone LRCX
   restructuring-charge identity break (2023-03-26 10-Q, ~4% off) as the one residual.
4. Confirm the extraction-bug families are clean: zero 10-K duration-band rows, and no
   ABBV/KLAC gross_profit or ABBV operating-margin FAILs (the ABBV/KLAC/GE selector
   fix should hold).
5. Spot-check via `concept_map.csv`: off-calendar names (ACN/COST/CSCO/INTU/KLAC/
   LRCX/PG) OCF/capex look like single quarters; the fixed positions (ABBV/KLAC
   gross_profit, GE cost_of_revenue) show extraction_method = calculated with sane
   values; AXP total_loans = 220,259M with card_member_loans = 207,247M.
6. If a prior financials.db snapshot is available, diff the two on key
   (ticker, accession_number, position), ignoring id/created_at, and report only rows
   whose value / selection_status / extraction_method / duration changed.

Report concisely: what's clean, what (if anything) is new and needs a human call, and
whether the retrieval looks correct.
