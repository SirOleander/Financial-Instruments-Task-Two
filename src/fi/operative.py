"""operative.py — the LLM competitive-advantage ("operative") score.

Was `G_operative`. Kept as its own module: it is the ONLY stage that calls a paid external
API. Per (ticker, report) it feeds that filing's MD&A / Business / Risk text to a LiteLLM
endpoint, parses a 1-5 judgement, and rescales (raw-1)/4 -> strategic_score in [0,1], into
`operative_scores`. Look-ahead locked (only that filing's text), reproducible (temp 0, model
+ prompt_version recorded), cached by accession so a re-run costs nothing for scored filings.

Key read ONLY from env var LITELLM_API_KEY (never hardcoded/printed/written). With no key
and new filings, it warns and leaves them unscored (operative_missing=1 downstream), exactly
as GEV is handled — the pipeline still completes.
"""
from __future__ import annotations

import json
import os
import re
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import closing

import requests

from fi import db, sec

BASE_URL = "https://litellm.s.studiumdigitale.uni-frankfurt.de"
MODEL = "qwen3.5-122b-a10b"
TEMPERATURE = 0
PROMPT_VERSION = "op-v2-compadv"
ENV_KEY_NAME = "LITELLM_API_KEY"
BUDGET_CHARS = 50_000          # overall ceiling; MD&A-dominant, see build_payload
# MD&A drives the score; Risk Factors are uniformly cautionary boilerplate and are
# capped so they don't drag risk-heavy filers down; Business gets a small slice.
SECTION_CAPS = {"mdna": BUDGET_CHARS, "risk": 10_000, "business": 4_000}
N_VOTES = 1                    # calls per filing (cache freezes the score once written;
                               # single call = 1x cost, ±1 jitter acceptable on one feature)
REQUEST_TIMEOUT = 240          # large payloads are slow; generous read timeout
MAX_ATTEMPTS = 4               # transient-error + unparseable retries per single vote
SLEEP_BETWEEN = 0.3            # polite gap between LLM calls
MDNA_MIN_CHARS = 3_000         # below this, MD&A is treated as "not in primary doc"
                               # (incorporated by reference) -> try Exhibit 13; if still
                               # below this after Ex-13, the report is scored MISSING.

_RUBRIC = (
    "You are an equity analyst assessing a company's DURABLE COMPETITIVE ADVANTAGE "
    "(economic moat) using ONLY the text of a single SEC filing.\n\n"
    "Assess the competitive advantage this filing provides evidence for, across six "
    "dimensions:\n"
    "1. Pricing power — ability to raise prices without losing demand.\n"
    "2. Innovation / IP — patents, R&D strength, technological differentiation.\n"
    "3. Customer stickiness — switching costs, retention, recurring relationships.\n"
    "4. Margin resilience — stability of margins despite cost pressure.\n"
    "5. Market leadership — market-share gains, strong position in key segments.\n"
    "6. Brand strength — premium positioning, loyalty, reputation.\n\n"
    "Weight the six dimensions by HOW MUCH SUBSTANTIVE EVIDENCE the filing provides for "
    "each: lean on the dimensions the filing actually evidences; if the filing is silent "
    "on a dimension, treat it as neutral/absent — do NOT fill it in. Then synthesize ONE "
    "holistic integer score:\n"
    "5 = strong, well-evidenced competitive advantages across multiple dimensions.\n"
    "4 = above-average, decent evidence.\n"
    "3 = mixed / moderate / limited evidence.\n"
    "2 = below-average / weak evidence.\n"
    "1 = weak, or evidence of an eroding competitive position.\n\n"
    "CRITICAL EVIDENCE-ONLY LOOK-AHEAD RULE:\n"
    "- Judge each dimension ONLY from evidence explicitly presented in THIS filing's text.\n"
    "- Treat the filing as coming from an anonymous, unnamed company; ignore the issuer's "
    "identity.\n"
    "- Do NOT use any prior or outside knowledge of this company's real-world brand, "
    "products, market position, reputation, customers, or of anything that happened after "
    "this filing was published. You may recognize the company — you MUST ignore that.\n"
    "- If the filing provides no evidence for a dimension, treat it as neutral/absent; do "
    "NOT supply it from general knowledge.\n"
    "A famous company whose filing provides little competitive-advantage evidence must "
    "score LOWER than an obscure company whose filing strongly evidences pricing power and "
    "customer stickiness. The score reflects what the FILING demonstrates, not what you "
    "know about the company.\n\n"
)

SYSTEM_PROMPT = _RUBRIC + (
    "Respond with ONLY the single integer (1, 2, 3, 4, or 5). No words, no explanation."
)

# Preview-only variant: same rubric + lock, but also asks for a short evidence note so a
# human can verify the score rests on filing text, not the model's memory of the company.
# NOT used in the production run (which stores only the score).
PREVIEW_EXPLAIN_PROMPT = _RUBRIC + (
    "Respond with the single integer (1-5) on the FIRST line. Then on the next line, in "
    "one or two sentences, name the SPECIFIC evidence in the filing that drove your score. "
    "Do NOT name or guess the company."
)

