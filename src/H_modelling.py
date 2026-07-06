"""
H_modelling.py — analytical phase, step 5: assemble the MODELLING TABLE.

One row per (ticker, report_release_date), joining every feature to the target STRICTLY
on that key. Purely additive: creates ONE new table `modelling_data` and NEVER modifies
financial_facts / daily_prices / target_63d / kpi_values / scores / operative_scores.

DESIGN (confirmed decisions — do not deviate):
  1. REGRESSION target = continuous future_63d_sharpe (no classification labels).
  2. operative_score and financial_score are SEPARATE model features (the model learns
     their relative weight). competitive_advantage_score_w050 = 0.5*fin + 0.5*op is a
     REPORTING column only (fallback -> financial_score where operative missing).
  3. WINSORIZE ratio-tail features (ROIC, cash_conversion, *_growth_yoy) AND the target
     tails at the 1st/99th pct. Keep BOTH raw and winsorized columns.
  4. NO min-observations floor here — STEP 1 REPORTS the per-company obs distribution so
     the floor can be set from real data in the next step.

LOOK-AHEAD (cardinal rule):
  - Spine = `scores` (1662 rows); its key set is proven identical to `target_63d`, so the
    feature<->target join is exact. Every value on a row is knowable at report_release_date.
  - "prior" for change features = that ticker's immediately-preceding report BY
    report_release_date (chronological). A prior is NEVER a chronologically-later row.
    First obs per ticker has no prior -> change features NULL, first_obs=1.

MISSING (no fabrication):
  - operative missing (no scored row on the exact key, incl. all 20-F names whose operative
    is keyed on a different date) -> operative_score NULL + operative_missing=1.
  - target NULL (most-recent reports w/o a full forward window) -> kept, target_missing=1.
  - KPI not computable -> NULL, never 0/mean-filled. Change NULL unless BOTH ends present.

WINSOR CAVEAT: caps are computed on the FULL computable population here. At the train/test
split the final caps MUST be refit on TRAIN ONLY (flagged in the STEP 1 report).

USAGE (run from inside src/):
    python H_modelling.py            # STEP 1 DRY-RUN: build in memory + report, WRITE NOTHING
    python H_modelling.py --write    # STEP 2: create table + idempotent upsert + verify
"""
from __future__ import annotations

import sys
from contextlib import closing

import numpy as np

import B_database

# --------------------------------------------------------------------------- #
# feature definitions
# --------------------------------------------------------------------------- #
SUBSCORES = ("profitability", "growth", "cash_flow", "leverage", "efficiency", "investment")
SCORE_FEATURES = [f"{s}_score" for s in SUBSCORES] + ["financial_score"]

# core KPI ratios used as DIRECT features. free_cash_flow (a native-currency LEVEL) is
# deliberately EXCLUDED — CLAUDE.md forbids the raw level cross-sectionally; the margin is
# kept. Sector-specific KPIs (inventory_turnover, net_interest_margin, capital_retention)
# are included: missing stays NULL for names/sectors where they don't apply.
KPI_FEATURES = [
    # profitability
    "gross_margin", "operating_margin", "net_margin", "return_on_assets", "return_on_equity",
    # growth
    "revenue_growth_yoy", "operating_income_growth_yoy", "net_income_growth_yoy",
    "operating_cash_flow_growth_yoy",
    # cash flow
    "operating_cash_flow_margin", "free_cash_flow_margin", "cash_conversion",
    # leverage
    "debt_to_assets", "net_debt_to_assets", "cash_to_assets", "equity_ratio",
    # efficiency
    "asset_turnover", "operating_income_to_assets", "inventory_turnover",
    # investment
    "r_and_d_intensity", "capex_intensity", "reinvestment_rate",
    # capital efficiency
    "ROIC",
    # bank-specific
    "net_interest_margin", "capital_retention",
]

