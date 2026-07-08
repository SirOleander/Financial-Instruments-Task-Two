"""verify.py — the proof harness: fingerprints + the project's invariants.

Two jobs, both READ-ONLY. Nothing here ever writes to the database.

1. FINGERPRINT — a deterministic content hash of every DB table and every generated
   artifact, so a refactor can be PROVEN behaviour-preserving:

       python src/fi/verify.py --save-baseline proofs/baseline.json
       ... move code around ...
       python src/fi/verify.py --check proofs/baseline.json      # must be green

   Table hashes deliberately EXCLUDE the volatile columns `id` and `created_at`.
   `financial_facts.id` is AUTOINCREMENT and `created_at` defaults to CURRENT_TIMESTAMP;
   every write path uses INSERT OR REPLACE, which DELETES and RE-INSERTS the row, so both
   columns change on a no-op rewrite while every meaningful value stays identical. Hashing
   them would make a true no-op look like a change. Rows are sorted before hashing, so the
   hash is independent of physical row order too.

2. INVARIANTS — the project's load-bearing guarantees, as executable assertions.

   They come in two flavours, and the distinction matters:

   * STRUCTURAL invariants hold for ANY valid state of this pipeline, including after new
     data arrives. Look-ahead safety, the risk-free rate, the firewall, the long-short sign
     convention, the forward-window rule. These are checked on EVERY run.

   * BASELINE-RELATIVE checks pin exact counts and metric values. These are NOT invariants
     of a living pipeline — ingesting a new quarter of reports legitimately moves them. They
     are only checked when a baseline is supplied, and they are what gates the refactor.

   Pinning row counts as if they were structural invariants would make the verifier fire on
   perfectly correct new data. That would train us to ignore it, which is worse than not
   having it.

USAGE (from the repo root):
    python src/fi/verify.py                              # structural invariants only
    python src/fi/verify.py --baseline proofs/baseline.json   # + baseline-relative checks
    python src/fi/verify.py --save-baseline proofs/baseline.json
    python src/fi/verify.py --check proofs/baseline.json  # fingerprint diff, exit 1 on drift
    python src/fi/verify.py --db /tmp/copy.db            # run against a DB copy

Exit code 0 = all green, 1 = any failure. Intended to be callable from the pipeline and
from CI, and to stay import-free of the rest of the package so it works identically at
every step of the refactor.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "data" / "financials.db"
OHLC_DB = ROOT / "data" / "ohlc_display.db"
ARTIFACT_DIRS = ("predictions", "analysis", "eda")

# Rewritten by every INSERT OR REPLACE; carry no information. See module docstring.
VOLATILE_COLS = frozenset({"id", "created_at"})

# `sqlite_sequence` is SQLite bookkeeping for AUTOINCREMENT, not project data.
SKIP_TABLES = frozenset({"sqlite_sequence"})

SPLIT_DATE = "2025-03-31"
EXPECTED_RF = 0.02
EXPECTED_UNIVERSE = 97
TRADING_DAYS_PER_YEAR = 252
FORWARD_WINDOW = 63
NULL_TOL = 0.05          # |rank correlation| below this is "indistinguishable from zero"


# --------------------------------------------------------------------------- #
# fingerprinting
# --------------------------------------------------------------------------- #
def _connect(db: Path) -> sqlite3.Connection:
    """Read-only URI connection: structurally incapable of writing."""
    return sqlite3.connect(f"file:{db}?mode=ro", uri=True)


def table_names(con: sqlite3.Connection) -> list[str]:
    rows = con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    return [r[0] for r in rows if r[0] not in SKIP_TABLES]


def hash_table(con: sqlite3.Connection, table: str) -> dict:
    """Content hash of one table: volatile columns dropped, rows sorted, values repr'd.

    `repr` on a Python float round-trips exactly (it prints the shortest string that parses
    back to the same double), so this is a lossless value hash, not a formatted one.
    """
    cols = [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
    keep = [c for c in cols if c not in VOLATILE_COLS]
    quoted = ", ".join(f'"{c}"' for c in keep)
    rows = con.execute(f"SELECT {quoted} FROM {table}").fetchall()
    # sort AFTER stringifying so mixed types (None/str/float) order deterministically
    lines = sorted("\x1f".join(repr(v) for v in row) for row in rows)
    h = hashlib.sha256("\x1e".join(lines).encode("utf-8")).hexdigest()
    return {"rows": len(rows), "columns": keep, "sha256": h}


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprint(db: Path = DEFAULT_DB) -> dict:
    """Full content fingerprint: every table + every generated artifact + the OHLC store."""
    with _connect(db) as con:
        tables = {t: hash_table(con, t) for t in table_names(con)}

    artifacts: dict[str, str] = {}
    for d in ARTIFACT_DIRS:
        base = ROOT / d
        if not base.is_dir():
            continue
        for f in sorted(base.rglob("*")):
            if f.is_file():
                artifacts[f.relative_to(ROOT).as_posix()] = hash_file(f)

    return {
        "tables": tables,
        "artifacts": artifacts,
        # the display cache is a firewall subject: recorded, never rebuilt by this pipeline
        "ohlc_display_sha256": hash_file(OHLC_DB) if OHLC_DB.exists() else None,
    }


def compare(baseline: dict, current: dict) -> list[str]:
    """Return a list of human-readable differences. Empty list == provably identical."""
    diffs: list[str] = []

    b_t, c_t = baseline["tables"], current["tables"]
    for t in sorted(set(b_t) | set(c_t)):
        if t not in c_t:
            diffs.append(f"TABLE MISSING: {t}")
        elif t not in b_t:
            diffs.append(f"TABLE ADDED: {t} ({c_t[t]['rows']} rows)")
        elif b_t[t]["sha256"] != c_t[t]["sha256"]:
            diffs.append(f"TABLE CHANGED: {t}  rows {b_t[t]['rows']} -> {c_t[t]['rows']}")
            if b_t[t]["columns"] != c_t[t]["columns"]:
                added = set(c_t[t]["columns"]) - set(b_t[t]["columns"])
                removed = set(b_t[t]["columns"]) - set(c_t[t]["columns"])
                diffs.append(f"    columns  +{sorted(added)}  -{sorted(removed)}")

    b_a, c_a = baseline["artifacts"], current["artifacts"]
    for f in sorted(set(b_a) | set(c_a)):
        if f not in c_a:
            diffs.append(f"ARTIFACT MISSING: {f}")
        elif f not in b_a:
            diffs.append(f"ARTIFACT ADDED: {f}")
        elif b_a[f] != c_a[f]:
            diffs.append(f"ARTIFACT CHANGED: {f}")

    if baseline.get("ohlc_display_sha256") != current.get("ohlc_display_sha256"):
        diffs.append("FIREWALL: ohlc_display.db changed — the pipeline must never touch it")

    return diffs


# --------------------------------------------------------------------------- #
# invariants — structural (always) and baseline-relative (only with a baseline)
# --------------------------------------------------------------------------- #
class Result:
    __slots__ = ("name", "ok", "detail", "skipped")

    def __init__(self, name: str, ok: bool, detail: str, skipped: bool = False):
        self.name, self.ok, self.detail, self.skipped = name, ok, detail, skipped


def _read_csv(rel: str) -> pd.DataFrame | None:
    p = ROOT / rel
    return pd.read_csv(p) if p.exists() else None


def inv_universe(con) -> Result:
    """97 = the 98 mandated names minus GOOG (documented Alphabet share-class dedup)."""
    bad = []
    for t in ("financial_facts", "kpi_values", "scores", "modelling_data"):
        n = con.execute(f"SELECT COUNT(DISTINCT ticker) FROM {t}").fetchone()[0]
        if n != EXPECTED_UNIVERSE:
            bad.append(f"{t}={n}")
    goog = con.execute("SELECT COUNT(*) FROM financial_facts WHERE ticker='GOOG'").fetchone()[0]
    googl = con.execute("SELECT COUNT(*) FROM financial_facts WHERE ticker='GOOGL'").fetchone()[0]
    if goog:
        bad.append(f"GOOG present ({goog} rows) — dedup violated")
    if not googl:
        bad.append("GOOGL absent")
    return Result("universe = 97, GOOG deduped", not bad,
                  "; ".join(bad) or f"{EXPECTED_UNIVERSE} tickers, GOOGL kept, GOOG absent")


def inv_lookahead(con) -> Result:
    """t+1 must be STRICTLY after the release date, on the stock's own calendar."""
    n = con.execute(
        "SELECT COUNT(*) FROM target_63d "
        "WHERE status='ok' AND t1_date <= report_release_date").fetchone()[0]
    tot = con.execute("SELECT COUNT(*) FROM target_63d WHERE status='ok'").fetchone()[0]
    return Result("look-ahead: t+1 > release_date", n == 0,
                  f"{n} violations of {tot} scored rows")