# ---- section markers (case-insensitive, applied to plain text) ----------------
_MK = {
    "k_business_start": r"item\s*1(?!\s*[0-9a-c])",
    "k_business_end":   r"item\s*1\s*a\b",
    "k_risk_start":     r"item\s*1\s*a\b",
    "k_risk_end":       r"item\s*(1\s*b|2)\b",
    "k_mdna_start":     r"item\s*7(?!\s*[0-9a])",
    "k_mdna_end":       r"item\s*(7\s*a|8)\b",
    "q_mdna_start":     r"item\s*2\b",
    "q_mdna_end":       r"item\s*(3|4)\b",
    # 20-F (annual, foreign private issuers): MD&A-equiv = Item 5 (Operating and
    # Financial Review and Prospects); Business = Item 4; Risk Factors = Item 3.D.
    "f_item5_start":    r"item\s*5\b",
    "f_item5_end":      r"item\s*6\b",
    "f_item4_start":    r"item\s*4\b(?!\s*a)",
    "f_item4_end":      r"item\s*(4\s*a|5)\b",
    "f_risk_start":     r"(item\s*3\s*\.?\s*d|risk\s+factors)",
    "f_risk_end":       r"item\s*4\b",
}

# Exhibit 13 (annual report to shareholders) carries MD&A under a TITLE, not an Item
# number, so it is located by heading text rather than the _MK item markers.
_EX13_MDNA_START = r"management.?s\s+discussion\s+and\s+analysis"
_EX13_MDNA_END = (r"(quantitative\s+and\s+qualitative\s+disclosures|"
                  r"report\s+of\s+(the\s+)?independent\s+registered|"
                  r"consolidated\s+(balance\s+sheet|statements?\s+of|financial\s+statements)|"
                  r"critical\s+accounting\s+estimates\s+report)")


# --------------------------------------------------------------------------- #
# text extraction
# --------------------------------------------------------------------------- #
def html_to_text(html: str) -> str:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text("\n")
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text


def _positions(pattern: str, text: str) -> list[int]:
    return [m.start() for m in re.finditer(pattern, text, flags=re.IGNORECASE)]


def _best_slice(text: str, start_pat: str, end_pat: str, allow_eof: bool = False) -> str:
    """Return the LONGEST slice from a start-marker to the next end-marker. The
    longest such block is the real body section (TOC entries produce tiny slices)."""
    starts = _positions(start_pat, text)
    ends = _positions(end_pat, text)
    best = ""
    for s in starts:
        later = [e for e in ends if e > s]
        e = min(later) if later else (len(text) if allow_eof else None)
        if e is None:
            continue
        if e - s > len(best):
            best = text[s:e]
    return best.strip()


def extract_sections(html: str, form: str) -> dict[str, str]:
    text = html_to_text(html)
    if form == "20-F":
        # mdna slot = Item 5 (MD&A-equivalent), so build_payload prioritizes it whole.
        return {
            "mdna": _best_slice(text, _MK["f_item5_start"], _MK["f_item5_end"]),
            "risk": _best_slice(text, _MK["f_risk_start"], _MK["f_risk_end"]),
            "business": _best_slice(text, _MK["f_item4_start"], _MK["f_item4_end"]),
        }
    if form == "10-K":
        return {
            "mdna": _best_slice(text, _MK["k_mdna_start"], _MK["k_mdna_end"]),
            "risk": _best_slice(text, _MK["k_risk_start"], _MK["k_risk_end"]),
            "business": _best_slice(text, _MK["k_business_start"], _MK["k_business_end"]),
        }
    # 10-Q: MD&A only (Business/Risk usually absent/minimal)
    return {
        "mdna": _best_slice(text, _MK["q_mdna_start"], _MK["q_mdna_end"], allow_eof=True),
        "risk": "",
        "business": "",
    }


def build_payload(sections: dict[str, str]) -> tuple[str, bool]:
    """Assemble prompt text under BUDGET_CHARS. Priority MD&A > Risk > Business:
    fill in that order; truncate/drop LOWER-priority sections first. Returns
    (text, truncated). truncated=True if any section was cut or dropped."""
    order = [("MD&A", "mdna"), ("RISK FACTORS", "risk"), ("BUSINESS", "business")]
    parts: list[str] = []
    used = 0
    truncated = False
    for title, key in order:
        sec = sections.get(key) or ""
        if not sec:
            continue
        header = f"=== {title} ===\n"
        # each section limited by BOTH its own cap and the overall remaining budget
        remaining = min(SECTION_CAPS[key], BUDGET_CHARS - used) - len(header)
        if remaining <= 0:
            truncated = True
            continue
        if len(sec) > remaining:
            sec = sec[:remaining]
            truncated = True
        block = header + sec
        parts.append(block)
        used += len(block)
    return "\n\n".join(parts), truncated