# ratio-tail KPIs to winsorize (near-zero-denominator blow-ups). Kept as both _raw and
# winsorized (name stays the winsorized/model column).
WINSOR_KPIS = ["ROIC", "cash_conversion", "revenue_growth_yoy",
               "operating_income_growth_yoy", "net_income_growth_yoy",
               "operating_cash_flow_growth_yoy"]
WINSOR_TARGET = ["future_63d_sharpe"]

# every column that gets a *_change (current - prior)
CHANGE_COLS = SCORE_FEATURES + ["operative_score", "competitive_advantage_score_w050"] + KPI_FEATURES

WINSOR_LO_PCT, WINSOR_HI_PCT = 1.0, 99.0


# --------------------------------------------------------------------------- #
# load
# --------------------------------------------------------------------------- #
def load() -> list[dict]:
    """Build one in-memory row per (ticker, report_release_date) with all level features
    and the target. Spine = scores; strict-key joins to kpi_values / operative_scores /
    target_63d. Change features + winsorization are applied afterwards."""
    with closing(B_database.get_connection()) as con:
        score_rows = [dict(r) for r in con.execute("SELECT * FROM scores")]
        kpi_rows = [dict(r) for r in con.execute(
            "SELECT ticker, report_release_date, company_group, kpi_name, value, computable "
            "FROM kpi_values")]
        op_rows = [dict(r) for r in con.execute(
            "SELECT ticker, report_release_date, operative_score, status, source "
            "FROM operative_scores")]
        tgt_rows = [dict(r) for r in con.execute(
            "SELECT ticker, report_release_date, future_63d_return, future_63d_volatility, "
            "future_63d_sharpe, status FROM target_63d")]
        # surrogate keys: the blocked non-US names (and ALV.DE's one unmatched period) have
        # NULL report_release_date, so downstream they are keyed on fiscal_period_end_date.
        # Flag those rows: they get NO target (target_missing) and never train (floor).
        no_rd_keys = {(r["ticker"], r["fiscal_period_end_date"]) for r in con.execute(
            "SELECT DISTINCT ticker, fiscal_period_end_date FROM financial_facts "
            "WHERE report_release_date IS NULL")}

    # wide KPI pivot + company_group lookup
    kpi_wide: dict[tuple, dict] = {}
    cgroup: dict[tuple, str] = {}
    for r in kpi_rows:
        key = (r["ticker"], r["report_release_date"])
        cgroup.setdefault(key, r["company_group"])
        if r["kpi_name"] in KPI_FEATURES:
            kpi_wide.setdefault(key, {})[r["kpi_name"]] = (
                r["value"] if r["computable"] else None)

    # operative resolution:
    #   op_exact  = scored operative on the EXACT (ticker, release_date) key (US edgar names).
    #   op_20f    = per-ticker sorted scored 20-F operative rows keyed on their FILING date,
    #               used as a LOOK-AHEAD-SAFE as-of fallback for the internationals whose
    #               yfinance scoring dates never coincide with the 20-F filing date. Attach
    #               the most recent 20-F operative whose filing date is ON OR BEFORE the
    #               report release date (strictly no future 20-F). Integrated / no-20-F
    #               names have no scored 20-F row -> stay NULL.
    op_exact: dict[tuple, float] = {}
    op_20f: dict[str, list[tuple]] = {}
    for r in op_rows:
        if r["status"] != "scored" or r["operative_score"] is None:
            continue
        op_exact[(r["ticker"], r["report_release_date"])] = r["operative_score"]
    for r in op_rows:
        if r["status"] == "scored" and r["operative_score"] is not None and r["source"] == "edgar-20f":
            op_20f.setdefault(r["ticker"], []).append(
                (r["report_release_date"], r["operative_score"]))
    for lst in op_20f.values():
        lst.sort()

    def resolve_operative(ticker: str, release: str):
        """Return (score, match_kind, asof_date). exact -> as-of 20-F -> NULL."""
        v = op_exact.get((ticker, release))
        if v is not None:
            return v, "exact", release
        cands = [(d, s) for d, s in op_20f.get(ticker, []) if d <= release]
        if cands:
            d, s = cands[-1]  # most recent 20-F filed on or before the release date
            return s, "asof_20f", d
        return None, None, None

    tgt_map = {(r["ticker"], r["report_release_date"]): r for r in tgt_rows}

    rows: list[dict] = []
    for s in score_rows:
        key = (s["ticker"], s["report_release_date"])
        row: dict = {
            "ticker": s["ticker"],
            "sector": s["sector"],
            "company_group": cgroup.get(key),
            "source": s["source"],
            "form": s["form"],
            "frequency": s["frequency"],
            "period": s["period"],
            "report_release_date": s["report_release_date"],
            "fiscal_period_end_date": s["fiscal_period_end_date"],
            "peer_group_size": s["peer_group_size"],
        }
        # score-level features
        for col in SCORE_FEATURES:
            row[col] = s[col]

        # operative: exact same-date match, else look-ahead-safe as-of 20-F match.
        op_val, op_match, op_asof = resolve_operative(s["ticker"], s["report_release_date"])
        row["operative_score"] = op_val
        row["operative_missing"] = 0 if op_val is not None else 1
        row["operative_match"] = op_match          # 'exact' | 'asof_20f' | None
        row["operative_asof_date"] = op_asof        # 20-F filing date used (audit)

        # w=0.5 reporting column (fallback -> financial_score where operative missing)
        fin = row["financial_score"]
        if row["operative_missing"] == 0 and fin is not None:
            row["competitive_advantage_score_w050"] = 0.5 * fin + 0.5 * row["operative_score"]
        else:
            row["competitive_advantage_score_w050"] = fin  # fallback (may be None)

        # KPI level features (raw; winsorized copies added later)
        kw = kpi_wide.get(key, {})
        for k in KPI_FEATURES:
            row[k] = kw.get(k)  # None if not computable / absent

        # target (strict key; identical key set proven)
        t = tgt_map.get(key)
        if t is not None:
            row["future_63d_return"] = t["future_63d_return"]
            row["future_63d_volatility"] = t["future_63d_volatility"]
            row["future_63d_sharpe"] = t["future_63d_sharpe"]
        else:
            row["future_63d_return"] = row["future_63d_volatility"] = row["future_63d_sharpe"] = None
        row["target_missing"] = 1 if row["future_63d_sharpe"] is None else 0
        # surrogate-keyed (no real release date) -> report_release_date column holds the
        # period-end; flag it so the ranking/dashboard can show "no release date" honestly.
        row["no_release_date"] = 1 if key in no_rd_keys else 0

        rows.append(row)
    return rows