def inv_risk_free(con) -> Result:
    """rf = 2% everywhere, and the audit identity sharpe = sharpe_rf0 - rf/ann_vol."""
    rates = [r[0] for r in con.execute(
        "SELECT DISTINCT risk_free_annual FROM target_63d WHERE risk_free_annual IS NOT NULL")]
    if rates != [EXPECTED_RF]:
        return Result("risk-free = 2%, audit identity", False, f"distinct rates: {rates}")
    df = pd.read_sql(
        "SELECT future_63d_sharpe s, future_63d_sharpe_rf0 s0, future_63d_volatility v "
        "FROM target_63d WHERE status='ok'", con)
    ann_vol = df["v"] * (TRADING_DAYS_PER_YEAR ** 0.5)
    err = (df["s"] - (df["s0"] - EXPECTED_RF / ann_vol)).abs().max()
    return Result("risk-free = 2%, audit identity", err < 1e-9,
                  f"rf=0.02 on all rows; max |sharpe - (sharpe_rf0 - rf/ann_vol)| = {err:.2e}")


def inv_forward_window(con) -> Result:
    """Incomplete forward windows get NULL targets — never a truncated Sharpe."""
    bad_short = con.execute(
        f"SELECT COUNT(*) FROM target_63d WHERE n_forward_days < {FORWARD_WINDOW} "
        "AND (status != 'insufficient_window' OR future_63d_sharpe IS NOT NULL)").fetchone()[0]
    bad_ok = con.execute(
        f"SELECT COUNT(*) FROM target_63d WHERE status='ok' "
        f"AND (n_forward_days != {FORWARD_WINDOW} OR future_63d_sharpe IS NULL)").fetchone()[0]
    return Result("forward-window discipline", bad_short == 0 and bad_ok == 0,
                  f"{bad_short} short windows mis-flagged, {bad_ok} 'ok' rows malformed")