def recover_mdna_ex13(session, rep: dict) -> tuple[str, str | None]:
    """When the primary doc's MD&A is near-empty (incorporated by reference), look for
    an Exhibit 13 document in the accession and extract MD&A from it by heading. Returns
    (mdna_text, ex13_filename) or ("", None)."""
    try:
        docs = sec.list_filing_inline_documents(
            session, rep["cik"], rep["accession_number"])
    except Exception:
        return "", None

    def is_ex13(name: str) -> bool:
        n = re.sub(r"[-_ ]", "", name.lower())
        return "ex13" in n or "exhibit13" in n

    for name in [d for d in docs if is_ex13(d)]:
        try:
            html = sec.fetch_filing_document(
                session, rep["cik"], rep["accession_number"], name)
        except Exception:
            continue
        mdna = _best_slice(html_to_text(html), _EX13_MDNA_START, _EX13_MDNA_END,
                           allow_eof=True)
        if len(mdna) >= MDNA_MIN_CHARS:
            return mdna, name
    return "", None


def prepare_payload(session, rep: dict) -> dict:
    """Fetch + extract + (if needed) Exhibit-13 MD&A recovery + budget assembly.
    MD&A is REQUIRED: if it cannot be obtained from the primary doc or Ex-13, the report
    is not scorable (status hint 'missing'). Returns a dict with everything the caller
    (score_report / dry_run) needs; performs no DB writes."""
    out = {"ok": False, "error": None, "sections": {"mdna": "", "risk": "", "business": ""},
           "primary_mdna_len": 0, "mdna_source": "none", "payload": "", "truncated": False}
    try:
        html = sec.fetch_filing_document(
            session, rep["cik"], rep["accession_number"], rep["primary_document"])
    except Exception as exc:
        out["error"] = f"fetch: {exc}"
        return out

    sections = extract_sections(html, rep["form"])
    out["primary_mdna_len"] = len(sections["mdna"])
    if len(sections["mdna"]) >= MDNA_MIN_CHARS:
        out["mdna_source"] = "primary"
    elif rep["form"] == "20-F":
        # 20-F: Item 5 is the MD&A-equivalent. Integrated-report filers (ASML/Shell/
        # Santander) carry Item 5 only in a cross-reference table; a generic title
        # fallback grabs the WRONG section, so we do NOT guess — mark missing per the
        # Stage-2 rule (never score on Risk/Business alone).
        out["mdna_source"] = "none"
    else:
        # Fallback 1: MD&A embedded in the SAME primary doc under a title heading
        # (banks/financials use annual-report headings, not "Item 7" markers).
        title_mdna = _best_slice(html_to_text(html), _EX13_MDNA_START, _EX13_MDNA_END,
                                 allow_eof=True)
        if len(title_mdna) >= MDNA_MIN_CHARS:
            sections["mdna"] = title_mdna
            out["mdna_source"] = "primary_title"
        else:
            # Fallback 2: separate Exhibit 13 document.
            rec, exname = recover_mdna_ex13(session, rep)
            if len(rec) >= MDNA_MIN_CHARS:
                sections["mdna"] = rec
                out["mdna_source"] = "ex13"
                out["ex13_name"] = exname
            else:
                out["mdna_source"] = "none"      # MD&A unavailable -> not scorable

    out["sections"] = sections
    payload, truncated = build_payload(sections)
    out["payload"], out["truncated"] = payload, truncated
    out["ok"] = out["mdna_source"] != "none"
    return out


def build_messages(payload_text: str, form: str, as_of: str,
                   system: str = SYSTEM_PROMPT) -> list[dict]:
    user = (f"Filing type: {form}. As-of (publication) date: {as_of}.\n"
            f"Assess the competitive advantage evidenced in the following filing excerpts.\n\n"
            f"{payload_text}")
    return [{"role": "system", "content": system},
            {"role": "user", "content": user}]


# --------------------------------------------------------------------------- #
# LLM call + parse
# --------------------------------------------------------------------------- #
def get_api_key() -> str:
    key = os.environ.get(ENV_KEY_NAME)
    if not key:
        raise SystemExit(
            f"Environment variable {ENV_KEY_NAME} is not set. Export your LiteLLM API key "
            f"into it (do NOT hardcode it in the source), then re-run.")
    return key


def call_llm(messages: list[dict], api_key: str) -> str:
    resp = requests.post(
        f"{BASE_URL}/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": MODEL, "temperature": TEMPERATURE, "messages": messages},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def single_vote(messages: list[dict], api_key: str) -> tuple[int | None, bool, str | None]:
    """One vote = one call with transient-error + unparseable retries. Returns
    (score|None, got_any_response, error). Permanent 4xx (auth/bad request) returns
    immediately with got_any_response=False."""
    raw = None
    last_err = None
    got = False
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            raw = call_llm(messages, api_key)
            got = True
        except requests.HTTPError as exc:
            code = exc.response.status_code if exc.response is not None else None
            if code is not None and 400 <= code < 500 and code != 429:
                return None, False, f"api HTTP {code}"     # permanent
            last_err = f"api HTTP {code}"
            time.sleep(min(5 * 2 ** (attempt - 1), 30))
            continue
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_err = f"transient {type(exc).__name__}"
            time.sleep(min(5 * 2 ** (attempt - 1), 30))
            continue
        except Exception as exc:
            return None, False, f"api: {exc}"
        score = parse_score(raw)
        if score is not None:
            return score, True, None
        last_err = f"unparseable: {raw!r}"
    return None, got, last_err


