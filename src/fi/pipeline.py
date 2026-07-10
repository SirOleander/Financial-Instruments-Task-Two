"""pipeline.py — the single ordered entry point for the whole pipeline.

`python run_pipeline.py` runs every stage in dependency order:

  ingest (network)         compute (local, DB->DB)      artifacts (local, DB->files)
  ----------------------   --------------------------   ----------------------------
  sec_facts  (EDGAR)       kpis     -> kpi_values        eda      -> eda/
  yf_facts   (yfinance)    scores   -> scores            train    -> predictions/
  prices     (yfinance)    target   -> target_63d        backtest -> predictions/
  operative  (LLM, paid)   modelling-> modelling_data    analysis -> analysis/

Design decisions, all made in the Phase-0 plan and honoured here:

* APPEND-ONLY / living pipeline. A default run fetches the latest data and UPSERTS it; it
  never drops raw tables. (The one remaining destructive path, sec_facts' historical
  drop_existing, is removed in a separate, separately-proven step — this module wires it
  as-is.)

* --offline runs ONLY the local stages (compute + artifacts) from the raw tables already in
  the database. No network, no API key. This is the mode the refactor's equivalence proof
  uses: it must reproduce today's committed numbers exactly, isolating "did the refactor
  change logic" from "did new data change results".

* SKIP-IF-UNCHANGED without touching any stage's write path. Every DB write uses
  INSERT OR REPLACE, which resets `id` and `created_at`, so a content-identical rerun still
  rewrites the 30 MB file and dirties git. The pipeline snapshots the DB before the run and,
  unless --force, restores that snapshot byte-for-byte when the post-run CONTENT fingerprint
  (id/created_at excluded, per fi.verify) is unchanged. Net effect: a no-op run leaves the
  tracked DB untouched; a real data change is kept.

* PRE-RUN BACKUP. The snapshot doubles as a rolling safety backup at
  data/financials.db.bak_auto (git-ignored), taken before any stage runs.

* The LLM stage is key-guarded: with no LITELLM_API_KEY it warns and skips (existing cached
  scores are retained), so a live run still completes — exactly how GEV is handled.

USAGE (from the repo root):
    python run_pipeline.py               # every stage, latest data, then retrain
    python run_pipeline.py --offline     # local stages only, from existing raw tables
    python run_pipeline.py --list        # print the stage plan and exit
    python run_pipeline.py --verify      # run the invariant suite only (read-only)
    python run_pipeline.py --from kpis --to backtest
    python run_pipeline.py --force       # keep a content-identical DB rewrite (no restore)
"""
from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from fi import config, features, market, modelling, operative, sec, verify

log = logging.getLogger("fi.pipeline")

DB_PATH = Path(config.DATABASE_PATH)
BACKUP_PATH = DB_PATH.with_name("financials.db.bak_auto")


# --------------------------------------------------------------------------- #
# stage registry
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Stage:
    name: str
    description: str
    run: Callable[[], None]
    network: bool          # requires the internet / an API key -> skipped by --offline
    writes_db: bool        # mutates a financials.db table (governs the skip-if-unchanged snapshot)


# `operative.run_full()` defaults to concurrency=1. On a from-scratch build that is ~1,531
# SEQUENTIAL (SEC document fetch + LLM call) round-trips — MEASURED at ~114 s/filing during the
# dry run, i.e. ~48 HOURS. CLAUDE.md records that the original build used `--concurrency 16`;
# at 16 the same work took ~3 h (a ~16x speedup, also measured). Raising this is safe by
# construction: run_full's workers do NETWORK ONLY — every SQLite write happens on the main
# thread, exactly to avoid concurrent writers. See FINDINGS.md #3.
OPERATIVE_CONCURRENCY = 16

# The international 20-F operative pass only considers filings from this fiscal year onward —
# the value CLAUDE.md records for the original build (`--since-year 2020`).
OPERATIVE_INTL_SINCE_YEAR = 2020


def _no_key() -> bool:
    """True (and warns) when the LLM key is absent, so the caller can skip gracefully."""
    if os.environ.get(operative.ENV_KEY_NAME):
        return False
    log.warning("LITELLM_API_KEY not set -> skipping operative scoring. Cached scores are "
                "retained; any new filing stays operative_missing (falls back to "
                "financial_score), exactly as GEV is handled.")
    return True


def _operative_stage() -> None:
    """Score NEW US 10-K/10-Q filings via the LLM, reusing the accession cache. Key-guarded."""
    if _no_key():
        return
    operative.run_full(concurrency=OPERATIVE_CONCURRENCY)