def _code_without_comments_or_docstrings(src: str) -> str:
    """Executable source only: comments and docstrings stripped, other literals KEPT.

    A real firewall breach reads a path — `sqlite3.connect(".../ohlc_display.db")` — so we
    must NOT strip string literals in general. But documentation is entitled to NAME the
    store in order to state the prohibition (fi/market.py does exactly that). Docstrings and
    comments are therefore removed, and everything else is searched.
    """
    import io
    import tokenize

    docstring_pos = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", None)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                docstring_pos.add((body[0].value.lineno, body[0].value.col_offset))

    kept = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.COMMENT:
            continue
        if tok.type == tokenize.STRING and tok.start in docstring_pos:
            continue
        kept.append(tok.string)
    return "\n".join(kept)


def inv_firewall(con) -> Result:
    """The OHLC display cache is a SEPARATE database and no pipeline module may read it.

    Enforced against EXECUTABLE code, not prose: `fi/market.py`'s docstring names the store
    precisely in order to forbid it, and that must not read as a violation. A genuine breach
    would need a path string or an import, both of which survive the strip.
    """
    problems = []
    if con.execute("SELECT 1 FROM sqlite_master WHERE name='daily_ohlc'").fetchone():
        problems.append("daily_ohlc table found INSIDE financials.db")
    me = Path(__file__).resolve()
    for py in sorted((ROOT / "src").rglob("*.py")):
        if py.resolve() == me:
            continue  # this verifier NAMES the store in order to police it
        src = py.read_text(encoding="utf-8", errors="ignore")
        if "ohlc" not in src.lower():
            continue
        try:
            code = _code_without_comments_or_docstrings(src)
        except SyntaxError:  # pragma: no cover - a broken module is a louder problem
            code = src
        if "ohlc_display" in code.lower():
            problems.append(f"src module CODE references ohlc_display: "
                            f"{py.relative_to(ROOT).as_posix()}")
    return Result("firewall: OHLC store isolated", not problems,
                  "; ".join(problems) or "daily_ohlc absent; no src/ code reference "
                                         "(docstrings may name it)")