def parse_score(raw: str):
    """Extract an integer 1-5 from the model response, tolerating <think> blocks and
    stray text. Returns int or None."""
    if raw is None:
        return None
    cleaned = re.sub(r"(?is)<think>.*?</think>", "", raw).strip()
    if re.fullmatch(r"[1-5]", cleaned):
        return int(cleaned)
    # last non-empty line that is exactly a digit
    for line in reversed([ln.strip() for ln in cleaned.splitlines() if ln.strip()]):
        if re.fullmatch(r"[1-5]", line):
            return int(line)
    # fallback: first standalone 1-5
    m = re.search(r"\b([1-5])\b", cleaned)
    return int(m.group(1)) if m else None


# --------------------------------------------------------------------------- #
# per-report scoring
# --------------------------------------------------------------------------- #
def load_us_reports() -> list[dict]:
    with closing(db.get_connection()) as con:
        rows = con.execute(
            """
            SELECT ticker, report_release_date,
                   MAX(fiscal_period_end_date) AS fiscal_period_end_date,
                   MAX(form) AS form, accession_number,
                   MAX(primary_document) AS primary_document, MAX(cik) AS cik
            FROM financial_facts
            WHERE source = 'edgar'
            GROUP BY ticker, report_release_date, accession_number
            ORDER BY ticker, report_release_date
            """
        ).fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------- #
# international 20-F reports (Stage 2): located on EDGAR by the issuer's CIK,
# resolved from its US ADR ticker via SEC company_tickers.json. The DB (local)
# ticker is preserved so operative rows join to the rest of the pipeline.
# --------------------------------------------------------------------------- #
ADR_MAP = {                       # DB/local ticker -> US ADR ticker (for CIK lookup)
    "TSM": "TSM", "ASML.AS": "ASML", "SAP.DE": "SAP", "7203.T": "TM",
    "6758.T": "SONY", "AZN.L": "AZN", "NOVN.SW": "NVS", "NOVO-B.CO": "NVO",
    "SHEL.L": "SHEL", "8306.T": "MUFG", "SAN.MC": "SAN",
}
SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
INTL_SOURCE = "edgar-20f"         # distinguishes these rows from US source='edgar'


def resolve_ciks(session) -> dict[str, str]:
    """DB ticker -> zero-padded CIK, via ADR ticker in SEC company_tickers.json."""
    j = sec.request_json(session, SEC_COMPANY_TICKERS_URL)
    by_ticker = {v["ticker"].upper(): str(v["cik_str"]).zfill(10) for v in j.values()}
    return {db: by_ticker[adr.upper()] for db, adr in ADR_MAP.items()
            if adr.upper() in by_ticker}


def load_intl_20f_reports(session=None, since_year: int | None = None) -> list[dict]:
    """One record per 20-F filing for each of the 11 international names. since_year
    (if set) keeps only filings whose report_release_date year >= since_year."""
    session = session or sec.make_session()
    ciks = resolve_ciks(session)
    reports: list[dict] = []
    for db_ticker, cik in ciks.items():
        subs = sec.fetch_submissions(session, db_ticker, cik)
        rec = subs["filings"]["recent"]
        for i in range(len(rec["form"])):
            if rec["form"][i] != "20-F":
                continue
            release = rec["filingDate"][i]
            if since_year and int(release[:4]) < since_year:
                continue
            reports.append({
                "ticker": db_ticker, "cik": cik, "form": "20-F",
                "accession_number": rec["accessionNumber"][i],
                "primary_document": rec["primaryDocument"][i],
                "report_release_date": release,
                "fiscal_period_end_date": rec["reportDate"][i] or None,
                "source": INTL_SOURCE,
            })
    reports.sort(key=lambda r: (r["ticker"], r["report_release_date"]))
    return reports


def score_report(rep: dict, session, api_key: str) -> dict:
    """Fetch, extract, call, parse for one report. Returns a result dict (no DB write)."""
    base = {
        "ticker": rep["ticker"], "report_release_date": rep["report_release_date"],
        "fiscal_period_end_date": rep["fiscal_period_end_date"],
        "source": rep.get("source", "edgar"),
        "form": rep["form"], "accession_number": rep["accession_number"],
        "model": MODEL, "prompt_version": PROMPT_VERSION,
        "operative_score_raw": None, "operative_score": None, "raw_scores": None,
        "truncated": 0, "mdna_source": "none", "status": "missing",
    }
    prep = prepare_payload(session, rep)
    base["truncated"] = 1 if prep["truncated"] else 0
    base["mdna_source"] = prep["mdna_source"]
    if prep["error"]:
        base["status"] = "error"
        base["_error"] = prep["error"]
        return base
    if not prep["ok"]:                        # MD&A unavailable (primary+Ex13) -> missing
        base["status"] = "missing"
        base["_error"] = "MD&A not available (primary near-empty, Ex-13 not recovered)"
        return base

    payload = prep["payload"]
    messages = build_messages(payload, rep["form"], rep["report_release_date"])

    votes: list[int | None] = []       # per-call outcome (score or None), for audit
    any_response = False
    last_err = None
    for _ in range(N_VOTES):
        score, got, err = single_vote(messages, api_key)
        any_response = any_response or got
        votes.append(score)
        if err:
            last_err = err
        time.sleep(SLEEP_BETWEEN)

    base["raw_scores"] = json.dumps(votes)         # e.g. "[2, 3, 2]" or "[2, null, 3]"
    valid = [s for s in votes if s is not None]
    if valid:
        med = statistics.median(valid)             # median of 3 ints -> integer
        base["operative_score_raw"] = med
        base["operative_score"] = (med - 1) / 4
        base["status"] = "scored"
        base["_raw_response"] = votes
        return base

    # no valid votes: got responses but unparseable -> missing; all API errors -> error
    base["status"] = "missing" if any_response else "error"
    base["_error"] = last_err
    return base