# --------------------------------------------------------------------------- #
# winsorization
# --------------------------------------------------------------------------- #
def winsorize(rows: list[dict]) -> dict:
    """For each winsor column store {col}_raw = original, {col} = clipped to [p1,p99]
    computed over all non-None values. Returns caps+counts for the report."""
    report: dict[str, dict] = {}
    for col in WINSOR_KPIS + WINSOR_TARGET:
        vals = np.array([r[col] for r in rows if r[col] is not None], dtype=float)
        if vals.size == 0:
            report[col] = {"n": 0, "lo": None, "hi": None, "capped_lo": 0, "capped_hi": 0}
            for r in rows:
                r[f"{col}_raw"] = r[col]
            continue
        lo = float(np.percentile(vals, WINSOR_LO_PCT))
        hi = float(np.percentile(vals, WINSOR_HI_PCT))
        capped_lo = capped_hi = 0
        for r in rows:
            v = r[col]
            r[f"{col}_raw"] = v
            if v is None:
                continue
            if v < lo:
                r[col] = lo
                capped_lo += 1
            elif v > hi:
                r[col] = hi
                capped_hi += 1
        report[col] = {"n": int(vals.size), "lo": lo, "hi": hi,
                       "capped_lo": capped_lo, "capped_hi": capped_hi}
    return report


