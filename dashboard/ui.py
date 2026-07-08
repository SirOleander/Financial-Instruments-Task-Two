"""
ui.py — visual identity for the Signal Desk dashboard (deep-navy + indigo/purple accent).

Palette discipline (this is load-bearing, not taste):
  * CHROME is navy + a single indigo/purple accent. The accent marks INTERACTION (selection,
    active nav, focus) and doubles as the primary SERIES hue where a chart needs one
    (the Validation line, importance bars). It never encodes performance polarity.
  * GREEN/RED are RESERVED status colors for performance semantics (up/down, long/short)
    and are never used for chrome, nor for reference lines, nor for metrics that merely hug
    zero. They always ship with a sign or a text label, so identity is never colour-alone.
  * Metrics that are indistinguishable from zero/chance get NEUTRAL fills and a prominent
    reference rule. Dramatising noise with green/red would misrepresent the finding.
  * SECTOR hues are the categorical palette; they encode data (sector identity), never
    performance, and always sit beside the ticker text + a hover title (secondary encoding).

The sector palette was DERIVED, not eyeballed: one shared hue set stepped into each mode's
OKLCH lightness band, chosen to maximise the minimum ALL-PAIRS Machado-2009 protan/deutan
CIE76 dE (sector badges appear in arbitrary juxtaposition, so the stricter all-pairs rule
applies, not adjacent-only). Result: min dE = 18.6 (dark) / 17.4 (light), both above the
>=12 target; every hue sits in-band, above the 0.10 chroma floor, and at >=3:1 contrast on
its surface. The previous palette failed all three checks (Industrials read gray at C=0.029;
Communication<->Industrials collapsed to dE=3.9 under deutan).

Because ALL pairs were validated, the sector->hue assignment below is permutation-invariant:
it is ordered for semantic sense without weakening CVD safety.

Two full palettes (light/dark) are injected as literal hex per run — the theme toggle just
flips st.session_state['mode'] and Streamlit re-runs, so no runtime CSS-variable juggling.
"""
from __future__ import annotations

import re

import streamlit as st

# ------------------------------------------------------------------ palettes ---------- #
DARK = dict(
    bg="#0a0e1f", panel="#111634", card="#151a38", border="#262c4e", border_soft="#1d2342",
    text="#b9c0d9", strong="#f2f4fa", muted="#7c86a8", faint="#5c6785",
    sel_bg="#1e2450", sel_bar="#7b61ff", hover="#171d3d", input_bg="#121738",
    accent="#7b61ff", accent_soft="#a78bfa", accent_dim="#2a2560",
    up="#26a69a", down="#ef5350",
)
LIGHT = dict(
    bg="#ffffff", panel="#f5f6fc", card="#ffffff", border="#e1e4f0", border_soft="#edeff7",
    text="#3b415c", strong="#0a0e1f", muted="#6e7690", faint="#8a93b2",
    sel_bg="#efecfd", sel_bar="#5b45e0", hover="#f4f5fb", input_bg="#ffffff",
    accent="#5b45e0", accent_soft="#7c66ea", accent_dim="#e8e4fb",
    up="#089981", down="#f23645",
)


def palette(mode: str) -> dict:
    return LIGHT if mode == "light" else DARK


# 9 sectors -> the validated categorical hue set (see module docstring). Same hues in both
# modes, stepped for each surface's lightness band.
SECTOR_COLORS_DARK = {
    "Technology": "#0074c7", "Banks": "#3b68e8", "Financial Services": "#00a5c9",
    "Healthcare": "#00816d", "Consumer Staples": "#00834b",
    "Consumer Discretionary": "#aa228c", "Communication": "#f1528e",
    "Industrials": "#b67000", "Energy, Materials & Utilities": "#c81f35",
}
SECTOR_COLORS_LIGHT = {
    "Technology": "#0077cd", "Banks": "#4575f6", "Financial Services": "#00a2c6",
    "Healthcare": "#008672", "Consumer Staples": "#008f52",
    "Consumer Discretionary": "#ae2790", "Communication": "#f2538f",
    "Industrials": "#b36e00", "Energy, Materials & Utilities": "#d12b3c",
}
SECTOR_FALLBACK = {"dark": "#7c86a8", "light": "#6e7690"}