def inv_backtest_sign() -> Result:
    """gross_ls == long_ret - short_ret. Shorting profits when the stock FALLS.

    backtest_periods.csv is written with .round(4), so the tolerance is the CSV's own
    rounding, not a fudge factor.
    """
    df = _read_csv("predictions/backtest_periods.csv")
    if df is None:
        return Result("backtest sign: LS = long - short", True, "no artifact yet", skipped=True)
    err = (df["long_ret"] - df["short_ret"] - df["gross_ls"]).abs().max()
    return Result("backtest sign: LS = long - short", err <= 1.01e-4,
                  f"max |long - short - gross_ls| = {err:.2e} (csv rounds to 4dp)")


def inv_null_result() -> Result:
    """The near-null finding. A loud failure here means new data changed the CONCLUSION."""
    problems, notes = [], []
    cv = _read_csv("predictions/cv_results.csv")
    if cv is not None:
        m = cv["cv_spearman_mean"].abs().max()
        notes.append(f"max |CV rho| = {m:.4f}")
        if m >= NULL_TOL:
            problems.append(f"CV Spearman {m:.4f} >= {NULL_TOL}")
    tm = _read_csv("predictions/test_metrics.csv")
    if tm is not None:
        ens = tm[tm["model"].str.contains("ENSEMBLE")]
        if len(ens):
            v = abs(float(ens["test_spearman_pooled"].iloc[0]))
            notes.append(f"ensemble test rho = {v:.4f}")
            if v >= NULL_TOL:
                problems.append(f"ensemble test Spearman {v:.4f} >= {NULL_TOL}")
    ab = _read_csv("predictions/ablation_results.csv")
    if ab is not None:
        m = ab["cv_spearman"].abs().max()
        notes.append(f"ablation max |CV rho| = {m:.4f}")
        if m >= NULL_TOL:
            problems.append(f"ablation CV Spearman {m:.4f} >= {NULL_TOL}")
    for mdl in ("Lasso", "ElasticNet"):
        c = _read_csv(f"predictions/coef_{mdl}.csv")
        if c is not None:
            nz = int((c["coef"] != 0).sum())
            notes.append(f"{mdl} {nz}/{len(c)} non-zero")
            if nz != 0:
                problems.append(f"{mdl} selected {nz} features (was 0 — the null model)")
    if not notes:
        return Result("near-null result holds", True, "no artifacts yet", skipped=True)
    return Result("near-null result holds", not problems, "; ".join(problems or notes))


def inv_no_deletions(con, baseline: dict | None) -> Result:
    """Ingestion is APPEND-ONLY: raw-table row counts never shrink."""
    if not baseline:
        return Result("append-only: no deletions", True, "no baseline", skipped=True)
    shrunk = []
    for t in ("financial_facts", "daily_prices"):
        before = baseline["tables"].get(t, {}).get("rows")
        after = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        if before is not None and after < before:
            shrunk.append(f"{t}: {before} -> {after}")
    return Result("append-only: no deletions", not shrunk,
                  "; ".join(shrunk) or "financial_facts, daily_prices non-decreasing")


