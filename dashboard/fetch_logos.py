"""
fetch_logos.py — one-time (cached) DISPLAY-QUALITY logo fetch for the watchlist,
ranking table and company-detail hero.

SOURCE: TradingView's symbol-logo CDN (s3-symbol-logo.tradingview.com).
Chosen after evaluating the alternatives against OUR 97 tickers:

  * TradingView — 97/97 coverage, **vector SVG**, purpose-built symbol logos: a 56x56
    full-bleed square with the brand colour as background, designed to be clipped to a circle.
    Crisp at every render size we use (26px table, 40px watchlist, 58px hero). No API key.
    Keyed by TradingView's own `logoid` slug, resolved per ticker from their public
    symbol-search endpoint (see `resolve_logoid`). CHOSEN.
  * logo.dev — returns HTTP 401 without an API token, so coverage/quality for our tickers
    cannot be assessed without signing up for a key. Rejected: a credential + external
    dependency for what is a one-time static asset fetch.
  * Clearbit — logo.clearbit.com no longer resolves (service retired).
  * DuckDuckGo / Google favicons (the PREVIOUS source) — 16-64px browser-tab icons: blurry
    when scaled up, square, inconsistently padded. This is what we are replacing.

Two tickers get a PARENT-GROUP mark rather than the subsidiary's own, because that is what
TradingView itself serves: SK hynix (000660.KS) -> `sk-telecom` (SK Group) and MUFG (8306.T)
-> `mitsubishi-group`. Confirmed against TradingView's search API — not a resolution error on
our side. Pin something else in LOGOID_OVERRIDES if you disagree.

Writes dashboard/logos/{TICKER}.svg plus `_manifest.csv` (ticker, logoid, source, bytes).
Idempotent: an existing file is never re-fetched. A ticker with no logo simply has no file —
the app falls back to a round, sector-coloured initials badge of the same size.

READ-ONLY on the database (reads ticker + company_name only, to resolve logoids).

USAGE (from repo root or dashboard/):
    python dashboard/fetch_logos.py                  # fetch missing
    python dashboard/fetch_logos.py --force          # re-fetch all
    python dashboard/fetch_logos.py --only AAPL,TSM  # re-fetch specific tickers
    python dashboard/fetch_logos.py --report         # print coverage table, write nothing
"""
from __future__ import annotations

import argparse
import csv
import difflib
import re
import sqlite3
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "financials.db"
LOGO_DIR = Path(__file__).resolve().parent / "logos"
MANIFEST = LOGO_DIR / "_manifest.csv"

CDN = "https://s3-symbol-logo.tradingview.com/{logoid}--big.svg"
SEARCH = ("https://symbol-search.tradingview.com/symbol_search/v3/"
          "?text={q}&hl=1&lang=en&search_type=stocks&domain=production")
HEADERS = {"User-Agent": "Mozilla/5.0 (SignalDesk logo cache)",
           "Origin": "https://www.tradingview.com",
           "Referer": "https://www.tradingview.com/"}
TIMEOUT = 15

# Manual pins. Anything listed here skips symbol-search entirely.
LOGOID_OVERRIDES: dict[str, str] = {
    # empty — symbol-search resolves all 97 correctly today. Add a ticker to pin its slug.
}

_TAG = re.compile(r"<[^>]+>")
_SUFFIX = re.compile(r"\b(inc|corp|corporation|company|co|plc|ltd|limited|group|holdings?|"
                     r"sa|se|ag|nv|as|a s|class [abc]|the)\b")


def _norm(s: str) -> str:
    s = re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())
    return re.sub(r"\s+", " ", _SUFFIX.sub(" ", s)).strip()


def _search(q: str) -> list[dict]:
    try:
        r = requests.get(SEARCH.format(q=requests.utils.quote(q)), headers=HEADERS,
                         timeout=TIMEOUT)
        return r.json().get("symbols", []) if r.status_code == 200 else []
    except Exception:
        return []


