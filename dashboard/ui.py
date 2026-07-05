"""
ui.py — visual identity for the Signal Desk dashboard (TradingView-like, near-monochrome).

Chrome is strictly greyscale in BOTH light and dark themes; green/red are RESERVED for
performance/data (up/down) and never used for chrome. One neutral selection treatment
(elevated surface + a strong-grey left bar) — no colored accent. Sector badge dots are the
only categorical color, and they encode data (sector), not decoration.

Two full palettes (light/dark) are injected as literal hex per run — the theme toggle just
flips st.session_state['mode'] and Streamlit re-runs, so no runtime CSS-variable juggling.
"""
from __future__ import annotations

import re

import streamlit as st

# ------------------------------------------------------------------ palettes ---------- #
DARK = dict(
    bg="#131722", panel="#181c26", card="#1e222d", border="#2a2e39", border_soft="#21252f",
    text="#c7ccd6", strong="#eceff4", muted="#868b93", faint="#565a63",
    sel_bg="#252a36", sel_bar="#eceff4", hover="#1e222d", input_bg="#1b1f29",
    up="#26a69a", down="#ef5350",
)
LIGHT = dict(
    bg="#ffffff", panel="#f7f8fa", card="#ffffff", border="#e0e3eb", border_soft="#eef0f4",
    text="#3c4149", strong="#131722", muted="#787b86", faint="#b2b5be",
    sel_bg="#eef1f6", sel_bar="#131722", hover="#f4f6f9", input_bg="#ffffff",
    up="#089981", down="#f23645",
)


def palette(mode: str) -> dict:
    return LIGHT if mode == "light" else DARK


# 9 sectors -> distinct hues for the badge dot (the only categorical color; encodes data) - #
SECTOR_COLORS = {
    "Technology": "#2b8fb3", "Banks": "#4b7bec", "Healthcare": "#9b8cff",
    "Consumer Discretionary": "#e0913a", "Consumer Staples": "#3aa66f",
    "Communication": "#c85c9c", "Energy, Materials & Utilities": "#d9773a",
    "Financial Services": "#6d7ee0", "Industrials": "#8a94a6",
}
SECTOR_FALLBACK = "#8a94a6"


def sector_color(sector: str) -> str:
    return SECTOR_COLORS.get(sector, SECTOR_FALLBACK)


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
            rules.append(f"{sel}{{background:#fff url({logo_uris[t]}) center/74% no-repeat;"
                         f"border-color:{P['border_soft']};}}")
        else:
            rules.append(f"{sel}{{background:{sector_color(s)};}}")
    dot_rules = "\n".join(rules)
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

    html, body, .stApp, [class*="css"] {{
      font-family:'Inter',-apple-system,Segoe UI,Roboto,sans-serif; color:{P['text']};
    }}
    .stApp {{ background:{P['bg']}; }}
    #MainMenu, header[data-testid="stHeader"], footer {{ visibility:hidden; height:0; }}
    .block-container {{ padding:0 2.2rem 3rem; max-width:1680px; }}
    .mono, code {{ font-family:'IBM Plex Mono',ui-monospace,monospace; }}
    hr {{ border-color:{P['border_soft']}; }}

    /* ---------------- slim top bar ---------------- */
    .st-key-topbar {{
      border-bottom:1px solid {P['border']}; padding:10px 4px 8px; margin-bottom:14px;
      position:sticky; top:0; z-index:50; background:{P['bg']};
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
      border-color:{P['muted']} !important; }}
    [data-baseweb="popover"], [data-baseweb="menu"], [role="listbox"] {{
      background:{P['card']} !important; border:1px solid {P['border']} !important; }}
    [role="option"] {{ color:{P['text']} !important; }}
    [role="option"]:hover {{ background:{P['hover']} !important; }}

    /* ---------------- top nav (segmented) — monochrome ---------------- */
    div[data-testid="stSegmentedControl"] [role="radiogroup"] {{ gap:2px; background:transparent; border:none; }}
    div[data-testid="stSegmentedControl"] button {{
      font-family:'Inter',sans-serif; font-weight:500; font-size:.84rem; letter-spacing:.01em;
      color:{P['muted']} !important; background:transparent !important; border:none !important;
      border-radius:7px !important; padding:6px 14px !important;
    }}
    div[data-testid="stSegmentedControl"] button:hover {{ color:{P['strong']} !important;
      background:{P['hover']} !important; }}
    div[data-testid="stSegmentedControl"] button[aria-checked="true"],
    div[data-testid="stSegmentedControl"] button[kind="segmented_controlActive"] {{
      color:{P['strong']} !important; background:{P['sel_bg']} !important; font-weight:600; }}

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
    .st-key-colist {{ max-height:calc(100vh - 210px); overflow-y:auto; overflow-x:hidden; padding-right:5px; }}
    .st-key-colist::-webkit-scrollbar {{ width:7px; }}
    .st-key-colist::-webkit-scrollbar-thumb {{ background:{P['border']}; border-radius:4px; }}

    .st-key-colist [data-testid="stButton"] button {{
      display:flex; align-items:center; gap:11px; width:100%; text-align:left; min-height:0;
      background:transparent; border:1px solid transparent; border-left:2px solid transparent;
      border-radius:8px; padding:7px 10px; margin:2px 0; color:{P['text']};
      font-family:'IBM Plex Mono',monospace; font-weight:500; font-size:.86rem; letter-spacing:.02em;
      transition:background .1s ease;
    }}
    .st-key-colist [data-testid="stButton"] button::before {{
      content:""; flex:0 0 auto; width:30px; height:30px; border-radius:7px;
      background:{P['faint']}; border:1px solid transparent; }}
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

    /* KPI stat tiles */
    .sd-tiles {{ display:flex; gap:12px; flex-wrap:wrap; margin:4px 0 6px; }}
    .sd-tile {{ flex:1; min-width:150px; border:1px solid {P['border']}; border-radius:11px;
      padding:14px 16px; background:{P['card']}; }}
    .sd-tile .v {{ font-family:'IBM Plex Mono',monospace; font-size:1.45rem; font-weight:600;
      color:{P['strong']}; line-height:1.1; }}
    .sd-tile .l {{ font-size:.66rem; letter-spacing:.1em; text-transform:uppercase; color:{P['muted']};
      margin-top:6px; }}
    .sd-tile .s {{ font-size:.72rem; color:{P['faint']}; margin-top:3px; }}

    /* matplotlib figures: sit on an intentional light card in either theme */
    [data-testid="stImage"] img {{ background:#fff; border:1px solid {P['border']};
      border-radius:10px; padding:8px; max-width:100%; }}
    </style>
    """, unsafe_allow_html=True)


def logo_html() -> str:
    return ('<div class="sd-logo"><span class="mark">SD</span>'
            '<span class="wm">SIGNAL<span class="dim">·</span>DESK</span></div>')


def hero_badge(ticker: str, sector: str, logo_uri: str | None) -> str:
    """Detail-hero badge: real logo on a white tile if available, else a sector-colored
    tile with the ticker's leading characters (graceful, never a broken image)."""
    if logo_uri:
        return (f'<div class="tkb" style="background:#fff url({logo_uri}) center/68% no-repeat;'
                f'border:1px solid rgba(0,0,0,.14)"></div>')
    return (f'<div class="tkb" style="background:{sector_color(sector)}">'
            f'{ticker.split(".")[0][:4]}</div>')


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