def inv_trainable_rows(con) -> Result:
    """Structural: a row may only train if it has a target AND a same-frequency prior.

    train_eligible=1 must therefore imply target_missing=0, first_obs=0, a non-NULL target
    and a real release date. Verified to hold on the current 1,314 rows; asserted so a
    future change to the floor logic cannot quietly admit an untargeted or prior-less row
    into training. Also reports the leak-free split partition (informational — the counts
    move legitimately when new reports arrive).
    """
    bad = con.execute(
        "SELECT COUNT(*) FROM modelling_data WHERE train_eligible=1 AND ("
        "target_missing=1 OR first_obs=1 OR no_release_date=1 "
        "OR future_63d_sharpe_raw IS NULL)").fetchone()[0]
    df = pd.read_sql(
        "SELECT report_release_date rd, train_eligible te, ticker FROM modelling_data", con)
    te = df[df["te"] == 1]
    tv = int((te["rd"] <= SPLIT_DATE).sum())
    ts = int((te["rd"] > SPLIT_DATE).sum())
    detail = (f"{bad} invalid; train_eligible={len(te)} ({te['ticker'].nunique()} companies) "
              f"= train+val {tv} + test {ts} @ {SPLIT_DATE}")
    return Result("trainable rows have target + prior", bad == 0 and tv + ts == len(te), detail)


def run_invariants(db: Path, baseline: dict | None) -> list[Result]:
    with _connect(db) as con:
        return [
            inv_universe(con),
            inv_lookahead(con),
            inv_risk_free(con),
            inv_forward_window(con),
            inv_firewall(con),
            inv_backtest_sign(),
            inv_null_result(),
            inv_trainable_rows(con),
            inv_no_deletions(con, baseline),
        ]


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", type=Path, default=DEFAULT_DB, help="database to inspect")
    ap.add_argument("--save-baseline", type=Path, help="write a fingerprint JSON and exit")
    ap.add_argument("--check", type=Path, help="compare against a baseline JSON; exit 1 on drift")
    ap.add_argument("--baseline", type=Path, help="baseline for baseline-relative invariants")
    args = ap.parse_args(argv)

    if args.save_baseline:
        fp = fingerprint(args.db)
        args.save_baseline.parent.mkdir(parents=True, exist_ok=True)
        args.save_baseline.write_text(json.dumps(fp, indent=2, sort_keys=True), encoding="utf-8")
        print(f"baseline -> {args.save_baseline}")
        print(f"  {len(fp['tables'])} tables, {len(fp['artifacts'])} artifacts")
        for t, v in sorted(fp["tables"].items()):
            print(f"    {t:20s} {v['rows']:>7,} rows  {v['sha256'][:16]}")
        return 0

    failed = 0

    if args.check:
        baseline = json.loads(args.check.read_text(encoding="utf-8"))
        diffs = compare(baseline, fingerprint(args.db))
        print("=" * 78)
        print(f"PROOF A — fingerprint vs {args.check}")
        print("=" * 78)
        if diffs:
            failed = 1
            for d in diffs:
                print(f"  DRIFT  {d}")
            print(f"\n  {len(diffs)} difference(s) — behaviour NOT preserved.")
        else:
            n = len(baseline["tables"]), len(baseline["artifacts"])
            print(f"  IDENTICAL — {n[0]} tables, {n[1]} artifacts, all content hashes match.")
        print()

    baseline = None
    if args.baseline:
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    elif args.check:
        baseline = json.loads(args.check.read_text(encoding="utf-8"))

    print("=" * 78)
    print("INVARIANTS")
    print("=" * 78)
    for r in run_invariants(args.db, baseline):
        if r.skipped:
            tag = "SKIP"
        elif r.ok:
            tag = "PASS"
        else:
            tag = "FAIL"
            failed = 1
        print(f"  [{tag}] {r.name:38s} {r.detail}")
    print()
    print("RESULT:", "ALL GREEN" if not failed else "FAILURES PRESENT")
    return failed


if __name__ == "__main__":
    sys.exit(main())