def _operative_intl_stage() -> None:
    """Score NEW international 20-F filings via the LLM. Key-guarded, cache-reusing.

    A SEPARATE stage, not folded into `operative`, because it is a distinct filing type and a
    distinct cost centre: it can be skipped or resumed independently with `--from`/`--to`.

    Without it a from-scratch build produces NO 20-F scores at all, and the 11 conventional
    internationals fall back to `financial_score` — silently reproducing a poorer feature set
    than the committed one. Their scores feed `features`' as-of 20-F join (match to the most
    recent 20-F filed ON OR BEFORE the report release date), which is what yields the
    `operative_match='asof_20f'` rows. See FINDINGS.md #2.
    """
    if _no_key():
        return
    operative.run_intl(concurrency=OPERATIVE_CONCURRENCY,
                       since_year=OPERATIVE_INTL_SINCE_YEAR)


def _train_stage() -> None:
    """Both training artifacts: the ablation table and the main CV/test/ensemble outputs."""
    modelling.ablation()
    modelling.main_train()


STAGES: list[Stage] = [
    Stage("sec_facts", "EDGAR companyfacts -> financial_facts (US)",
          sec.main, network=True, writes_db=True),
    Stage("yf_facts", "yfinance fundamentals -> financial_facts (non-US)",
          lambda: market.main_yf_facts(write=True), network=True, writes_db=True),
    Stage("prices", "yfinance daily adjusted close -> daily_prices",
          lambda: market.main_prices(write=True), network=True, writes_db=True),
    # `target` runs HERE, directly after `prices`, and before kpis/scores/operative. It depends
    # only on daily_prices + financial_facts (verified: it reads none of the later tables), and
    # this restores the dependency order the pre-refactor README documented (price_target.py ran
    # before E_kpis.py). Several stages' before/after guards COUNT target_63d, so creating it
    # early removes an entire class of from-scratch failure at the source. See FINDINGS.md #5.
    Stage("target", "forward 63-day excess Sharpe -> target_63d",
          lambda: features.main_target(write=True), network=False, writes_db=True),
    Stage("kpis", "raw KPIs -> kpi_values",
          lambda: features.main_kpis(do_write=True), network=False, writes_db=True),
    Stage("scores", "sector-percentile sub-scores -> scores",
          lambda: features.main_scores(do_write=True), network=False, writes_db=True),
    Stage("operative", "LLM competitive-advantage score, US 10-K/10-Q -> operative_scores",
          _operative_stage, network=True, writes_db=True),
    Stage("operative_intl", "LLM competitive-advantage score, international 20-F -> operative_scores",
          _operative_intl_stage, network=True, writes_db=True),
    Stage("modelling", "join features + target -> modelling_data",
          lambda: features.main_modelling(["--write", "--floor=6"]), network=False, writes_db=True),
    Stage("eda", "feature diagnostics -> eda/",
          modelling.main_eda, network=False, writes_db=False),
    Stage("train", "CV + ensemble + ablation -> predictions/",
          _train_stage, network=False, writes_db=False),
    Stage("backtest", "walk-forward long/short -> predictions/",
          modelling.main_backtest, network=False, writes_db=False),
    Stage("analysis", "bias-variance / importance / classification -> analysis/",
          modelling.main_analysis, network=False, writes_db=False),
]
STAGE_INDEX = {s.name: i for i, s in enumerate(STAGES)}


# --------------------------------------------------------------------------- #
# skip-if-unchanged (content fingerprint of the DB tables, id/created_at excluded)
# --------------------------------------------------------------------------- #
def _db_table_fingerprint() -> dict:
    """{table: content-sha256} using fi.verify's hashing (excludes id/created_at)."""
    with verify._connect(DB_PATH) as con:
        return {t: verify.hash_table(con, t)["sha256"] for t in verify.table_names(con)}


def _db_table_rows() -> dict:
    """{table: row count} — the reference the append-only deletion check is measured against."""
    with verify._connect(DB_PATH) as con:
        return {t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                for t in verify.table_names(con)}


