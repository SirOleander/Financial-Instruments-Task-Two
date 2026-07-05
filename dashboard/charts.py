"""
charts.py — small, theme-aware Altair charts for the dashboard.

Design per the dataviz method: the metrics here are signed rank-correlations that all hug
zero, so their JOB is "show they're indistinguishable from zero" — a diverging-around-a-
highlighted-zero-baseline bar, NEUTRAL fill (green/red is reserved for genuine long/short
performance, not for dramatising noise). Thin marks, recessive axes, hover tooltips, a
prominent zero rule. Everything is styled from the active palette (light/dark).
"""
from __future__ import annotations

import altair as alt
import pandas as pd

import ui


def _themed(chart: alt.Chart, P: dict) -> alt.Chart:
    return (chart
            .configure(background="transparent")
            .configure_view(stroke=None)
            .configure_axis(labelColor=P["muted"], titleColor=P["muted"],
                            gridColor=P["border_soft"], domainColor=P["border"],
                            tickColor=P["border"], labelFontSize=11, titleFontSize=11,
                            labelFont="Inter", titleFont="Inter")
            .configure_axisY(grid=False))


def signed_bar(df: pd.DataFrame, cat: str, val: str, mode: str, *, x_title: str,
               domain: tuple[float, float], height: int = 220, err: bool = False,
               fmt: str = ".3f") -> alt.Chart:
    """Horizontal bars off a highlighted zero baseline. Rows are drawn in the order given
    (pre-sort the df). Optional symmetric error whiskers from {val}_lo..{val}_hi."""
    P = ui.palette(mode)
    order = df[cat].tolist()
    base = alt.Chart(df)
    enc_y = alt.Y(f"{cat}:N", sort=order, title=None,
                  axis=alt.Axis(labelLimit=260, labelFont="IBM Plex Mono"))

    bars = base.mark_bar(size=13, color=P["faint"], cornerRadius=3).encode(
        y=enc_y,
        x=alt.X(f"{val}:Q", title=x_title,
                scale=alt.Scale(domain=list(domain), nice=False)),
        tooltip=[alt.Tooltip(f"{cat}:N", title=""),
                 alt.Tooltip(f"{val}:Q", title=x_title, format=fmt)],
    )
    layers = [bars]
    if err:
        layers.append(base.mark_rule(color=P["muted"], size=1.5, opacity=.8).encode(
            y=enc_y, x=f"{val}_lo:Q", x2=f"{val}_hi:Q"))
    zero = (alt.Chart(pd.DataFrame({"z": [0]}))
            .mark_rule(color=P["strong"], size=1.5).encode(x="z:Q"))
    layers.append(zero)
    return _themed(alt.layer(*layers).properties(height=height), P)


def price_line(df: pd.DataFrame, mode: str, height: int = 250) -> alt.Chart:
    """Adjusted-close history. Neutral strong line + faint area (a price level, not
    up/down performance — so no green/red)."""
    P = ui.palette(mode)
    base = alt.Chart(df).encode(
        x=alt.X("date:T", title=None, axis=alt.Axis(format="%Y")),
        y=alt.Y("adjusted_close:Q", title="adj. close", scale=alt.Scale(zero=False, nice=True)))
    area = base.mark_area(opacity=.10, color=P["muted"])
    line = base.mark_line(color=P["strong"], strokeWidth=1.6).encode(
        tooltip=[alt.Tooltip("date:T", title=""),
                 alt.Tooltip("adjusted_close:Q", title="adj. close", format=",.2f")])
    return _themed(alt.layer(area, line).properties(height=height), P)


def profile_bars(df: pd.DataFrame, cat: str, val: str, mode: str, height: int = 210) -> alt.Chart:
    """Horizontal [0,1] percentile bars with a 0.5 median reference and end labels."""
    P = ui.palette(mode)
    order = df[cat].tolist()
    base = alt.Chart(df)
    enc_y = alt.Y(f"{cat}:N", sort=order, title=None,
                  axis=alt.Axis(labelFont="IBM Plex Mono", labelLimit=180))
    bars = base.mark_bar(size=16, color=P["muted"], cornerRadius=3).encode(
        y=enc_y, x=alt.X(f"{val}:Q", title="sector percentile (0–1)",
                         scale=alt.Scale(domain=[0, 1], nice=False)),
        tooltip=[alt.Tooltip(f"{cat}:N", title=""), alt.Tooltip(f"{val}:Q", format=".2f")])
    labels = base.mark_text(align="left", dx=4, color=P["text"], fontSize=10,
                            font="IBM Plex Mono").encode(
        y=enc_y, x=f"{val}:Q", text=alt.Text(f"{val}:Q", format=".2f"))
    mid = (alt.Chart(pd.DataFrame({"m": [0.5]}))
           .mark_rule(color=P["faint"], strokeDash=[3, 3], size=1).encode(x="m:Q"))
    return _themed(alt.layer(mid, bars, labels).properties(height=height), P)


def time_line(df: pd.DataFrame, xcol: str, ycol: str, mode: str, *, y_title: str,
              y_domain=None, ref: float | None = None, height: int = 210) -> alt.Chart:
    """Generic dated line for a single [0,1]-ish score over a company's reports."""
    P = ui.palette(mode)
    yscale = alt.Scale(domain=list(y_domain)) if y_domain else alt.Scale(zero=False, nice=True)
    line = alt.Chart(df).mark_line(
        color=P["strong"], strokeWidth=2, point=alt.OverlayMarkDef(size=34, filled=True)).encode(
        x=alt.X(f"{xcol}:T", title=None, axis=alt.Axis(format="%b %Y")),
        y=alt.Y(f"{ycol}:Q", title=y_title, scale=yscale),
        tooltip=[alt.Tooltip(f"{xcol}:T", title=""), alt.Tooltip(f"{ycol}:Q", format=".3f")])
    layers = [line]
    if ref is not None:
        layers.insert(0, alt.Chart(pd.DataFrame({"r": [ref]}))
                      .mark_rule(color=P["faint"], strokeDash=[3, 3], size=1).encode(y="r:Q"))
    return _themed(alt.layer(*layers).properties(height=height), P)


def equity_lines(df: pd.DataFrame, mode: str, order: list[str],
                 color_map: dict[str, str], height: int = 300) -> alt.Chart:
    """Multi-series 'growth of $1' line chart. df tidy: [Point, Series, Value]. A dashed
    rule at 1.0 marks break-even. Series colours are passed explicitly (green/red are
    legitimate here — this is real long/short performance)."""
    P = ui.palette(mode)
    base = alt.Chart(df)
    one = (alt.Chart(pd.DataFrame({"y": [1.0]}))
           .mark_rule(color=P["faint"], strokeDash=[4, 4], size=1).encode(y="y:Q"))
    line = base.mark_line(strokeWidth=2.5, point=alt.OverlayMarkDef(size=42, filled=True)).encode(
        x=alt.X("Point:N", sort=order, title=None,
                axis=alt.Axis(labelFont="IBM Plex Mono", labelAngle=0)),
        y=alt.Y("Value:Q", title="growth of $1", scale=alt.Scale(zero=False, nice=True)),
        color=alt.Color("Series:N",
                        scale=alt.Scale(domain=list(color_map), range=list(color_map.values())),
                        legend=alt.Legend(orient="top", title=None, labelColor=P["text"],
                                          symbolType="stroke")),
        tooltip=[alt.Tooltip("Series:N", title=""), alt.Tooltip("Point:N", title=""),
                 alt.Tooltip("Value:Q", format=".3f", title="growth of $1")],
    )
    return _themed(alt.layer(one, line).properties(height=height), P)