# --------------------------------------------------------------------------- #
# table
# --------------------------------------------------------------------------- #
OP_COLUMNS = ("ticker", "report_release_date", "fiscal_period_end_date", "source", "form",
              "accession_number", "operative_score_raw", "operative_score", "raw_scores",
              "model", "prompt_version", "truncated", "mdna_source", "status")


def create_table() -> None:
    with closing(db.get_connection()) as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS operative_scores (
                ticker                  TEXT NOT NULL,
                report_release_date     TEXT NOT NULL,
                fiscal_period_end_date  TEXT,
                source                  TEXT,
                form                    TEXT,
                accession_number        TEXT NOT NULL,
                operative_score_raw     REAL,
                operative_score         REAL,
                raw_scores              TEXT,
                model                   TEXT,
                prompt_version          TEXT,
                truncated               INTEGER,
                mdna_source             TEXT,
                status                  TEXT,
                created_at              TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (ticker, report_release_date, accession_number)
            )
            """
        )
        con.commit()


def already_scored() -> set[str]:
    """Accession numbers with a real score already stored (cache)."""
    with closing(db.get_connection()) as con:
        try:
            rows = con.execute(
                "SELECT accession_number FROM operative_scores WHERE status = 'scored'"
            ).fetchall()
        except Exception:
            return set()
    return {r["accession_number"] for r in rows}


def upsert(results: list[dict]) -> None:
    if not results:
        return
    placeholders = ", ".join("?" for _ in OP_COLUMNS)
    with closing(db.get_connection()) as con:
        con.executemany(
            f"INSERT OR REPLACE INTO operative_scores ({', '.join(OP_COLUMNS)}) "
            f"VALUES ({placeholders})",
            [tuple(r[c] for c in OP_COLUMNS) for r in results],
        )
        con.commit()


def _counts(con) -> dict:
    """Row counts for the protected tables that EXIST.

    On a FIRST BUILD `target_63d` is created by a LATER stage, so `SELECT COUNT(*)` raised
    `sqlite3.OperationalError: no such table`. A table that does not exist cannot have been
    corrupted, so it is skipped. On a populated database every table exists and the guard is
    exactly as strict as before.
    """
    have = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("financial_facts", "daily_prices", "target_63d", "kpi_values", "scores")
            if t in have}


# --------------------------------------------------------------------------- #
# 1a dry-run
# --------------------------------------------------------------------------- #
def _pick_samples(reports: list[dict]) -> list[dict]:
    def latest(ticker, form):
        cs = [r for r in reports if r["ticker"] == ticker and r["form"] == form]
        return max(cs, key=lambda r: r["report_release_date"]) if cs else None
    picks = [latest("AAPL", "10-K"), latest("JPM", "10-K"), latest("AAPL", "10-Q"),
             latest("BA", "10-K"), latest("PLTR", "10-K")]
    return [p for p in picks if p]


def dry_run() -> None:
    reports = load_us_reports()
    samples = _pick_samples(reports)
    session = sec.make_session()
    key = os.environ.get(ENV_KEY_NAME)

    print("=" * 92)
    print(f"STAGE 1a DRY-RUN — {len(samples)} US filings. NO writes. "
          f"model={MODEL} temp={TEMPERATURE} budget={BUDGET_CHARS} chars")
    print(f"API key env {ENV_KEY_NAME}: {'SET' if key else 'NOT SET (live calls skipped)'}")
    print("=" * 92)
    print("\n--- SYSTEM PROMPT (identical for every call) ---")
    print(SYSTEM_PROMPT)

    # endpoint reachability probe (no key needed; 401 still proves it responds)
    try:
        r = requests.post(f"{BASE_URL}/v1/chat/completions",
                          headers={"Content-Type": "application/json"},
                          json={"model": MODEL, "messages": [{"role": "user", "content": "ping"}]},
                          timeout=30)
        print(f"\nendpoint probe (no key): HTTP {r.status_code} — endpoint responded")
    except Exception as exc:
        print(f"\nendpoint probe FAILED: {exc}")

    for rep in samples:
        print("\n" + "#" * 92)
        print(f"### {rep['ticker']} {rep['form']} release={rep['report_release_date']} "
              f"acc={rep['accession_number']}")
        prep = prepare_payload(session, rep)
        if prep["error"]:
            print(f"  FETCH FAILED: {prep['error']}")
            continue
        sections = prep["sections"]
        for k in ("mdna", "risk", "business"):
            sec = sections[k]
            head = sec[:200].replace("\n", " ")
            print(f"  [{k:8}] len={len(sec):>7}  first200: {head!r}")
        print(f"  MD&A source: {prep['mdna_source']} "
              f"(primary MD&A len was {prep['primary_mdna_len']}"
              f"{', Ex-13=' + prep['ex13_name'] if prep.get('ex13_name') else ''})")
        payload, truncated = prep["payload"], prep["truncated"]
        print(f"  payload chars={len(payload)}  truncated={truncated}  scorable={prep['ok']}")
        print(f"  USER excerpt (first 400 chars): {payload[:400]!r}")
        if not prep["ok"]:
            print("  -> NOT SCORABLE (MD&A unavailable) — would be marked missing")
        elif key:
            res = score_report(rep, session, key)
            print(f"  VOTES (3 raw scores): {res.get('raw_scores')}")
            print(f"  MEDIAN 1-5 = {res['operative_score_raw']}  "
                  f"rescaled [0,1] = {res['operative_score']}  status={res['status']}"
                  + (f"  _error={res.get('_error')}" if res.get('_error') else ""))
            # diagnostic-only: ask once for the evidence behind the score (NOT stored)
            try:
                ex = call_llm(build_messages(payload, rep["form"],
                                             rep["report_release_date"],
                                             system=PREVIEW_EXPLAIN_PROMPT), key)
                print(f"  EVIDENCE NOTE (diagnostic, not stored):\n     "
                      + ex.strip().replace("\n", "\n     "))
            except Exception as exc:
                print(f"  EVIDENCE NOTE unavailable: {exc}")
        else:
            print("  (LIVE CALL SKIPPED — set the env var to see model responses)")

    print("\n" + "=" * 92)
    print("STAGE 1a complete. Nothing written. Review, set env var if needed, then --write.")


# --------------------------------------------------------------------------- #
# 1b full run
# --------------------------------------------------------------------------- #
# thread-local SEC session (requests.Session isn't guaranteed thread-safe to share)
_tls = threading.local()


def _thread_session():
    s = getattr(_tls, "session", None)
    if s is None:
        s = sec.make_session()
        _tls.session = s
    return s


def run_full(concurrency: int = 1) -> None:
    key = get_api_key()
    with closing(db.get_connection()) as con:
        counts_before = _counts(con)          # snapshot the 5 other tables before writing
    create_table()
    reports = load_us_reports()
    cached = already_scored()
    todo = [r for r in reports if r["accession_number"] not in cached]

    print(f"US reports: {len(reports)} | already scored (cached): {len(cached)} | "
          f"to score now: {len(todo)} | concurrency={concurrency}", flush=True)

    def worker(rep: dict) -> dict:
        return score_report(rep, _thread_session(), key)

    batch: list[dict] = []
    scored = missing = error = 0
    done = 0
    # Workers do only network (fetch + LLM); ALL DB upserts happen here on the main
    # thread to avoid concurrent SQLite writes.
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futures = {ex.submit(worker, rep): rep for rep in todo}
        for fut in as_completed(futures):
            res = fut.result()
            done += 1
            batch.append(res)
            scored += res["status"] == "scored"
            missing += res["status"] == "missing"
            error += res["status"] == "error"
            if len(batch) >= 25:
                upsert(batch); batch = []
            if done % 50 == 0:
                print(f"  {done}/{len(todo)}  scored={scored} missing={missing} "
                      f"error={error}", flush=True)
    upsert(batch)
    print(f"done this run: scored={scored} missing={missing} error={error}", flush=True)

    verify(counts_before)


# --------------------------------------------------------------------------- #
# concurrency burst test (find the endpoint's safe concurrency)
# --------------------------------------------------------------------------- #
def _timed_call(messages: list[dict], key: str) -> dict:
    t0 = time.time()
    try:
        raw = call_llm(messages, key)
        return {"ok": True, "latency": time.time() - t0, "err": None,
                "score": parse_score(raw)}
    except requests.HTTPError as exc:
        code = exc.response.status_code if exc.response is not None else "?"
        return {"ok": False, "latency": time.time() - t0, "err": f"HTTP {code}"}
    except Exception as exc:
        return {"ok": False, "latency": time.time() - t0, "err": type(exc).__name__}


def burst_test(levels=(2, 4, 8, 12, 16)) -> int:
    """Ramp concurrency against the endpoint using real filing payloads; stop when
    errors/throttling appear. Prints a table and returns a recommended concurrency."""
    import collections
    key = get_api_key()
    session = sec.make_session()
    reports = load_us_reports()

    # build a few representative payloads (varied size) once
    def latest(t, f):
        cs = [r for r in reports if r["ticker"] == t and r["form"] == f]
        return max(cs, key=lambda r: r["report_release_date"]) if cs else None
    picks = [p for p in (latest("AAPL", "10-K"), latest("JPM", "10-K"),
                         latest("AAPL", "10-Q"), latest("MSFT", "10-Q"),
                         latest("KO", "10-Q")) if p]
    payloads = []
    for rep in picks:
        prep = prepare_payload(session, rep)
        if prep["ok"]:
            payloads.append(build_messages(prep["payload"], rep["form"],
                                           rep["report_release_date"]))
    if not payloads:
        raise SystemExit("burst test could not build any payload")

    print(f"BURST TEST — model={MODEL}, {len(payloads)} payloads, ramping {levels}",
          flush=True)
    print(f"{'conc':>5} {'ok':>4} {'err':>4} {'wall_s':>8} {'med_lat':>8} "
          f"{'thruput/s':>9}  errors", flush=True)
    best = 1
    best_thru = 0.0
    for c in levels:
        msgs = [payloads[i % len(payloads)] for i in range(c)]
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=c) as ex:
            results = list(ex.map(lambda m: _timed_call(m, key), msgs))
        wall = time.time() - t0
        ok = [r for r in results if r["ok"]]
        errs = [r["err"] for r in results if not r["ok"]]
        med = statistics.median([r["latency"] for r in ok]) if ok else float("nan")
        thru = len(ok) / wall if wall else 0
        print(f"{c:>5} {len(ok):>4} {len(errs):>4} {wall:>8.1f} {med:>8.1f} "
              f"{thru:>9.2f}  {dict(collections.Counter(errs)) if errs else ''}",
              flush=True)
        if errs:                               # throttling/failures -> stop ramping
            print(f"  -> errors at concurrency {c}; not ramping further", flush=True)
            break
        if thru >= best_thru:
            best_thru, best = thru, c
        time.sleep(2)                          # let the endpoint breathe between levels
    print(f"\nRecommended concurrency: {best} (throughput ~{best_thru:.2f} calls/s)",
          flush=True)
    return best


def verify(counts_before: dict | None = None) -> None:
    with closing(db.get_connection()) as con:
        counts = _counts(con)
        total = con.execute("SELECT COUNT(*) FROM operative_scores").fetchone()[0]
        by_status = dict(con.execute(
            "SELECT status, COUNT(*) FROM operative_scores GROUP BY status").fetchall())
        dist = dict(con.execute(
            "SELECT operative_score_raw, COUNT(*) FROM operative_scores "
            "WHERE status='scored' GROUP BY operative_score_raw ORDER BY operative_score_raw"
        ).fetchall())
        trunc = con.execute(
            "SELECT COUNT(*) FROM operative_scores WHERE truncated=1").fetchone()[0]
        mdna_src = dict(con.execute(
            "SELECT mdna_source, COUNT(*) FROM operative_scores GROUP BY mdna_source").fetchall())
        samples = con.execute(
            "SELECT ticker, fiscal_period_end_date, form, operative_score_raw, operative_score "
            "FROM operative_scores WHERE status='scored' "
            "ORDER BY report_release_date DESC LIMIT 3").fetchall()

    print("\n" + "=" * 60)
    print(f"operative_scores rows: {total}")
    print(f"by status: {by_status}")
    print(f"score distribution (1-5): {dist}")
    print(f"truncated filings: {trunc}")
    print(f"MD&A source breakdown: {mdna_src}")
    print("sample scored rows:")
    for s in samples:
        print(f"   {s['ticker']:6} {s['fiscal_period_end_date']} {s['form']:5} "
              f"raw={s['operative_score_raw']} rescaled={s['operative_score']}")
    print("untouched-table counts (must be unchanged):")
    for t, n in counts.items():
        if counts_before is not None:
            flag = "UNCHANGED" if counts_before.get(t) == n else "CHANGED! investigate"
            print(f"   {t:16} {counts_before.get(t)} -> {n}  ({flag})")
        else:
            print(f"   {t:16} {n}")


# --------------------------------------------------------------------------- #
# Stage 2 — international 20-F: dry-run + full run
# --------------------------------------------------------------------------- #
_F20_LABELS = {"mdna": "Item 5 (MD&A-equiv)", "risk": "Item 3.D (Risk)",
               "business": "Item 4 (Business)"}


def _op_us_fingerprint(con) -> tuple[int, str]:
    """(count, sha256) of the US operative rows (source='edgar'), to prove Stage-2
    never touches them."""
    import hashlib
    rows = con.execute(
        "SELECT ticker, report_release_date, accession_number, operative_score_raw, "
        "operative_score, status, mdna_source FROM operative_scores WHERE source='edgar' "
        "ORDER BY ticker, report_release_date, accession_number").fetchall()
    payload = repr([tuple(r) for r in rows]).encode()
    return len(rows), hashlib.sha256(payload).hexdigest()


def dry_run_intl(sample_tickers=("SAP.DE", "8306.T", "ASML.AS")) -> None:
    session = sec.make_session()
    key = os.environ.get(ENV_KEY_NAME)
    reports = load_intl_20f_reports(session)

    print("=" * 92)
    print(f"STAGE 2a DRY-RUN (20-F) — {len(sample_tickers)} names. NO writes. "
          f"model={MODEL} temp={TEMPERATURE} prompt={PROMPT_VERSION}")
    print(f"API key env {ENV_KEY_NAME}: {'SET' if key else 'NOT SET (live calls skipped)'}")
    print(f"total 20-F filings discovered across 11 names: {len(reports)}")
    print("=" * 92)

    for tk in sample_tickers:
        cands = [r for r in reports if r["ticker"] == tk]
        print("\n" + "#" * 92)
        if not cands:
            print(f"### {tk}: no 20-F filings found"); continue
        rep = max(cands, key=lambda r: r["report_release_date"])
        print(f"### {tk} 20-F  cik={rep['cik']} release={rep['report_release_date']} "
              f"period={rep['fiscal_period_end_date']} acc={rep['accession_number']}")
        prep = prepare_payload(session, rep)
        if prep["error"]:
            print(f"  FETCH FAILED: {prep['error']}"); continue
        for k in ("mdna", "risk", "business"):
            sec = prep["sections"][k]
            print(f"  [{_F20_LABELS[k]:20}] len={len(sec):>7}  "
                  f"first200: {sec[:200].replace(chr(10), ' ')!r}")
        print(f"  mdna_source={prep['mdna_source']}  payload={len(prep['payload'])}  "
              f"truncated={prep['truncated']}  scorable={prep['ok']}")
        if not prep["ok"]:
            print("  -> NOT SCORABLE (Item 5 not cleanly extractable) — would be MISSING")
            continue
        if not key:
            print("  (LIVE CALL SKIPPED — env var not set)"); continue
        res = score_report(rep, session, key)
        print(f"  SCORE raw={res['operative_score_raw']} rescaled={res['operative_score']} "
              f"status={res['status']}")
        try:
            ex = call_llm(build_messages(prep["payload"], rep["form"],
                                         rep["report_release_date"],
                                         system=PREVIEW_EXPLAIN_PROMPT), key)
            print("  EVIDENCE NOTE (diagnostic, not stored):\n     "
                  + ex.strip().replace("\n", "\n     "))
        except Exception as exc:
            print(f"  EVIDENCE NOTE unavailable: {exc}")

    print("\n" + "=" * 92)
    print("STAGE 2a complete. Nothing written. Review, then run --intl-write.")


def run_intl(concurrency: int = 1, since_year: int | None = None) -> None:
    key = get_api_key()
    with closing(db.get_connection()) as con:
        counts_before = _counts(con)
        us_before = _op_us_fingerprint(con)
    create_table()
    reports = load_intl_20f_reports(since_year=since_year)
    cached = already_scored()
    todo = [r for r in reports if r["accession_number"] not in cached]
    print(f"20-F filings: {len(reports)} | already scored (cached): "
          f"{len(reports) - len(todo)} | to score now: {len(todo)} | "
          f"concurrency={concurrency}", flush=True)

    def worker(rep):
        return score_report(rep, _thread_session(), key)

    batch, scored, missing, error, done = [], 0, 0, 0, 0
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futures = {ex.submit(worker, rep): rep for rep in todo}
        for fut in as_completed(futures):
            res = fut.result(); done += 1; batch.append(res)
            scored += res["status"] == "scored"
            missing += res["status"] == "missing"
            error += res["status"] == "error"
            if len(batch) >= 25:
                upsert(batch); batch = []
            if done % 20 == 0:
                print(f"  {done}/{len(todo)} scored={scored} missing={missing} "
                      f"error={error}", flush=True)
    upsert(batch)
    print(f"done this run: scored={scored} missing={missing} error={error}", flush=True)

    verify(counts_before)
    with closing(db.get_connection()) as con:
        us_after = _op_us_fingerprint(con)
    ok = us_before == us_after
    print(f"\nUS operative rows (source='edgar'): {us_before[0]} -> {us_after[0]} | "
          f"fingerprint {'IDENTICAL' if ok else 'CHANGED! investigate'}")
    # per-name breakdown of the international rows
    with closing(db.get_connection()) as con:
        per = con.execute(
            "SELECT ticker, status, COUNT(*) n FROM operative_scores "
            "WHERE source=? GROUP BY ticker, status ORDER BY ticker", (INTL_SOURCE,)
        ).fetchall()
    print("\ninternational 20-F rows per name/status:")
    for r in per:
        print(f"   {r['ticker']:12} {r['status']:8} {r['n']}")


def main() -> None:
    args = sys.argv
    if "--burst" in args:
        burst_test()
    elif "--intl-dry-run" in args:
        dry_run_intl()
    elif "--intl-write" in args:
        concurrency = 1
        if "--concurrency" in args:
            concurrency = int(args[args.index("--concurrency") + 1])
        since = None
        if "--since-year" in args:
            since = int(args[args.index("--since-year") + 1])
        run_intl(concurrency=concurrency, since_year=since)
    elif "--write" in args:
        concurrency = 1
        if "--concurrency" in args:
            concurrency = int(args[args.index("--concurrency") + 1])
        run_full(concurrency=concurrency)
    else:
        dry_run()


if __name__ == "__main__":
    main()
