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


def ohlc_price_line(df: pd.DataFrame, mode: str, height: int = 300,
                    date_title: str = "Date") -> alt.Chart:
    """Close-price line with a hover crosshair and an OHLC tooltip.

    Deliberate choices:
      * ONE series (close), so no legend — the section title names it. Open/high/low live in
        the tooltip rather than as extra marks: this is a price OVERVIEW, not a candlestick.
      * The line is neutral `strong`, not green/red. A price LEVEL has no polarity; the
        direction is stated once, in the period-change badge, where green/red is earned.
      * Crosshair = a vertical rule at the hovered date + a horizontal rule at that close,
        both recessive dashed, BOTH behind `transform_filter(hover)` so each draws exactly ONE
        mark. Using `opacity=alt.condition(hover, …)` instead — the obvious idiom — renders a
        rule for EVERY datum and merely hides them: 1,644 invisible SVG nodes that still get
        hit-tested on every mousemove. That, plus a per-datum invisible `selectors` rule layer,
        produced 4,971 SVG elements and made hovering visibly laggy.
      * The hit target is `mark_point(opacity=0)` — one lightweight symbol per datum, which
        `nearest` needs. Caller should pass a DOWNSAMPLED (weekly) frame so this is a few
        hundred nodes, not a few thousand.
      * NO area fill. `mark_area` implicitly sets y2=0, which drags the scale's domain down to
        zero and overrides `zero=False` — the price line then reads as a flat band in the top
        half of the plot. A truncated baseline is correct for a LINE (it encodes position);
        it is only an anti-pattern for BARS, which encode length.
    df: [date, open, high, low, close]."""
    P = ui.palette(mode)
    hover = alt.selection_point(fields=["date"], nearest=True, on="mouseover",
                                empty=False, clear="mouseout")

    base = alt.Chart(df).encode(
        x=alt.X("date:T", title=None, axis=alt.Axis(format="%Y", tickCount="year")),
        y=alt.Y("close:Q", title="price (own listing currency)",
                scale=alt.Scale(zero=False, nice=True)))

    line = base.mark_line(color=P["strong"], strokeWidth=1.6)

    # nearest-point hit target + tooltip: N invisible symbols (cheapest per-datum mark)
    selectors = base.mark_point(size=90, opacity=0).encode(
        tooltip=[alt.Tooltip("date:T", title=date_title, format="%d %b %Y"),
                 alt.Tooltip("close:Q", title="Close", format=",.2f"),
                 alt.Tooltip("open:Q", title="Open", format=",.2f"),
                 alt.Tooltip("high:Q", title="High", format=",.2f"),
                 alt.Tooltip("low:Q", title="Low", format=",.2f")],
    ).add_params(hover)

    # each of these renders ONE mark, only while hovering.
    # vrule is built from a bare Chart (x only, no y) so it spans the full plot height.
    vrule = (alt.Chart(df).transform_filter(hover)
             .mark_rule(color=P["muted"], strokeDash=[3, 3], size=1, opacity=.85)
             .encode(x=alt.X("date:T", title=None)))
    hrule = base.transform_filter(hover).mark_rule(
        color=P["muted"], strokeDash=[3, 3], size=1).encode(y="close:Q")
    point = base.transform_filter(hover).mark_point(
        size=60, filled=True, color=P["accent"], stroke=P["bg"], strokeWidth=1.5)

    return _themed(
        alt.layer(line, hrule, vrule, point, selectors).properties(height=height), P)


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