# --------------------------------------------------------------------------- #
# change features (current - prior, prior = immediately-preceding report by release date)
# --------------------------------------------------------------------------- #
def add_change_features(rows: list[dict]) -> None:
    """Set first_obs and {col}_change for every CHANGE_COLS column. Prior = the
    immediately-preceding SAME-FREQUENCY report by release date (annual diffs against prior
    annual, quarterly against prior quarterly) — because financial_score is a WITHIN-
    frequency percentile, so cross-frequency diffs would mix ranking populations. Change
    uses the winsorized/model column value; NULL unless BOTH ends present. first_obs=1 means
    no same-frequency prior exists."""
    by_key: dict[tuple, list[dict]] = {}
    for r in rows:
        by_key.setdefault((r["ticker"], r["frequency"]), []).append(r)

    for lst in by_key.values():
        lst.sort(key=lambda r: r["report_release_date"])
        prev: dict | None = None
        for r in lst:
            r["first_obs"] = 1 if prev is None else 0
            r["prior_release_date"] = None if prev is None else prev["report_release_date"]
            for col in CHANGE_COLS:
                cur = r.get(col)
                pv = prev.get(col) if prev is not None else None
                r[f"{col}_change"] = (cur - pv) if (cur is not None and pv is not None) else None
            prev = r


# --------------------------------------------------------------------------- #
# STEP 1 report
# --------------------------------------------------------------------------- #
def _f(v):
    return f"{v:+.4f}" if isinstance(v, (int, float)) and v is not None else " NULL "


