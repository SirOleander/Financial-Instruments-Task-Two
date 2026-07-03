"""
yf_bank_probe.py — read-only deep dump of the 5 surviving non-US banks.

Unlike yf_probe.py, this does NOT filter against expected labels. For each bank
it prints the COMPLETE raw row index of every statement (annual + quarterly,
income / balance / cashflow), exactly as the yfinance API returns it, plus a
targeted hunt for the four contested lines (noninterest expense, loans,
deposits, allowance) using a wide keyword search.

Goal: settle definitively, per bank, whether a summed Non Interest Expense line
exists in the API, and whether loans / deposits / allowance appear under ANY
label. No DB writes. Requires: pip install yfinance pandas
Run:  python yf_bank_probe.py
"""

from __future__ import annotations

import time

import pandas as pd

try:
    import yfinance as yf
except ImportError:
    raise SystemExit("Install yfinance first:  pip install yfinance pandas")


BANKS = ["HSBA.L", "RY.TO", "8306.T", "TD.TO", "SAN.MC"]

# keyword groups for the targeted hunt (substring match, case-insensitive)
HUNT = {
    "noninterest_expense": ["non interest expense", "noninterest expense"],
    "total_loans": ["loan", "advances", "lending"],
    "total_deposits": ["deposit"],
    "allowance_for_credit_losses": ["allowance", "credit loss", "impairment",
                                    "provision for"],
    # bonus: things we may want for NIM / capital_retention
    "interest_income/expense": ["interest income", "interest expense"],
    "dividends": ["dividend"],
    "retained_earnings": ["retained earnings"],
}

STATEMENTS = [
    ("income_stmt", "annual income"),
    ("quarterly_income_stmt", "quarterly income"),
    ("balance_sheet", "annual balance"),
    ("quarterly_balance_sheet", "quarterly balance"),
    ("cashflow", "annual cashflow"),
    ("quarterly_cashflow", "quarterly cashflow"),
]


def get_df(t: yf.Ticker, attr: str) -> pd.DataFrame:
    try:
        df = getattr(t, attr)
        return df if df is not None else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def all_labels(t: yf.Ticker) -> dict[str, list[str]]:
    """Per statement, the raw row index as returned by the API."""
    out = {}
    for attr, nice in STATEMENTS:
        df = get_df(t, attr)
        out[nice] = list(df.index) if not df.empty else []
    return out


def hunt(labels_union: list[str]) -> dict[str, list[str]]:
    found = {}
    low = [(l, str(l).lower()) for l in labels_union]
    for key, kws in HUNT.items():
        hits = sorted({l for l, ll in low if any(kw in ll for kw in kws)})
        found[key] = hits
    return found


def main() -> None:
    print("yfinance BANK deep-probe — read-only, full raw statement indexes\n"
          + "=" * 72)
    for ticker in BANKS:
        print(f"\n{'#' * 72}\n### {ticker}\n{'#' * 72}")
        t = yf.Ticker(ticker)

        labels = all_labels(t)
        union = sorted({l for v in labels.values() for l in v})

        # 1) targeted hunt across the union of all labels
        print("\n-- TARGETED HUNT (does each contested line exist under ANY label?) --")
        for key, hits in hunt(union).items():
            status = hits if hits else "NONE FOUND"
            print(f"  {key:32}: {status}")

        # 2) full raw index per statement
        for nice, idx in labels.items():
            print(f"\n-- {ticker} :: {nice}  ({len(idx)} rows) --")
            if not idx:
                print("     (empty / not returned)")
                continue
            for lab in idx:
                print(f"     {lab}")

        time.sleep(1.5)  # polite to Yahoo

    print("\n" + "=" * 72)
    print("Read the TARGETED HUNT blocks first. If 'noninterest_expense' shows a "
          "summed line for all 5 banks -> efficiency_ratio is recoverable. If "
          "loans/deposits/allowance are NONE FOUND across all 5 -> they are "
          "genuinely unavailable via the API and must be hand-sourced or dropped.")


if __name__ == "__main__":
    main()