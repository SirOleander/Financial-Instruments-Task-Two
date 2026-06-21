"""
Diagnose why IBM inline (iXBRL) items are missing for the 10-K.

Run from your project root (same folder you run D_pipeline.py from), AFTER a
normal run so the raw filing HTML has been saved to config.SEC_FILINGS_DIR:

    python diagnose_ibm_inline.py

It does NOT hit the network. It only reads the HTML files your pipeline
already saved, and re-parses them with your own C_client functions so the
result is faithful to the real pipeline.
"""

import re

from bs4 import BeautifulSoup

import A_config as config
import C_client as client


TICKER = "IBM"
CONCEPTS = (
    "OtherExpenseAndIncome",
    "SellingGeneralAndAdministrativeExpense",
    "IntellectualPropertyAndCustomDevelopmentIncome",
)

# Crude ground-truth counter: how many inline numeric/text fact tags exist in
# the raw bytes, independent of any HTML parser.
RAW_FACT_RE = re.compile(r"<ix:non(fraction|numeric)\b", re.IGNORECASE)


def count_with_parser(html: str, parser: str) -> int:
    """Count ix:nonFraction/ix:nonNumeric tags BeautifulSoup actually sees."""
    soup = BeautifulSoup(html, parser)
    tags = soup.find_all(
        lambda tag: tag.name
        and ("nonfraction" in tag.name.lower() or "nonnumeric" in tag.name.lower())
        and tag.get("name") is not None
    )
    return len(tags)


def main() -> None:
    files = sorted(config.SEC_FILINGS_DIR.glob(f"{TICKER}_*"))
    if not files:
        print(f"No saved filings found in {config.SEC_FILINGS_DIR} for {TICKER}.")
        print("Run the pipeline first so fetch_filing_document() saves the HTML.")
        return

    for path in files:
        html = path.read_text(encoding="utf-8", errors="replace")
        size_mb = len(html) / 1_000_000

        raw_hits = len(RAW_FACT_RE.findall(html))
        html_parser_count = count_with_parser(html, "html.parser")
        try:
            lxml_count = count_with_parser(html, "lxml")
        except Exception as exc:  # lxml not installed
            lxml_count = f"unavailable ({exc})"

        print("=" * 100)
        print(f"FILE: {path.name}")
        print(f"  size: {size_mb:.2f} MB")
        print(f"  raw <ix:nonFraction/nonNumeric> in bytes : {raw_hits}")
        print(f"  facts seen by html.parser (your pipeline): {html_parser_count}")
        print(f"  facts seen by lxml                       : {lxml_count}")

        if isinstance(lxml_count, int) and lxml_count > html_parser_count * 1.05:
            print("  >>> html.parser is seeing far fewer facts than lxml: "
                  "strong sign of truncation. Switch the parser to 'lxml'.")

        # Re-parse with the pipeline's own function and look for the 3 concepts.
        facts = client._parse_ixbrl_facts(html)
        if facts.empty:
            print("  >>> _parse_ixbrl_facts() returned ZERO facts for this file.")
            print("      (If raw_hits above is large, the parser dropped them.)")
            continue

        for concept in CONCEPTS:
            matches = facts[facts["concept"] == concept]
            print(f"\n  concept '{concept}': {len(matches)} parsed instance(s)")
            for _, row in matches.iterrows():
                dims = row.get("dimensions")
                non_dim = isinstance(dims, dict) and len(dims) == 0
                print(
                    f"    value={row.get('value')!s:>16}  "
                    f"start={str(row.get('start'))[:10]}  "
                    f"end={str(row.get('end'))[:10]}  "
                    f"non_dimensional={non_dim}  dims={dims}"
                )

    print("=" * 100)
    print("How to read this:")
    print("  * raw_hits big but _parse_ixbrl_facts == 0  -> fetch saved a non-XBRL")
    print("    document, OR the parser failed. Compare html.parser vs lxml counts.")
    print("  * The 10-K shows 0 parsed instances of the concepts, but the 10-Q")
    print("    shows them with non_dimensional=True -> the 10-K inline pass is the")
    print("    problem, not the concept mapping.")
    print("  * A concept present only with non_dimensional=False on the 10-K means")
    print("    the non-dimensional filter is dropping it (different fix).")


if __name__ == "__main__":
    main()
