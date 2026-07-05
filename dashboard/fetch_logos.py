"""
fetch_logos.py — one-time (cached) logo fetch for the watchlist / detail hero.

For each ticker in logo_domains.TICKER_DOMAINS, download the company's logo mark ONCE via a
domain-logo service and normalize it to a consistent transparent 128x128 PNG at
dashboard/logos/{TICKER}.png. Idempotent: an existing, valid file is never re-fetched.
Failures are EXPECTED for some names and handled gracefully — the app falls back to the
styled ticker badge for any ticker without a cached logo.

Providers (Clearbit's free logo API is deprecated/unreachable):
  1. DuckDuckGo icons  https://icons.duckduckgo.com/ip3/{domain}.ico   (primary)
  2. Google favicons   https://www.google.com/s2/favicons?domain={domain}&sz=128 (fallback)

USAGE (from repo root or dashboard/):
    python dashboard/fetch_logos.py            # fetch missing, cache to dashboard/logos/
    python dashboard/fetch_logos.py --force    # re-fetch all (ignore cache)
    python dashboard/fetch_logos.py --only AAPL,TSM   # re-fetch specific tickers
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import requests
from PIL import Image

try:
    from logo_domains import TICKER_DOMAINS
except ModuleNotFoundError:  # invoked from repo root
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from logo_domains import TICKER_DOMAINS

LOGO_DIR = Path(__file__).resolve().parent / "logos"
CANVAS = 128            # output square size
MIN_BYTES = 100         # below this = empty response; real validation is image-based below
TIMEOUT = 12
HEADERS = {"User-Agent": "Mozilla/5.0 (SignalDesk logo cache)"}


def providers(domain: str):
    yield f"https://icons.duckduckgo.com/ip3/{domain}.ico"
    yield f"https://www.google.com/s2/favicons?domain={domain}&sz=128"


def _normalize(raw: bytes) -> Image.Image | None:
    """Open bytes as an image, pick the largest frame (for multi-res .ico), and fit it
    centered onto a transparent CANVAS x CANVAS square without distortion."""
    try:
        img = Image.open(io.BytesIO(raw))
    except Exception:
        return None
    # multi-frame .ico -> choose the largest frame
    try:
        if getattr(img, "n_frames", 1) > 1:
            best, best_area = img, 0
            for i in range(img.n_frames):
                img.seek(i)
                area = img.size[0] * img.size[1]
                if area > best_area:
                    best, best_area = img.copy(), area
            img = best
    except Exception:
        pass
    img = img.convert("RGBA")
    if min(img.size) < 16:            # 16px favicons are too small for a clean badge
        return None
    if img.getextrema()[3][1] == 0:   # fully transparent = blank placeholder
        return None
    img.thumbnail((CANVAS, CANVAS), Image.LANCZOS)
    canvas = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    canvas.paste(img, ((CANVAS - img.width) // 2, (CANVAS - img.height) // 2), img)
    return canvas


def fetch_one(ticker: str, domain: str) -> tuple[bool, str]:
    for url in providers(domain):
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        except requests.RequestException:
            continue
        if r.status_code != 200 or len(r.content) < MIN_BYTES:
            continue
        img = _normalize(r.content)
        if img is None:
            continue
        img.save(LOGO_DIR / f"{ticker}.png")
        return True, url.split("/")[2]  # provider host
    return False, "—"


def main(argv: list[str]) -> None:
    LOGO_DIR.mkdir(exist_ok=True)
    force = "--force" in argv
    only = None
    for a in argv:
        if a.startswith("--only"):
            val = a.split("=", 1)[1] if "=" in a else argv[argv.index(a) + 1]
            only = {t.strip() for t in val.split(",")}

    items = {t: d for t, d in TICKER_DOMAINS.items() if (only is None or t in only)}
    got, cached, failed = [], [], []
    for ticker, domain in sorted(items.items()):
        dest = LOGO_DIR / f"{ticker}.png"
        if dest.exists() and not force:
            cached.append(ticker)
            continue
        ok, src = fetch_one(ticker, domain)
        (got if ok else failed).append(ticker)
        print(f"  {ticker:12} {domain:24} {'OK via ' + src if ok else 'FAIL -> badge fallback'}")

    print("\n" + "=" * 60)
    print(f"logos cached at {LOGO_DIR}")
    print(f"  fetched now : {len(got)}")
    print(f"  already cached: {len(cached)}")
    print(f"  FAILED (fallback to styled badge): {len(failed)}  {failed}")
    total_ok = len(got) + len(cached)
    print(f"  coverage: {total_ok}/{len(TICKER_DOMAINS)} tickers have a real logo")


if __name__ == "__main__":
    main(sys.argv[1:])