def train_val_dumbbell(df: pd.DataFrame, mode: str, height: int = 230) -> alt.Chart:
    """Bias-variance in one read: a rule from TRAIN rho to VALIDATION rho per model.

    A long bar = the model memorised the training rows and generalised at zero (variance);
    a dot-on-dot at zero = it regularised to the mean predictor (bias). Both land on the same
    validation point. Two series -> legend + direct labels (identity never colour-alone).
    df: [model, train_spearman, val_spearman], pre-sorted."""
    P = ui.palette(mode)
    order = df["model"].tolist()
    # labelOverlap=False: with 6 models in ~230px Vega silently drops every other label
    enc_y = alt.Y("model:N", sort=order, title=None,
                  axis=alt.Axis(labelFont="IBM Plex Mono", labelLimit=160, labelOverlap=False))
    base = alt.Chart(df)

    connector = base.mark_rule(color=P["faint"], size=2, opacity=.55).encode(
        y=enc_y, x="train_spearman:Q", x2="val_spearman:Q")

    long = df.melt(id_vars="model", value_vars=["train_spearman", "val_spearman"],
                   var_name="Split", value_name="rho")
    long["Split"] = long["Split"].map({"train_spearman": "Train", "val_spearman": "Validation"})
    cmap = {"Train": P["faint"], "Validation": P["accent"]}
    pts = alt.Chart(long).mark_point(size=110, filled=True, opacity=1,
                                     stroke=P["bg"], strokeWidth=2).encode(
        y=alt.Y("model:N", sort=order, title=None),
        x=alt.X("rho:Q", title="Spearman rank correlation",
                scale=alt.Scale(domain=[-0.15, 1.0], nice=False)),
        color=alt.Color("Split:N",
                        scale=alt.Scale(domain=list(cmap), range=list(cmap.values())),
                        legend=alt.Legend(orient="top", title=None, labelColor=P["text"])),
        tooltip=[alt.Tooltip("model:N", title=""), alt.Tooltip("Split:N", title=""),
                 alt.Tooltip("rho:Q", format="+.3f", title="Spearman")],
    )
    zero = (alt.Chart(pd.DataFrame({"z": [0]}))
            .mark_rule(color=P["strong"], size=1.5).encode(x="z:Q"))
    return _themed(alt.layer(zero, connector, pts).properties(height=height), P)


def learning_curve(df: pd.DataFrame, mode: str, ref: float, height: int = 240) -> alt.Chart:
    """Train vs validation RMSE against an expanding chronological training prefix.

    The dashed rule is the target's own std — a mean-predictor's RMSE. Validation sitting
    flat on that rule as data grows is the evidence that VARIANCE is not the binding
    constraint. One y-axis only (both series are RMSE in the same units)."""
    P = ui.palette(mode)
    long = df.melt(id_vars="n_train", value_vars=["train_rmse", "val_rmse"],
                   var_name="Split", value_name="rmse")
    long["Split"] = long["Split"].map({"train_rmse": "Train", "val_rmse": "Validation"})
    cmap = {"Train": P["faint"], "Validation": P["accent"]}
    # tick only at the 8 real prefix sizes — a quantitative axis otherwise invents ~35 ticks
    ticks = sorted(df["n_train"].unique().tolist())
    line = alt.Chart(long).mark_line(
        strokeWidth=2, point=alt.OverlayMarkDef(size=44, filled=True)).encode(
        x=alt.X("n_train:Q", title="training rows (expanding chronological prefix)",
                scale=alt.Scale(nice=False, zero=False, padding=14),
                axis=alt.Axis(values=ticks, labelOverlap=False)),
        y=alt.Y("rmse:Q", title="RMSE", scale=alt.Scale(zero=False, nice=True)),
        color=alt.Color("Split:N",
                        scale=alt.Scale(domain=list(cmap), range=list(cmap.values())),
                        legend=alt.Legend(orient="top", title=None, labelColor=P["text"])),
        tooltip=[alt.Tooltip("Split:N", title=""), alt.Tooltip("n_train:Q", title="rows"),
                 alt.Tooltip("rmse:Q", format=".3f", title="RMSE")],
    )
    # the reference is a NEUTRAL baseline, not a bad-status line: red/green are reserved for
    # performance semantics, and colouring "you're no better than the mean" red would imply
    # a status this chart is not encoding.
    rule = (alt.Chart(pd.DataFrame({"y": [ref]}))
            .mark_rule(color=P["muted"], strokeDash=[5, 4], size=1.4).encode(y="y:Q"))
    label = (alt.Chart(pd.DataFrame({"y": [ref], "t": ["mean-predictor RMSE (target std)"]}))
             .mark_text(align="left", dx=6, dy=-7, color=P["muted"], fontSize=10, font="Inter")
             .encode(y="y:Q", text="t:N"))
    return _themed(alt.layer(rule, label, line).properties(height=height), P)