def sector_color(sector: str, mode: str = "dark") -> str:
    table = SECTOR_COLORS_LIGHT if mode == "light" else SECTOR_COLORS_DARK
    return table.get(sector, SECTOR_FALLBACK["light" if mode == "light" else "dark"])


def safe_key(ticker: str) -> str:
    return "co_" + re.sub(r"\W", "_", ticker)


# ------------------------------------------------------------------ theme -------------- #
def inject_theme(companies, mode: str, logo_uris: dict[str, str] | None = None) -> None:
    P = palette(mode)
    logo_uris = logo_uris or {}
    # per-ticker badge tile: real logo on a white chip if cached, else a sector-colored tile.
    rules = []
    for t, s in zip(companies["ticker"], companies["sector"]):
        sel = f".st-key-colist .st-key-{safe_key(t)} button::before"
        if t in logo_uris:
            # `contain` (not a %) — the URI is already trimmed + margined to a square canvas
            # by data._normalize_logo, so contain fills the tile at the mark's true aspect.
            rules.append(f"{sel}{{background:#fff url({logo_uris[t]}) center/contain no-repeat;"
                         f"border-color:{P['border_soft']};}}")
        else:
            rules.append(f"{sel}{{background:{sector_color(s, mode)};}}")
    dot_rules = "\n".join(rules)
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

    html, body, .stApp, [class*="css"] {{
      font-family:'Inter',-apple-system,Segoe UI,Roboto,sans-serif; color:{P['text']};
    }}
    .stApp {{ background:{P['bg']}; }}
    #MainMenu, header[data-testid="stHeader"], footer {{ visibility:hidden; height:0; }}
    /* Watchlist sits hard against the left window edge: kill the centering max-width and the
       big left gutter. ~0.85rem here + the column's own padding lands the first ticker tile
       roughly 1cm from the border. Right side keeps its normal gutter. */
    .block-container {{ padding:0 2.2rem 3rem .85rem; max-width:100%; }}
    .mono, code {{ font-family:'IBM Plex Mono',ui-monospace,monospace; }}
    hr {{ border-color:{P['border_soft']}; }}

    /* ---------------- slim top bar ---------------- */
    /* Sticky must go on the WRAPPER, not on .st-key-topbar. Streamlit wraps a keyed container
       in a `stLayoutWrapper` sized to its content (73px), and a sticky element is confined to
       its containing block — so sticking the inner div made it stick for 73px and then scroll
       away. The wrapper IS a direct child of the tall page vertical block, so it sticks for
       the whole page. This matters now the watchlist scrolls with the page: the search box is
       the only way to jump to a company once you've scrolled down. */
    [data-testid="stLayoutWrapper"]:has(> .st-key-topbar) {{
      position:sticky; top:0; z-index:60; background:{P['bg']};
    }}
    .st-key-topbar {{
      border-bottom:1px solid {P['border']}; padding:10px 4px 8px; margin-bottom:14px;
      background:{P['bg']};
    }}
    .st-key-topbar [data-testid="stHorizontalBlock"] {{ align-items:center; }}
    .sd-logo {{ display:flex; align-items:center; gap:11px; }}
    .sd-logo .mark {{
      width:30px;height:30px;border-radius:8px;flex:0 0 auto;
      border:1px solid {P['border']}; display:flex;align-items:center;justify-content:center;
      color:{P['muted']}; font-family:'IBM Plex Mono',monospace; font-size:.62rem; letter-spacing:.06em;
      background:{P['panel']};
    }}
    .sd-logo .wm {{ font-family:'IBM Plex Mono',monospace; font-weight:600; letter-spacing:.24em;
      font-size:.92rem; color:{P['strong']}; }}
    .sd-logo .wm .dim {{ color:{P['faint']}; }}

    /* ---------------- inputs (search + selectbox) ---------------- */
    .stTextInput input, [data-baseweb="select"] > div {{
      background:{P['input_bg']} !important; border:1px solid {P['border']} !important;
      color:{P['text']} !important; border-radius:8px !important; font-size:.85rem !important;
      box-shadow:none !important;
    }}
    .stTextInput input::placeholder {{ color:{P['faint']} !important; }}
    .stTextInput input:focus, [data-baseweb="select"] > div:focus-within {{
      border-color:{P['accent']} !important;
      box-shadow:0 0 0 3px {P['accent']}26 !important; }}
    [data-baseweb="popover"], [data-baseweb="menu"], [role="listbox"] {{
      background:{P['card']} !important; border:1px solid {P['border']} !important; }}
    [role="option"] {{ color:{P['text']} !important; }}
    [role="option"]:hover {{ background:{P['hover']} !important; }}

    /* ---------------- top nav: FOUR STANDALONE pills beside the search ----------------
       Not a fused segmented group — each item is its own bordered button with a real gap. */
    .st-key-navbar [data-testid="stHorizontalBlock"] {{ gap:9px; }}
    .st-key-navbar [data-testid="stButton"] button {{
      width:100%; min-height:0; padding:7px 12px; border-radius:9px;
      border:1px solid {P['border']} !important; background:{P['card']} !important;
      color:{P['muted']} !important; font-family:'Inter',sans-serif; font-weight:550;
      font-size:.82rem; letter-spacing:.01em; box-shadow:none !important;
      transition:color .1s ease, border-color .1s ease, background .1s ease;
    }}
    .st-key-navbar [data-testid="stButton"] button:hover {{
      color:{P['strong']} !important; border-color:{P['accent']}88 !important;
      background:{P['hover']} !important; }}
    .st-key-navbar [data-testid="stButton"] button[kind="primary"] {{
      background:{P['accent']} !important; border-color:{P['accent']} !important;
      color:#fff !important; font-weight:650;
      box-shadow:0 2px 10px {P['accent']}4d !important; }}

    /* ---------------- in-content segmented controls (cost, model, scheme) ------------- */
    div[data-testid="stSegmentedControl"] [role="radiogroup"] {{ gap:2px; background:transparent; border:none; }}
    div[data-testid="stSegmentedControl"] button {{
      font-family:'Inter',sans-serif; font-weight:500; font-size:.84rem; letter-spacing:.01em;
      color:{P['muted']} !important; background:transparent !important; border:none !important;
      border-radius:7px !important; padding:6px 14px !important;
    }}
    div[data-testid="stSegmentedControl"] button:hover {{ color:{P['strong']} !important;
      background:{P['hover']} !important; }}
    /* active nav = the accent's job (interaction, never data) */
    div[data-testid="stSegmentedControl"] button[aria-checked="true"],
    div[data-testid="stSegmentedControl"] button[kind="segmented_controlActive"] {{
      color:#fff !important; background:{P['accent']} !important; font-weight:600;
      box-shadow:0 2px 10px {P['accent']}4d; }}

    /* ---------------- inner tabs (Model / Data curation) ---------------- */
    .stTabs [data-baseweb="tab-list"] {{ gap:2px; border-bottom:1px solid {P['border_soft']};
      background:transparent; }}
    .stTabs [data-baseweb="tab"] {{
      color:{P['muted']}; font-size:.8rem; font-weight:500; letter-spacing:.02em;
      background:transparent; border-radius:8px 8px 0 0; padding:8px 14px; }}
    .stTabs [data-baseweb="tab"]:hover {{ color:{P['strong']}; background:{P['hover']}; }}
    .stTabs [aria-selected="true"] {{ color:{P['accent']} !important; font-weight:650; }}
    .stTabs [data-baseweb="tab-highlight"] {{ background:{P['accent']}; height:2px; }}
    .stTabs [data-baseweb="tab-border"] {{ background:transparent; }}

    /* theme toggle button */
    .st-key-themebtn button {{
      background:transparent !important; border:1px solid {P['border']} !important;
      color:{P['muted']} !important; border-radius:8px !important; min-height:0 !important;
      padding:6px 10px !important; font-size:.95rem !important; }}
    .st-key-themebtn button:hover {{ color:{P['strong']} !important; border-color:{P['muted']} !important; }}

    /* ---------------- watchlist (left column) ---------------- */
    .st-key-watchlist {{ border-right:1px solid {P['border_soft']}; padding-right:14px; }}
    .sd-wl-label {{ color:{P['faint']}; font-size:.64rem; letter-spacing:.18em; text-transform:uppercase;
      font-weight:600; margin:2px 2px 8px; display:flex; justify-content:space-between; }}
    .sd-wl-label .ct {{ color:{P['muted']}; }}
    /* The watchlist scrolls WITH THE PAGE — it is not its own scroll container. There is no
       inner scrollbar anywhere in the app; .stMain (the page) is the single scroller. Do NOT
       reintroduce max-height + overflow-y here: the whole column is part of the page flow, so
       it scrolls off-screen as the user goes down, and the top-bar search is how you jump to a
       company from anywhere. `overflow-x:hidden` alone would ALSO create a scroll container
       (any non-visible overflow on one axis makes the other axis a scrollport), so it is gone
       too — long tickers are clipped by the button's own text-overflow instead. */
    .st-key-colist {{ padding-right:5px; }}

    /* icon tiles: 30px was too small to read a logo — 40px with a tighter crop */
    .st-key-colist [data-testid="stButton"] button {{
      display:flex; align-items:center; gap:12px; width:100%; text-align:left; min-height:0;
      background:transparent; border:1px solid transparent; border-left:2px solid transparent;
      border-radius:9px; padding:8px 11px; margin:3px 0; color:{P['text']};
      font-family:'IBM Plex Mono',monospace; font-weight:500; font-size:.88rem; letter-spacing:.02em;
      transition:background .1s ease, border-color .1s ease;
    }}
    .st-key-colist [data-testid="stButton"] button::before {{
      content:""; flex:0 0 auto; width:40px; height:40px; border-radius:9px;
      background:{P['faint']}; border:1px solid transparent;
      box-shadow:0 1px 3px rgba(0,0,0,.18); }}
    /* clip long tickers at the button — the column no longer has overflow-x to do it */
    .st-key-colist [data-testid="stButton"] button p {{
      overflow:hidden; text-overflow:ellipsis; white-space:nowrap; min-width:0; }}
    .st-key-colist [data-testid="stButton"] button:hover {{ background:{P['hover']}; }}
    .st-key-colist [data-testid="stButton"] button[kind="primary"] {{
      background:{P['sel_bg']}; border-left:2px solid {P['sel_bar']}; color:{P['strong']}; font-weight:600; }}
    {dot_rules}

    /* ---------------- content ---------------- */
    .sd-view-title {{ font-size:1.4rem; font-weight:700; letter-spacing:-.01em; color:{P['strong']}; margin:0; }}
    .sd-view-sub {{ color:{P['muted']}; font-size:.85rem; margin:3px 0 20px; }}
    .sd-soon {{ border:1px dashed {P['border']}; border-radius:12px; padding:50px 26px; text-align:center;
      color:{P['faint']}; background:{P['panel']}; }}
    .sd-soon .stage {{ display:inline-block; font-family:'IBM Plex Mono',monospace; font-size:.64rem;
      letter-spacing:.22em; text-transform:uppercase; color:{P['muted']}; border:1px solid {P['border']};
      border-radius:999px; padding:4px 12px; margin-bottom:15px; }}
    .sd-soon h3 {{ color:{P['strong']}; font-weight:600; margin:0 0 6px; font-size:1.02rem; }}
    .sd-soon p {{ margin:0; font-size:.85rem; }}

    .sd-hero {{ border:1px solid {P['border']}; border-radius:12px; padding:20px 22px; background:{P['card']};
      display:flex; align-items:center; gap:16px; margin-bottom:16px; }}
    .sd-hero .tkb {{ font-family:'IBM Plex Mono',monospace; font-weight:600; font-size:.9rem; color:#fff;
      width:58px;height:58px;border-radius:12px;display:flex;align-items:center;justify-content:center;flex:0 0 auto; }}
    .sd-hero .nm {{ font-size:1.2rem; font-weight:700; color:{P['strong']}; }}
    .sd-hero .sub {{ color:{P['muted']}; font-size:.78rem; font-family:'IBM Plex Mono',monospace;
      letter-spacing:.05em; margin-top:3px; }}
    .sd-chip {{ display:inline-block; font-size:.62rem; letter-spacing:.13em; text-transform:uppercase;
      border:1px solid {P['border']}; border-radius:999px; padding:3px 10px; color:{P['muted']}; margin-left:8px; }}
    .sd-empty {{ color:{P['muted']}; border:1px dashed {P['border']}; border-radius:12px; padding:40px;
      text-align:center; background:{P['panel']}; }}

    /* section heading + note */
    .sd-sec {{ font-size:.72rem; letter-spacing:.16em; text-transform:uppercase; font-weight:700;
      color:{P['muted']}; margin:26px 0 12px; padding-bottom:7px; border-bottom:1px solid {P['border_soft']}; }}
    .sd-note {{ color:{P['muted']}; font-size:.8rem; line-height:1.5; margin:6px 0 4px; }}

    /* KPI stat tiles — accent hairline marks them as the headline read */
    .sd-tiles {{ display:flex; gap:12px; flex-wrap:wrap; margin:4px 0 6px; }}
    .sd-tile {{ flex:1; min-width:150px; border:1px solid {P['border']}; border-radius:11px;
      padding:14px 16px; background:{P['card']}; position:relative; overflow:hidden; }}
    .sd-tile::before {{ content:""; position:absolute; left:0; top:0; bottom:0; width:2px;
      background:linear-gradient(180deg,{P['accent']},{P['accent']}00); }}
    .sd-tile .v {{ font-family:'IBM Plex Mono',monospace; font-size:1.45rem; font-weight:600;
      color:{P['strong']}; line-height:1.1; }}
    .sd-tile .l {{ font-size:.66rem; letter-spacing:.1em; text-transform:uppercase; color:{P['muted']};
      margin-top:6px; }}
    .sd-tile .s {{ font-size:.72rem; color:{P['faint']}; margin-top:3px; }}

    /* ---------------- ranking table: full-page HTML grid, no inner scrollbar ----------------
       Each row is a plain grid div with a TRANSPARENT st.button stretched over it, so the whole
       row is clickable while the click stays in-session (no page reload, no canvas checkbox
       column). The row container must be position:relative for the overlay to anchor. */
    .sd-rt-head, .sd-rt-row {{
      display:grid; grid-template-columns:{RANK_COLS}; align-items:center; gap:10px;
      padding:0 12px; }}
    /* NOTE: `position:sticky` does not actually stick here — the scroll container is
       Streamlit's .stMain flex column, which defeats it (the top bar has the same issue).
       Kept harmlessly; the header scrolls away with the page, which is normal for a
       full-page table. Do not "fix" by giving the table its own scroll container: an inner
       scrollbar is exactly what this table is meant not to have. */
    .sd-rt-head {{
      position:sticky; top:64px; z-index:20; background:{P['bg']};
      border-bottom:1px solid {P['border']}; padding-top:9px; padding-bottom:9px;
      margin-top:4px; }}
    .sd-rt-head .h {{ font-size:.63rem; letter-spacing:.14em; text-transform:uppercase;
      font-weight:700; color:{P['faint']}; }}
    .sd-rt-head .h:nth-child(6) {{ text-align:right; }}

    /* fixed px, not 100%: an unnamed emotion wrapper sits between stMarkdown and
       stMarkdownContainer and collapses to content height, so a percentage never resolves */
    .sd-rt-row {{ height:{RANK_ROW_H}px; border-bottom:1px solid {P['border_soft']};
      border-radius:6px; transition:background .08s ease; }}
    .sd-rt-row .c {{ overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
    .sd-rt-row .rank {{ font-family:'IBM Plex Mono',monospace; font-size:.8rem;
      color:{P['muted']}; }}
    .sd-rt-row .logo {{ display:flex; align-items:center; }}
    .sd-rt-row .logo img {{ width:26px; height:26px; border-radius:6px; background:#fff;
      object-fit:contain; padding:1px; }}
    .sd-rt-row .logo .fallback {{ width:26px; height:26px; border-radius:6px; color:#fff;
      display:flex; align-items:center; justify-content:center;
      font-family:'IBM Plex Mono',monospace; font-size:.58rem; font-weight:700; }}
    .sd-rt-row .tk {{ font-family:'IBM Plex Mono',monospace; font-weight:600; font-size:.83rem;
      color:{P['strong']}; }}
    .sd-rt-row .nm {{ font-size:.83rem; color:{P['text']}; }}
    .sd-rt-row .sec {{ font-size:.78rem; color:{P['muted']}; }}
    /* predicted Sharpe is a MODEL OUTPUT, not realized performance -> neutral, never up/down */
    .sd-rt-row .ps {{ font-family:'IBM Plex Mono',monospace; font-size:.85rem; font-weight:600;
      color:{P['strong']}; text-align:right; }}
    .sd-rt-row .pill {{ font-family:'IBM Plex Mono',monospace; font-size:.63rem; font-weight:700;
      letter-spacing:.06em; border:1px solid; border-radius:5px; padding:2px 6px; }}
    .sd-rt-row .mid {{ color:{P['faint']}; }}
    .sd-rt-row.sel {{ outline:1px solid {P['accent']}; outline-offset:-1px; }}

    /* Anchor the overlay. The row container MUST carry an explicit height: with the button
       absolutely positioned it leaves the flow, and Streamlit's vertical block otherwise
       collapses to the button's natural 28px, so `inset:0` would stretch the overlay over
       28px of a 44px row and the row's own middle would not be clickable. Every wrapper
       between the container and .sd-rt-row is forced to 100% for the same reason. */
    /* `flex:0 0 Npx` is load-bearing: Streamlit makes each row container a column-flex item
       with `flex:1 1 0%`, and a flex-basis of 0% BEATS `height`, collapsing the row to its
       content (27px) no matter what height we set. */
    div[class*="st-key-rkrow_"] {{
      position:relative; flex:0 0 {RANK_ROW_H}px !important;
      height:{RANK_ROW_H}px; min-height:{RANK_ROW_H}px; margin-bottom:2px; }}
    /* kill Streamlit's 1rem inter-element gap BETWEEN rows, else 44px rows sit 62px apart */
    div[class*="st-key-ranktable"] {{ gap:0 !important; }}
    div[class*="st-key-rkrow_"] > [data-testid="stVerticalBlock"] {{
      height:100%; gap:0 !important; }}
    div[class*="st-key-rkrow_"] [data-testid="stElementContainer"]:not([class*="st-key-rkbtn_"]) {{
      height:100%; margin:0 !important; }}
    div[class*="st-key-rkrow_"] [data-testid="stMarkdown"],
    div[class*="st-key-rkrow_"] [data-testid="stMarkdownContainer"] {{
      height:100%; margin:0 !important; }}
    div[class*="st-key-rkrow_"]:hover .sd-rt-row {{ background:{P['hover']} !important; }}

    /* the invisible full-row click target (keeps an accessible name for screen readers) */
    div[class*="st-key-rkbtn_"] {{
      position:absolute; inset:0; width:100%; height:100% !important; z-index:5;
      margin:0 !important; }}
    div[class*="st-key-rkbtn_"] button {{
      width:100%; height:100% !important; min-height:0 !important; padding:0 !important;
      background:transparent !important; border:none !important; box-shadow:none !important;
      color:transparent !important; font-size:0 !important; cursor:pointer; }}
    div[class*="st-key-rkbtn_"] button:hover, div[class*="st-key-rkbtn_"] button:active,
    div[class*="st-key-rkbtn_"] button:focus {{
      background:transparent !important; border:none !important; color:transparent !important;
      box-shadow:none !important; }}
    div[class*="st-key-rkbtn_"] button:focus-visible {{
      outline:2px solid {P['accent']}; outline-offset:-2px; }}

    /* matplotlib figures: sit on an intentional light card in either theme */
    [data-testid="stImage"] img {{ background:#fff; border:1px solid {P['border']};
      border-radius:10px; padding:8px; max-width:100%; }}
    </style>
    """, unsafe_allow_html=True)


def logo_html() -> str:
    return ('<div class="sd-logo"><span class="mark">SD</span>'
            '<span class="wm">SIGNAL<span class="dim">·</span>DESK</span></div>')


def hero_badge(ticker: str, sector: str, logo_uri: str | None, mode: str = "dark") -> str:
    """Detail-hero badge: real logo on a white tile if available, else a sector-colored
    tile with the ticker's leading characters (graceful, never a broken image)."""
    if logo_uri:
        return (f'<div class="tkb" style="background:#fff url({logo_uri}) center/contain '
                f'no-repeat;border:1px solid rgba(0,0,0,.14)"></div>')
    return (f'<div class="tkb" style="background:{sector_color(sector, mode)}">'
            f'{ticker.split(".")[0][:4]}</div>')


def scope_note(mode: str, text: str) -> None:
    """The single prominent tab-level scope/caveat statement on the Ranking view.

    This REPLACED a per-row 'Confidence' column. A per-row train/prediction-only flag
    contradicted the ranking itself — it marked the very rows the ranking was recommending.
    The honest disclosure belongs once, at tab level, describing the whole book. Rendered in
    the accent (chrome/attention), never green/red: it is scope, not performance."""
    P = palette(mode)
    st.markdown(
        f'<div style="border:1px solid {P["accent"]}55;border-left:3px solid {P["accent"]};'
        f'border-radius:10px;padding:13px 16px;margin:2px 0 16px;background:{P["accent_dim"]};'
        f'color:{P["text"]};font-size:.82rem;line-height:1.6;">'
        f'<div style="font-size:.64rem;letter-spacing:.18em;text-transform:uppercase;'
        f'font-weight:700;color:{P["accent_soft"] if mode == "dark" else P["accent"]};'
        f'margin-bottom:6px;">Scope of the model</div>{text}</div>',
        unsafe_allow_html=True)


# ------------------------------------------------------------- ranking table ------------ #
# One shared grid template for the header and every row, so columns line up exactly.
RANK_COLS = "62px 46px 96px minmax(190px,1fr) 210px 118px 96px"
RANK_HEADS = ["Rank", "", "Ticker", "Company", "Sector", "Pred. Sharpe", "Basket"]
RANK_ROW_H = 44  # px — must be a fixed height; the click overlay is sized against it


def ranking_table_head() -> None:
    cells = "".join(f'<div class="h">{h}</div>' for h in RANK_HEADS)
    st.markdown(f'<div class="sd-rt-head">{cells}</div>', unsafe_allow_html=True)


def ranking_row_html(mode: str, *, rank: int, logo: str | None, ticker: str, name: str,
                     sector: str, pred: float, basket: str, selected: bool) -> str:
    """One full-width grid row. Basket pills use the reserved green/red (real long/short
    semantics); the predicted Sharpe stays NEUTRAL — it is a model output, not realized
    performance, and colouring it green/red would imply a result the model does not have."""
    P = palette(mode)
    tint = (f"{P['up']}26" if basket == "LONG"
            else f"{P['down']}26" if basket == "SHORT" else "transparent")
    badge = (f'<img src="{logo}" alt="">' if logo
             else f'<span class="fallback" style="background:{sector_color(sector, mode)}">'
                  f'{ticker.split(".")[0][:2]}</span>')
    pill = (f'<span class="pill" style="color:{P["up"]};border-color:{P["up"]}66">LONG</span>'
            if basket == "LONG" else
            f'<span class="pill" style="color:{P["down"]};border-color:{P["down"]}66">SHORT</span>'
            if basket == "SHORT" else '<span class="mid">—</span>')
    sel = " sel" if selected else ""
    return (f'<div class="sd-rt-row{sel}" style="background:{tint}">'
            f'<div class="c rank">{rank}</div>'
            f'<div class="c logo">{badge}</div>'
            f'<div class="c tk">{ticker}</div>'
            f'<div class="c nm">{name}</div>'
            f'<div class="c sec">{sector}</div>'
            f'<div class="c ps">{pred:+.2f}</div>'
            f'<div class="c bk">{pill}</div></div>')


def coming_soon(stage: str, title: str, body: str) -> None:
    st.markdown(f'<div class="sd-soon"><span class="stage">{stage}</span>'
                f'<h3>{title}</h3><p>{body}</p></div>', unsafe_allow_html=True)


def section(title: str) -> None:
    st.markdown(f'<div class="sd-sec">{title}</div>', unsafe_allow_html=True)


def note(text: str) -> None:
    st.markdown(f'<div class="sd-note">{text}</div>', unsafe_allow_html=True)


def stat_tiles(tiles: list[tuple[str, str, str]]) -> None:
    """tiles = [(value, label, sublabel), ...] -> a monochrome KPI row."""
    cells = "".join(
        f'<div class="sd-tile"><div class="v">{v}</div>'
        f'<div class="l">{l}</div><div class="s">{s}</div></div>' for v, l, s in tiles)
    st.markdown(f'<div class="sd-tiles">{cells}</div>', unsafe_allow_html=True)


def caveat(mode: str, text: str) -> None:
    P = palette(mode)
    st.markdown(
        f'<div style="border:1px solid {P["border"]};border-left:3px solid {P["muted"]};'
        f'border-radius:8px;padding:10px 14px;margin:2px 0 16px;background:{P["panel"]};'
        f'color:{P["muted"]};font-size:.8rem;line-height:1.5;">'
        f'<span style="color:{P["strong"]};font-weight:600;letter-spacing:.04em;">'
        f'MODEL PREDICTION</span> &nbsp;{text}</div>', unsafe_allow_html=True)


def basket_summary(mode: str, longs: list[str], shorts: list[str]) -> None:
    """Compact LONG (top-10) / SHORT (bottom-10) ticker strip; green/red = data semantics."""
    P = palette(mode)

    def chips(tickers, color):
        return " ".join(
            f'<span style="font-family:IBM Plex Mono,monospace;font-size:.78rem;'
            f'font-weight:600;color:{color};border:1px solid {color}44;border-radius:6px;'
            f'padding:2px 7px;margin:2px 3px 2px 0;display:inline-block;">{t}</span>'
            for t in tickers)

    def side(label, tickers, color):
        return (
            f'<div style="flex:1;min-width:280px;border:1px solid {P["border"]};'
            f'border-radius:10px;padding:12px 14px;background:{P["card"]};">'
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">'
            f'<span style="width:9px;height:9px;border-radius:2px;background:{color};'
            f'display:inline-block;"></span>'
            f'<span style="font-size:.66rem;letter-spacing:.18em;text-transform:uppercase;'
            f'font-weight:700;color:{P["strong"]};">{label}</span>'
            f'<span style="color:{P["faint"]};font-size:.66rem;letter-spacing:.1em;">'
            f'{len(tickers)} NAMES</span></div>{chips(tickers, color)}</div>')

    st.markdown(
        f'<div style="display:flex;gap:14px;flex-wrap:wrap;margin-bottom:16px;">'
        f'{side("Long · Top 10", longs, P["up"])}'
        f'{side("Short · Bottom 10", shorts, P["down"])}</div>',
        unsafe_allow_html=True)