def report(rows: list[dict], wins: dict) -> None:
    n = len(rows)
    has_t = sum(r["target_missing"] == 0 for r in rows)
    first = sum(r["first_obs"] == 1 for r in rows)
    op_present = sum(r["operative_missing"] == 0 for r in rows)
    usable = sum(r["target_missing"] == 0 and r["first_obs"] == 0 for r in rows)

    print("=" * 92)
    print("STEP 1 DRY-RUN — modelling_data assembled IN MEMORY. NOTHING WRITTEN.")
    print("=" * 92)
    print(f"\nTOTAL rows: {n}   |   distinct tickers: {len({r['ticker'] for r in rows})}")
    print(f"  has-target ............ {has_t:5}     target_missing ...... {n - has_t}")
    print(f"  has-change (non-first)  {n - first:5}     first_obs (no prior)  {first}")
    print(f"  operative present ..... {op_present:5}     operative_missing ... {n - op_present}")
    print(f"  TRAIN-USABLE (target AND change) ......... {usable}")

    # operative coverage (exact same-date vs look-ahead-safe as-of 20-F vs missing)
    from collections import Counter
    match_by = Counter(r["operative_match"] or "MISSING" for r in rows)
    print("\n  operative coverage:")
    for k in ("exact", "asof_20f", "MISSING"):
        print(f"      {k:10} {match_by.get(k, 0)}")
    miss_by_src = Counter(r["source"] for r in rows if r["operative_missing"] == 1)
    print("  operative_missing by source:")
    for src, c in sorted(miss_by_src.items()):
        print(f"      {src:14} {c}")

    # as-of match proof: internationals now recovered, filing date <= release date
    print("\n  AS-OF 20-F MATCHES (proof: operative_asof_date <= report_release_date):")
    asof = [r for r in rows if r["operative_match"] == "asof_20f"]
    print(f"      {len(asof)} rows recovered across "
          f"{len({r['ticker'] for r in asof})} intl names")
    seen = set()
    for r in sorted(asof, key=lambda r: (r["ticker"], r["report_release_date"])):
        if r["ticker"] in seen:
            continue
        seen.add(r["ticker"])
        ok = "OK" if r["operative_asof_date"] <= r["report_release_date"] else "!! FUTURE !!"
        print(f"      {r['ticker']:10} release={r['report_release_date']} "
              f"<- 20-F filed {r['operative_asof_date']}  op={_f(r['operative_score'])}  {ok}")

    # ---- per-company observation-count distribution ----
    from collections import defaultdict
    per: dict[str, dict] = defaultdict(lambda: {"tot": 0, "tgt": 0, "chg": 0, "both": 0})
    for r in rows:
        p = per[r["ticker"]]
        p["tot"] += 1
        if r["target_missing"] == 0:
            p["tgt"] += 1
        if r["first_obs"] == 0:
            p["chg"] += 1
        if r["target_missing"] == 0 and r["first_obs"] == 0:
            p["both"] += 1

    print("\n" + "=" * 92)
    print("PER-COMPANY OBSERVATION COUNTS  (set the min-obs floor from this)")
    print("  tot=all rows | tgt=with target | chg=with change features | both=train-usable")
    print("=" * 92)
    print(f"  {'ticker':10} {'tot':>4} {'tgt':>4} {'chg':>4} {'both':>5}")
    for tk in sorted(per, key=lambda t: (per[t]["both"], per[t]["tot"])):
        p = per[tk]
        print(f"  {tk:10} {p['tot']:>4} {p['tgt']:>4} {p['chg']:>4} {p['both']:>5}")

    booth = sorted(p["both"] for p in per.values())
    tots = sorted(p["tot"] for p in per.values())
    print(f"\n  train-usable (both) per company: min={booth[0]} "
          f"median={booth[len(booth)//2]} max={booth[-1]}")
    hist = Counter(p["both"] for p in per.values())
    print("  histogram of train-usable-per-company (count : #companies):")
    for k in sorted(hist):
        print(f"      both={k:>3} : {hist[k]} companies   {'#'*hist[k]}")
    # cumulative "if floor = f, companies kept / rows kept"
    print("\n  floor sensitivity (floor on train-usable rows-per-company):")
    print(f"      {'floor':>6} {'companies_kept':>15} {'usable_rows_kept':>17}")
    for floor in (1, 2, 3, 4, 5, 6, 8, 10):
        comps = [tk for tk in per if per[tk]["both"] >= floor]
        rows_kept = sum(per[tk]["both"] for tk in comps)
        print(f"      {floor:>6} {len(comps):>15} {rows_kept:>17}")

    # ---- sample full rows ----
    print("\n" + "=" * 92)
    print("SAMPLE ROWS (eyeball features / changes / fallback / target / prior date)")
    print("=" * 92)

    def latest(ticker, freq=None):
        c = [r for r in rows if r["ticker"] == ticker
             and (freq is None or r["frequency"] == freq) and r["first_obs"] == 0]
        return max(c, key=lambda r: r["report_release_date"]) if c else None

    samples = [
        ("AAPL", "quarterly", "US quarterly"),
        ("MSFT", "annual", "US annual"),
        ("SAP.DE", "annual", "non-US annual"),
        ("PM", None, "negative-equity (ROE/equity_ratio NULL)"),
        ("7203.T", None, "intl — operative recovered via as-of 20-F match"),
        ("SHEL.L", None, "integrated 20-F (no scored operative) -> stays NULL"),
    ]
    for tk, freq, note in samples:
        r = latest(tk, freq)
        if r is None:
            print(f"\n### {tk}: no non-first row"); continue
        print(f"\n### {tk} [{r['sector']} / {r['company_group']}] {r['form']} {r['frequency']} "
              f"release={r['report_release_date']}  prior={r['prior_release_date']}  — {note}")
        print(f"    financial_score={_f(r['financial_score'])}  operative_score={_f(r['operative_score'])}"
              f"  match={r['operative_match']} asof={r['operative_asof_date']}"
              f"  cas_w050={_f(r['competitive_advantage_score_w050'])}")
        print(f"    sub-scores: " + " ".join(f"{s[:4]}={_f(r[s+'_score'])}" for s in SUBSCORES))
        print(f"    KPIs: ROA={_f(r['return_on_assets'])} ROE={_f(r['return_on_equity'])} "
              f"op_margin={_f(r['operating_margin'])} rev_g={_f(r['revenue_growth_yoy'])} "
              f"ROIC={_f(r['ROIC'])}(raw={_f(r['ROIC_raw'])})")
        print(f"    CHANGES: fin_chg={_f(r['financial_score_change'])} "
              f"op_chg={_f(r['operative_score_change'])} ROA_chg={_f(r['return_on_assets_change'])} "
              f"revg_chg={_f(r['revenue_growth_yoy_change'])}")
        print(f"    TARGET: ret={_f(r['future_63d_return'])} vol={_f(r['future_63d_volatility'])} "
              f"sharpe={_f(r['future_63d_sharpe'])}(raw={_f(r['future_63d_sharpe_raw'])}) "
              f"target_missing={r['target_missing']}")

    # ---- winsorization report ----
    print("\n" + "=" * 92)
    print("WINSORIZATION (1st/99th pct on FULL computable population)")
    print("  CAVEAT: final caps MUST be refit on TRAIN ONLY at split time (leakage-safe).")
    print("=" * 92)
    print(f"  {'column':34} {'n':>5} {'p1':>12} {'p99':>12} {'capped_lo':>10} {'capped_hi':>10}")
    for col, d in wins.items():
        lo = f"{d['lo']:.4f}" if d["lo"] is not None else "-"
        hi = f"{d['hi']:.4f}" if d["hi"] is not None else "-"
        print(f"  {col:34} {d['n']:>5} {lo:>12} {hi:>12} {d['capped_lo']:>10} {d['capped_hi']:>10}")

    # ---- NaN / integrity check ----
    feat_cols = (SCORE_FEATURES + ["operative_score", "competitive_advantage_score_w050"]
                 + KPI_FEATURES + [f"{c}_change" for c in CHANGE_COLS]
                 + ["future_63d_return", "future_63d_volatility", "future_63d_sharpe"])
    nan_hits = 0
    for r in rows:
        for c in feat_cols:
            v = r.get(c)
            if isinstance(v, float) and v != v:  # NaN
                nan_hits += 1
    print("\n" + "=" * 92)
    print(f"NaN CHECK across {len(feat_cols)} feature/target columns × {n} rows: "
          f"{nan_hits} NaN found (missing is NULL, never silent-NaN).")
    print("=" * 92)
    print("\nSTEP 1 complete. Review, then give the min-obs floor and I will --write.")


