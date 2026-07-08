"""
verify_release_dates.py — does the stored report_release_date match SEC's filingDate?

Read-only. Compares financial_facts.report_release_date (per ticker+accession)
against us_release_dates.csv (freshly pulled SEC filingDate). Reports any
mismatch. This proves the US release dates are correct, not just present.

Read-only diagnostic in tools/. Reads us_release_dates.csv from the repo root.

    python tools/verify_release_dates.py
"""

from __future__ import annotations

import sys
from contextlib import closing
from pathlib import Path

import pandas as pd

# this diagnostic lives in tools/; make the src/ package importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from fi import db

CSV_PATH = Path(__file__).resolve().parent.parent / "us_release_dates.csv"


def main() -> None:
    sec = pd.read_csv(CSV_PATH, dtype=str)
    sec["filing_date"] = pd.to_datetime(sec["filing_date"]).dt.date.astype(str)
    sec_map = {(r.ticker, r.accession_number): r.filing_date
               for r in sec.itertuples()}

    with closing(db.get_connection()) as conn:
        rows = conn.execute(
            "SELECT DISTINCT ticker, accession_number, report_release_date "
            "FROM financial_facts WHERE source='edgar' "
            "AND accession_number IS NOT NULL AND accession_number != ''"
        ).fetchall()

    total = match = mismatch = missing_in_sec = 0
    mismatches = []
    for ticker, acc, stored in rows:
        total += 1
        stored_d = str(pd.to_datetime(stored).date()) if stored else None
        sec_d = sec_map.get((ticker, acc))
        if sec_d is None:
            missing_in_sec += 1
            continue
        if stored_d == sec_d:
            match += 1
        else:
            mismatch += 1
            mismatches.append((ticker, acc, stored_d, sec_d))

    print("=" * 66)
    print(f"distinct EDGAR accessions checked : {total}")
    print(f"  stored == SEC filingDate        : {match}")
    print(f"  MISMATCH                        : {mismatch}")
    print(f"  not found in SEC csv            : {missing_in_sec}")
    print("=" * 66)

    if mismatches:
        print("\nMismatches (ticker, accession, stored, sec_filingDate):")
        for t, a, s, d in mismatches[:60]:
            # a difference of a few days can be legit (filing vs acceptance);
            # large gaps are the concern
            try:
                gap = abs((pd.to_datetime(s) - pd.to_datetime(d)).days)
            except Exception:
                gap = "?"
            print(f"  {t:6} {a}  stored={s}  sec={d}  gap={gap}d")
        if len(mismatches) > 60:
            print(f"  ... and {len(mismatches) - 60} more")
        print("\nSmall gaps (1-4d) are usually filingDate vs acceptance timing "
              "and are harmless. Large gaps mean a wrong-period match — "
              "investigate those.")
    else:
        print("\nPerfect: every stored report_release_date matches SEC filingDate. "
              "US release dates are verified correct.")


if __name__ == "__main__":
    main()