def auc_bars(df: pd.DataFrame, mode: str, height: int = 210) -> alt.Chart:
    """Classification AUC per model, drawn as the DEVIATION FROM CHANCE (auc - 0.5).

    Two deliberate choices:
      * Bars measure `auc - 0.5`, not `auc`, off a zero baseline that IS chance. Drawing raw
        AUC bars from 0 on a truncated [0.40,0.60] axis would exaggerate differences between
        models that are all indistinguishable from chance — a truncated-bar-axis lie. Here
        bar length is literally "how far from chance", and a near-zero bar reads as such.
      * Neutral fill: these hug chance, and colouring noise green/red would dramatise a
        result that is not there.
    Direct labels carry the true AUC, so no information is lost by plotting the deviation.
    df: [model, auc], pre-sorted."""
    P = ui.palette(mode)
    d = df.copy()
    d["dev"] = d["auc"] - 0.5
    order = d["model"].tolist()
    span = max(0.08, float(d["dev"].abs().max()) * 1.45)
    base = alt.Chart(d)
    enc_y = alt.Y("model:N", sort=order, title=None,
                  axis=alt.Axis(labelFont="IBM Plex Mono", labelLimit=180, labelOverlap=False))

    bars = base.mark_bar(size=15, color=P["faint"], cornerRadius=3).encode(
        y=enc_y,
        x=alt.X("dev:Q", title="AUC − 0.5   (0 = chance)",
                scale=alt.Scale(domain=[-span, span], nice=False),
                axis=alt.Axis(format="+.3f")),
        tooltip=[alt.Tooltip("model:N", title=""),
                 alt.Tooltip("auc:Q", format=".3f", title="AUC"),
                 alt.Tooltip("dev:Q", format="+.3f", title="vs chance")])
    # label the TRUE auc, flipped to whichever side the bar points. `align`/`dx` are mark
    # properties (not encoding channels) in this Altair, so use two filtered layers.
    def _lab(pos: bool):
        return (base.transform_filter(
                    alt.datum.dev >= 0 if pos else alt.datum.dev < 0)
                .mark_text(align="left" if pos else "right", dx=5 if pos else -5,
                           color=P["text"], fontSize=10, font="IBM Plex Mono")
                .encode(y=enc_y, x="dev:Q", text=alt.Text("auc:Q", format=".3f")))

    chance = (alt.Chart(pd.DataFrame({"z": [0]}))
              .mark_rule(color=P["strong"], size=1.6).encode(x="z:Q"))
    return _themed(
        alt.layer(bars, _lab(True), _lab(False), chance).properties(height=height), P)


def importance_bar(df: pd.DataFrame, cat: str, val: str, mode: str, *, x_title: str,
                   height: int = 300) -> alt.Chart:
    """Horizontal importance bars, neutral fill (importance is magnitude, not polarity)."""
    P = ui.palette(mode)
    order = df[cat].tolist()
    base = alt.Chart(df)
    enc_y = alt.Y(f"{cat}:N", sort=order, title=None,
                  axis=alt.Axis(labelFont="IBM Plex Mono", labelLimit=240))
    bars = base.mark_bar(size=12, color=P["accent"], cornerRadius=3, opacity=.85).encode(
        y=enc_y, x=alt.X(f"{val}:Q", title=x_title, scale=alt.Scale(nice=True)),
        tooltip=[alt.Tooltip(f"{cat}:N", title=""), alt.Tooltip(f"{val}:Q", format=".4f")])
    return _themed(bars.properties(height=height), P)


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