def _select(from_stage: str | None, to_stage: str | None, offline: bool) -> list[Stage]:
    lo = STAGE_INDEX[from_stage] if from_stage else 0
    hi = STAGE_INDEX[to_stage] if to_stage else len(STAGES) - 1
    if lo > hi:
        raise SystemExit(f"--from {from_stage} is after --to {to_stage}")
    chosen = STAGES[lo:hi + 1]
    return [s for s in chosen if not (offline and s.network)]


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--offline", action="store_true",
                    help="run only local stages (compute + artifacts) from existing raw tables")
    ap.add_argument("--from", dest="from_stage", metavar="STAGE", help="first stage to run")
    ap.add_argument("--to", dest="to_stage", metavar="STAGE", help="last stage to run")
    ap.add_argument("--list", action="store_true", help="print the stage plan and exit")
    ap.add_argument("--verify", action="store_true", help="run the invariant suite only and exit")
    ap.add_argument("--force", action="store_true",
                    help="keep a content-identical DB rewrite instead of restoring the snapshot")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    for name in (args.from_stage, args.to_stage):
        if name and name not in STAGE_INDEX:
            raise SystemExit(f"unknown stage {name!r}; choose from {list(STAGE_INDEX)}")

    if args.list:
        print("Stage plan (order is dependency order):\n")
        for i, s in enumerate(STAGES):
            tag = "net" if s.network else "   "
            print(f"  {i + 1:2d}. [{tag}] {s.name:11s} {s.description}")
        print("\n  [net] = network / API key required; skipped by --offline")
        return 0

    if args.verify:
        return verify.main(["--baseline", str(_default_baseline())] if _default_baseline() else [])

    plan = _select(args.from_stage, args.to_stage, args.offline)
    if not plan:
        print("No stages selected.")
        return 0

    writes = any(s.writes_db for s in plan)
    print("=" * 78)
    print(f"PIPELINE: {'OFFLINE ' if args.offline else ''}running {len(plan)} stage(s): "
          f"{', '.join(s.name for s in plan)}")
    print("=" * 78)

    # Did a database exist BEFORE this run? This is the precise fact that governs both the
    # snapshot (below) and the baseline-relative invariants (at the end). It must NOT be
    # inferred from `snapshot_before is None`, which is also true for an artifact-only run
    # (writes=False) against a perfectly good existing database.
    db_existed = DB_PATH.exists()

    # Row counts as this run STARTS. This — not a recorded baseline of a different database —
    # is the honest reference for the append-only "did this run delete anything?" check.
    # None on a from-scratch build, where the question has no answer. See FINDINGS.md #8.
    rows_before = _db_table_rows() if db_existed else None

    # FROM-SCRATCH GUARD: on a first build there is no database to snapshot, and
    # `shutil.copy2` on a nonexistent file raises FileNotFoundError before any stage runs.
    # Only back up / fingerprint when a database already exists.
    snapshot_before = None
    if writes and db_existed:
        shutil.copy2(DB_PATH, BACKUP_PATH)
        snapshot_before = _db_table_fingerprint()
        print(f"backup -> {BACKUP_PATH.name} ; DB content fingerprinted ({len(snapshot_before)} tables)\n")
    elif writes:
        print(f"no existing database at {DB_PATH.name} -> FROM-SCRATCH build; "
              "no snapshot to take, skip-if-unchanged disabled for this run.\n")

    t0 = time.time()
    failed: str | None = None
    for i, s in enumerate(plan, 1):
        print(f"[{i}/{len(plan)}] {s.name:11s} {s.description}")
        st = time.time()
        try:
            s.run()
        except Exception:
            # The stages are a dependency chain, so we STOP rather than continue: a later stage
            # would otherwise read a half-built table. The value here is a clear resume hint and
            # a non-zero exit code instead of a bare traceback that discards the run's context.
            failed = s.name
            traceback.print_exc()
            print(f"\n*** STAGE '{s.name}' FAILED after {time.time() - st:.1f}s.\n"
                  f"    Fix the cause, then resume with:  python run_pipeline.py "
                  f"--from {s.name}\n")
            break
        print(f"            done in {time.time() - st:.1f}s\n")

    if failed is not None:
        # Do NOT restore the snapshot: whatever earlier stages fetched is real work and must
        # survive so the run can be resumed with `--from`. Do NOT run the invariants either —
        # they would be evaluated against a half-built database.
        print(f"PIPELINE INCOMPLETE — stage '{failed}' failed after "
              f"{time.time() - t0:.1f}s. Work from earlier stages is RETAINED.")
        if writes and db_existed:
            print(f"A pre-run backup of the database is at {BACKUP_PATH.name}.")
        return 1

    # skip-if-unchanged: restore the byte-identical snapshot when content did not move.
    # Skipped entirely on a from-scratch build (snapshot_before is None): there is no prior
    # state to compare against or restore to, and `None.get(...)` would raise AttributeError.
    if writes and not args.force and snapshot_before is not None:
        after = _db_table_fingerprint()
        changed = [t for t in after if snapshot_before.get(t) != after[t]]
        if changed:
            print(f"DB CONTENT CHANGED: {', '.join(changed)} (kept). Backup at {BACKUP_PATH.name}.")
        else:
            shutil.copy2(BACKUP_PATH, DB_PATH)
            print("DB content unchanged -> restored the pre-run snapshot (byte-identical, git clean).")

    print(f"\nPipeline finished in {time.time() - t0:.1f}s.")

    # The append-only deletion check is measured against THIS RUN's starting row counts, never
    # against proofs/baseline.json (a fingerprint of a DIFFERENT database). That both makes the
    # check meaningful — it now detects a deletion caused by this run — and stops a from-scratch
    # build from reporting a spurious `daily_prices: 156666 -> 150557` deletion. With no prior
    # state (`rows_before is None`) the question is unanswerable and verify SKIPs it.
    return verify.main(["--db", str(DB_PATH)], deletion_ref=rows_before)


def _default_baseline() -> Path | None:
    p = config.BASE_DIR / "proofs" / "baseline.json"
    return p if p.exists() else None


if __name__ == "__main__":
    sys.exit(main())