# --------------------------------------------------------------------------- #
# STEP 2 write
# --------------------------------------------------------------------------- #
def column_spec() -> list[tuple[str, str]]:
    """(name, sqltype) in write order."""
    cols: list[tuple[str, str]] = [
        ("ticker", "TEXT NOT NULL"), ("report_release_date", "TEXT NOT NULL"),
        ("fiscal_period_end_date", "TEXT"), ("sector", "TEXT"), ("company_group", "TEXT"),
        ("source", "TEXT"), ("form", "TEXT"), ("frequency", "TEXT"), ("period", "TEXT"),
        ("peer_group_size", "INTEGER"),
        ("first_obs", "INTEGER"), ("prior_release_date", "TEXT"),
        ("operative_missing", "INTEGER"), ("operative_match", "TEXT"),
        ("operative_asof_date", "TEXT"), ("target_missing", "INTEGER"),
        ("no_release_date", "INTEGER"), ("train_eligible", "INTEGER"),
    ]
    for c in SCORE_FEATURES + ["operative_score", "competitive_advantage_score_w050"]:
        cols.append((c, "REAL"))
    for k in KPI_FEATURES:
        cols.append((k, "REAL"))
        if k in WINSOR_KPIS:
            cols.append((f"{k}_raw", "REAL"))
    for c in ("future_63d_return", "future_63d_volatility", "future_63d_sharpe",
              "future_63d_sharpe_raw"):
        cols.append((c, "REAL"))
    for c in CHANGE_COLS:
        cols.append((f"{c}_change", "REAL"))
    return cols