def resolve_logoid(ticker: str, name: str) -> tuple[str | None, float]:
    """Best (logoid, score) for a ticker via TradingView symbol-search.

    Queries the raw ticker, its exchange-stripped base, a dot-variant (BRK-B -> BRK.B, which
    the plain base does NOT find), and the company name. Each hit is scored by fuzzy-matching
    OUR company_name against TradingView's description, plus a bonus for an exact symbol
    match. The name check is what stops a bare-ticker collision picking the wrong company.
    """
    if ticker in LOGOID_OVERRIDES:
        return LOGOID_OVERRIDES[ticker], 99.0

    base = ticker.split(".")[0]
    queries = [ticker, base]
    if "-" in base:
        queries.append(base.replace("-", "."))
    queries += [name, _norm(name)]

    seen: set[str] = set()
    best: tuple[str | None, float] = (None, 0.0)
    for q in queries:
        if not q or q in seen:
            continue
        seen.add(q)
        for hit in _search(q)[:12]:
            logoid = hit.get("logoid")
            if not logoid:
                continue
            desc = _TAG.sub("", hit.get("description") or "")
            sym = _TAG.sub("", hit.get("symbol") or "")
            score = difflib.SequenceMatcher(None, _norm(name), _norm(desc)).ratio()
            if sym.upper() == base.upper():
                score += 0.35
            if score > best[1]:
                best = (logoid, score)
        if best[1] >= 1.0:
            break
        time.sleep(0.05)
    return best


def fetch_svg(logoid: str) -> bytes | None:
    try:
        r = requests.get(CDN.format(logoid=logoid), headers=HEADERS, timeout=TIMEOUT)
    except Exception:
        return None
    if r.status_code != 200 or b"<svg" not in r.content[:200]:
        return None
    return r.content


def universe() -> list[tuple[str, str]]:
    with sqlite3.connect(DB_PATH) as con:      # READ-ONLY
        return con.execute("SELECT ticker, MAX(company_name) FROM financial_facts "
                           "GROUP BY ticker ORDER BY ticker").fetchall()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-fetch even if cached")
    ap.add_argument("--only", help="comma-separated tickers")
    ap.add_argument("--report", action="store_true", help="print coverage, write nothing")
    args = ap.parse_args()

    LOGO_DIR.mkdir(exist_ok=True)
    rows = universe()
    if args.only:
        want = {t.strip().upper() for t in args.only.split(",")}
        rows = [r for r in rows if r[0].upper() in want]

    manifest: list[tuple] = []
    real, fallback = 0, []
    for ticker, name in rows:
        dest = LOGO_DIR / f"{ticker}.svg"
        if dest.exists() and not args.force and not args.report:
            manifest.append((ticker, "(cached)", "tradingview", dest.stat().st_size))
            real += 1
            print(f"  {ticker:11s} cached")
            continue

        logoid, score = resolve_logoid(ticker, name)
        svg = fetch_svg(logoid) if logoid else None
        if svg:
            if not args.report:
                dest.write_bytes(svg)
            real += 1
            src = "override" if ticker in LOGOID_OVERRIDES else "tradingview"
            manifest.append((ticker, logoid, src, len(svg)))
            print(f"  {ticker:11s} {logoid:28s} {src:12s} {len(svg):6d}B  score {score:.2f}")
        else:
            fallback.append(ticker)
            manifest.append((ticker, "", "fallback", 0))
            print(f"  {ticker:11s} {'-':28s} FALLBACK (styled round badge)")

    if not args.report:
        with MANIFEST.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["ticker", "logoid", "source", "bytes"])
            w.writerows(manifest)

    print(f"\n=== {real}/{len(rows)} real logos · {len(fallback)} fallback ===")
    if fallback:
        print("fallback tickers:", ", ".join(fallback))
    if not args.report:
        print(f"manifest -> {MANIFEST}")


if __name__ == "__main__":
    main()