def create_table() -> None:
    spec = column_spec()
    ddl = ("CREATE TABLE IF NOT EXISTS modelling_data (\n  "
           + ",\n  ".join(f"{n} {t}" for n, t in spec)
           + ",\n  created_at TEXT DEFAULT CURRENT_TIMESTAMP"
           + ",\n  PRIMARY KEY (ticker, report_release_date)\n)")
    with closing(B_database.get_connection()) as con:
        con.execute(ddl)
        con.execute("CREATE INDEX IF NOT EXISTS idx_md_grp ON modelling_data "
                    "(sector, frequency, period)")
        con.commit()


PROTECTED = ("financial_facts", "daily_prices", "target_63d", "kpi_values",
             "scores", "operative_scores")


def _counts(con) -> dict:
    return {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in PROTECTED}


def set_train_eligible(rows: list[dict], floor: int) -> set:
    """Mark train_eligible=1 on rows usable for TRAINING (NOT a delete). A row qualifies
    iff (a) its company has >= floor train-usable rows [target AND change], AND (b) the row
    itself has target AND change (not first_obs, not target_missing). Internationals below
    the floor and every first-obs / target-missing row are train_eligible=0 but RETAINED in
    modelling_data for prediction/ranking. Returns the set of qualifying companies."""
    from collections import Counter
    both = Counter()
    for r in rows:
        if r["target_missing"] == 0 and r["first_obs"] == 0:
            both[r["ticker"]] += 1
    qualifying = {tk for tk, c in both.items() if c >= floor}
    for r in rows:
        r["train_eligible"] = 1 if (
            r["ticker"] in qualifying and r["target_missing"] == 0 and r["first_obs"] == 0
        ) else 0
    return qualifying


def write(rows: list[dict], floor: int | None) -> None:
    """Set the train_eligible flag from the floor (retain-not-delete) then idempotent-upsert
    ALL rows of modelling_data."""
    floor = floor if floor is not None else 1
    qualifying = set_train_eligible(rows, floor)
    n_elig = sum(r["train_eligible"] for r in rows)
    n_pred = len(rows) - n_elig
    intl = sorted({r["ticker"] for r in rows if r["source"] != "edgar"})
    intl_elig = sum(r["train_eligible"] for r in rows if r["source"] != "edgar")
    print(f"train_eligible criterion: floor={floor} train-usable rows per company.")
    print(f"  qualifying companies (train): {len(qualifying)}")
    print(f"  train_eligible rows ...... {n_elig}")
    print(f"  prediction-only rows ..... {n_pred}")
    print(f"  internationals retained: {len(intl)} names, "
          f"{sum(r['source'] != 'edgar' for r in rows)} rows, "
          f"train_eligible among them = {intl_elig} (expected 0)")

    create_table()
    cols = [n for n, _ in column_spec()]
    placeholders = ", ".join(f":{c}" for c in cols)
    with closing(B_database.get_connection()) as con:
        before = _counts(con)
        con.executemany(
            f"INSERT OR REPLACE INTO modelling_data ({', '.join(cols)}) VALUES ({placeholders})",
            [{c: r.get(c) for c in cols} for r in rows],
        )
        con.commit()
        after = _counts(con)
        nm = con.execute("SELECT COUNT(*) FROM modelling_data").fetchone()[0]
        nt = con.execute("SELECT COUNT(DISTINCT ticker) FROM modelling_data").fetchone()[0]

    print(f"\nWrote {nm} rows to modelling_data — {nt} distinct tickers.")
    print("Protected-table row counts:")
    for t in before:
        flag = "UNCHANGED" if before[t] == after[t] else "CHANGED! investigate"
        print(f"   {t:16} {before[t]} -> {after[t]}  ({flag})")


# --------------------------------------------------------------------------- #
def build(rows_only: bool = False):
    rows = load()
    wins = winsorize(rows)
    add_change_features(rows)
    return (rows, wins)


def main(argv: list[str]) -> None:
    rows, wins = build()
    if "--write" in argv:
        floor = None
        for a in argv:
            if a.startswith("--floor="):
                floor = int(a.split("=", 1)[1])
        write(rows, floor)
        print("\nSTEP 2 complete.")
    else:
        report(rows, wins)


if __name__ == "__main__":
    main(sys.argv[1:])
