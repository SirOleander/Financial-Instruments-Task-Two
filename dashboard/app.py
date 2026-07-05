"""
app.py — Signal Desk: report-signal equity-research dashboard (READ-ONLY).

STAGE 1.5 — skeleton + navigation, TradingView-like near-monochrome restyle. A slim
full-width top bar (logo far-left, integrated search, horizontal nav, light/dark toggle)
over a left ticker watchlist + a main content area with four view shells. No real tab
content yet. Reads data/financials.db (company universe) via cached loaders; writes nothing.

Run from the repo root:
    streamlit run dashboard/app.py
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

import data
import ui

ASSETS = Path(__file__).resolve().parent / "assets"
VIEWS = ["Ranking", "Model & EDA", "Backtest", "Company Detail"]


def top_bar() -> str:
    """Slim top bar: logo | search | nav | theme toggle. Returns the active view."""
    with st.container(key="topbar"):
        c_logo, c_search, c_nav, c_toggle = st.columns(
            [2.4, 3.2, 5.2, 0.7], vertical_alignment="center")
        with c_logo:
            logo = ASSETS / "logo.png"
            if logo.exists():
                st.image(str(logo), width=150)
            else:
                st.markdown(ui.logo_html(), unsafe_allow_html=True)
        with c_search:
            st.text_input("search", placeholder="Search ticker or company…",
                          label_visibility="collapsed", key="co_search")
        with c_nav:
            view = st.segmented_control("nav", VIEWS, key="view",
                                        label_visibility="collapsed")
        with c_toggle:
            icon = "☀" if st.session_state["mode"] == "dark" else "☾"
            if st.button(icon, key="themebtn", help="Toggle light / dark"):
                st.session_state["mode"] = "light" if st.session_state["mode"] == "dark" else "dark"
                st.rerun()
    return view or st.session_state["view"]


def watchlist(companies) -> None:
    """Left column: sector filter + the ticker-only company list (names on hover)."""
    with st.container(key="watchlist"):
        sectors = ["All sectors"] + sorted(companies["sector"].unique())
        st.selectbox("sector", sectors, label_visibility="collapsed", key="co_sector")

        df = companies
        pick = st.session_state.get("co_sector", "All sectors")
        if pick != "All sectors":
            df = df[df["sector"] == pick]
        q = (st.session_state.get("co_search") or "").strip().lower()
        if q:
            df = df[df["ticker"].str.lower().str.contains(q)
                    | df["name"].str.lower().str.contains(q)]

        st.markdown(f'<div class="sd-wl-label"><span>Watchlist</span>'
                    f'<span class="ct">{len(df)}</span></div>', unsafe_allow_html=True)

        with st.container(key="colist"):
            if df.empty:
                st.caption("No matches.")
            for _, r in df.iterrows():
                selected = st.session_state.get("selected") == r["ticker"]
                if st.button(r["ticker"], key=ui.safe_key(r["ticker"]),
                             help=f"{r['name']} · {r['sector']}",
                             use_container_width=True,
                             type="primary" if selected else "secondary"):
                    st.session_state["selected"] = r["ticker"]
                    # route via a pending flag: 'view' is a widget key and can't be set
                    # after the nav widget is instantiated this run — apply it before.
                    st.session_state["_pending_view"] = "Company Detail"
                    st.rerun()


def view_ranking(logos: dict) -> None:
    import pandas as pd
    mode = st.session_state["mode"]
    st.markdown('<div class="sd-view-title">Company Ranking</div>'
                '<div class="sd-view-sub">All 89 companies by model-predicted forward-63d '
                'Sharpe · long top-10 / short bottom-10.</div>', unsafe_allow_html=True)

    ui.caveat(mode, "shown for completeness. Out-of-sample signal is weak (near-zero rank "
                    "correlation) and the long/short backtest is flat — see the "
                    "<b>Model &amp; EDA</b> tab. Rankings are low-confidence, not investment "
                    "advice.")

    df = data.load_ranking()
    longs = df[df["basket"] == "LONG"]["ticker"].tolist()
    shorts = df[df["basket"] == "SHORT"]["ticker"].tolist()
    ui.basket_summary(mode, longs, shorts)

    # scannable, sortable table — logos via ImageColumn, green/red row tint per basket
    disp = pd.DataFrame({
        "Rank": df["rank_ensemble"],
        "Logo": [logos.get(t, "") for t in df["ticker"]],
        "Ticker": df["ticker"],
        "Company": df["name"],
        "Sector": df["sector"],
        "Pred. Sharpe": df["pred_ensemble"],
        "Basket": df["basket"],
        "Note": ["OOD · held out of training" if o else ""
                 for o in df["out_of_training_dist"]],
    })
    P = ui.palette(mode)

    def _tint(row):
        c = (f"rgba(38,166,154,.15)" if row["Basket"] == "LONG"
             else f"rgba(239,83,80,.15)" if row["Basket"] == "SHORT" else "")
        return [f"background-color:{c}"] * len(row)

    styler = disp.style.apply(_tint, axis=1).format({"Pred. Sharpe": "{:+.2f}"})

    ev = st.dataframe(
        styler, hide_index=True, width="stretch", height=560,
        on_select="rerun", selection_mode="single-row",
        column_config={
            "Rank": st.column_config.NumberColumn(width="small"),
            "Logo": st.column_config.ImageColumn("", width="small"),
            "Ticker": st.column_config.TextColumn(width="small"),
            "Company": st.column_config.TextColumn(width="large"),
            "Sector": st.column_config.TextColumn(width="medium"),
            "Pred. Sharpe": st.column_config.NumberColumn(
                "Pred. Sharpe", width="small",
                help="Ensemble-predicted forward 63-day Sharpe (SVR+RF+XGB)."),
            "Basket": st.column_config.TextColumn(width="small"),
            "Note": st.column_config.TextColumn("Note", width="medium"),
        },
    )
    if ev.selection.rows:
        tk = df.iloc[ev.selection.rows[0]]["ticker"]
        if tk != st.session_state.get("_rank_last"):
            st.session_state["_rank_last"] = tk
            st.session_state["selected"] = tk
            st.session_state["_pending_view"] = "Company Detail"
            st.rerun()
    st.caption("Click a row to open its Company Detail. Click a column header to sort.")


def view_model() -> None:
    import pandas as pd
    import charts
    mode = st.session_state["mode"]
    st.markdown('<div class="sd-view-title">Model &amp; EDA</div>'
                '<div class="sd-view-sub">Leak-safe model performance and feature '
                'diagnostics — reported straight.</div>', unsafe_allow_html=True)

    cv = data.load_cv()
    tm = data.load_test_metrics()
    ft = data.load_feature_target()
    ens = tm[tm["model"].str.startswith("ENSEMBLE")].iloc[0]
    best_cv = cv.loc[cv["cv_spearman_mean"].idxmax()]
    ft_rel = ft[ft["reliable"] == True]
    max_ft = ft_rel["spearman"].abs().max()

    ui.note("<b>Verdict:</b> report fundamentals carry <b>no reliable signal</b> for the "
            "forward 63-day Sharpe on this universe/period — the honest result, consistent "
            "with market efficiency. Every metric below is indistinguishable from zero. The "
            "value of this project is the leak-free methodology, not alpha.")

    ui.stat_tiles([
        (f"{max_ft:.3f}", "Max feature |Spearman|", "strongest single feature vs target"),
        (f"{best_cv['cv_spearman_mean']:+.3f}", "Best CV Spearman",
         f"{best_cv['model']} · ±{best_cv['cv_spearman_std']:.3f} across folds"),
        (f"{ens['test_spearman_pooled']:+.3f}", "Ensemble test Spearman", "held-out 12-month test"),
        (f"{ens['test_rmse']:.2f}", "Ensemble test RMSE", "future_63d_sharpe units"),
    ])

    # ---- model performance ----
    ui.section("Model performance · CV selection + one-shot test")
    perf = cv.merge(tm[["model", "test_spearman_pooled", "test_rmse"]], on="model", how="left")
    perf = perf.sort_values("cv_spearman_mean", ascending=False)
    table = pd.DataFrame({
        "Model": perf["model"],
        "CV Spearman": [f"{m:+.3f} ± {s:.3f}" for m, s in
                        zip(perf["cv_spearman_mean"], perf["cv_spearman_std"])],
        "Test Spearman": perf["test_spearman_pooled"].map(lambda v: f"{v:+.3f}"),
        "Test RMSE": perf["test_rmse"].map(lambda v: f"{v:.2f}"),
        "Note": ["null / constant model" if d else "" for d in perf["degenerate_constant"]],
    })
    st.dataframe(table, hide_index=True, width="stretch")

    c1, c2 = st.columns([1, 1], gap="large")
    with c1:
        cvp = cv.sort_values("cv_spearman_mean").copy()
        cvp["cv_spearman_mean_lo"] = cvp["cv_spearman_mean"] - cvp["cv_spearman_std"]
        cvp["cv_spearman_mean_hi"] = cvp["cv_spearman_mean"] + cvp["cv_spearman_std"]
        st.markdown('<div class="sd-note"><b>CV Spearman per model</b> (bars) with ±1 std '
                    'whiskers. Every whisker straddles zero — no model beats chance.</div>',
                    unsafe_allow_html=True)
        st.altair_chart(charts.signed_bar(
            cvp, "model", "cv_spearman_mean", mode, x_title="CV rank correlation",
            domain=(-0.16, 0.16), height=230, err=True), width="stretch")
    with c2:
        top = ft_rel.reindex(ft_rel["spearman"].abs().sort_values(ascending=False).index).head(10)
        st.markdown('<div class="sd-note"><b>Feature → target rank correlation</b> '
                    '(well-populated features). The strongest is ~0.075 — essentially '
                    'nothing.</div>', unsafe_allow_html=True)
        st.altair_chart(charts.signed_bar(
            top, "feature", "spearman", mode, x_title="Spearman vs future_63d_sharpe",
            domain=(-0.1, 0.1), height=230), width="stretch")

    # ---- ablation ----
    ui.section("Robustness · feature-set ablation")
    ui.note("Re-running the whole roster on <b>sub-scores only</b> vs <b>KPIs only</b> vs "
            "<b>full</b> — the null does not move. Max |CV Spearman| across all 18 cells = "
            "<b>0.041</b>.")
    abl = data.load_ablation().pivot_table(index="model", columns="feature_set",
                                           values="cv_spearman").round(4)
    abl = abl[["subscores_only", "kpis_only", "full"]].reset_index()
    st.dataframe(abl, hide_index=True, width="stretch")

    # ---- EDA figures ----
    ui.section("Exploratory data analysis")
    ui.note("Full diagnostics (train-eligible rows only). Figures open on demand.")
    figs = [
        ("Feature → target correlation (all features)", "fig_target_corr_bar.png"),
        ("Feature distributions · scores", "fig_dist_scores.png"),
        ("Feature distributions · KPIs (winsor caps marked)", "fig_dist_kpis.png"),
        ("Raw vs winsorized ratio-tails", "fig_dist_winsor_rawvswins.png"),
        ("Target distribution", "fig_dist_target.png"),
        ("Feature–feature correlation heatmap", "fig_corr_heatmap.png"),
        ("Missingness (US vs international)", "fig_missingness.png"),
        ("Forward Sharpe by sector (in-sample)", "fig_target_by_sector.png"),
    ]
    for label, fname in figs:
        with st.expander(label):
            st.image(data.eda_fig(fname), width="stretch")

    with st.expander("Multicollinearity (VIF) — by-construction identities"):
        vif = data.load_vif()
        vshow = vif[vif["flag"] != ""][["block", "feature", "VIF", "flag"]].copy()
        vshow["VIF"] = vshow["VIF"].map(lambda v: "∞" if v > 1e6 else f"{v:.1f}")
        st.dataframe(vshow, hide_index=True, width="stretch")
        ui.note("Five exact identities (VIF = ∞) plus high-VIF redundancies drove the "
                "de-duplicated feature set — see CLAUDE.md.")


def view_backtest(logos: dict) -> None:
    import pandas as pd
    import charts
    mode = st.session_state["mode"]
    P = ui.palette(mode)
    st.markdown('<div class="sd-view-title">Backtest</div>'
                '<div class="sd-view-sub">Walk-forward top-10 long / bottom-10 short over the '
                'held-out test year.</div>', unsafe_allow_html=True)

    ui.note("<b>A test of the pipeline, not a claim of alpha.</b> The ensemble is frozen on "
            "pre-test data and applied forward to each quarterly rebalance. Equal-weight "
            "top-10 long / bottom-10 short, ~63-day hold, risk-free = 0. With only 4 "
            "rebalances the statistics are high-variance — read direction, not precision.")

    per = data.load_backtest_periods()
    summ = data.load_backtest_summary()

    # transaction-cost control -> drives tiles + the long-short curve
    cost_lbl = st.segmented_control("Transaction cost (one-way)", ["0 bps", "5 bps", "10 bps"],
                                    default="10 bps", key="bt_cost")
    cost = int((cost_lbl or "10 bps").split()[0])
    srow = summ[summ["cost_bps_oneway"] == cost].iloc[0]

    def pct(x):
        return f"{x:+.1%}"

    ui.stat_tiles([
        (pct(srow["cum_return_LS"]), "Cumulative long-short", f"net of {cost} bps · test year"),
        (f"{srow['ann_sharpe_LS']:+.2f}", "Annualized Sharpe", "of quarterly LS returns"),
        (pct(srow["max_drawdown_LS"]), "Max drawdown", "long-short equity"),
        (f"{int(srow['n_rebalances'])}", "Rebalances", "quarterly · ~63-day hold"),
    ])

    # ---- equity curve ----
    ui.section("Equity curve · growth of $1")
    net_ls = per["gross_ls"] - (cost / 1e4) * per["traded_notional_oneway"]
    pts = ["Start"] + per["period"].tolist()
    cl = cs = cx = 1.0
    long_eq, short_eq, ls_eq = [1.0], [1.0], [1.0]
    for i in range(len(per)):
        cl *= 1 + per["long_ret"].iloc[i]; long_eq.append(cl)
        cs *= 1 + per["short_ret"].iloc[i]; short_eq.append(cs)
        cx *= 1 + net_ls.iloc[i]; ls_eq.append(cx)
    tidy = pd.concat([
        pd.DataFrame({"Point": pts, "Series": "Long basket", "Value": long_eq}),
        pd.DataFrame({"Point": pts, "Series": "Short basket", "Value": short_eq}),
        pd.DataFrame({"Point": pts, "Series": "Long–Short (net)", "Value": ls_eq}),
    ])
    cmap = {"Long basket": P["up"], "Short basket": P["down"], "Long–Short (net)": P["strong"]}
    st.altair_chart(charts.equity_lines(tidy, mode, pts, cmap, height=300), width="stretch")
    ui.note(f"Both baskets rose with a strong market (long +{long_eq[-1]-1:.0%}, short basket "
            f"+{short_eq[-1]-1:.0%}); the long–short spread nets to {ls_eq[-1]-1:+.1%} — no "
            "edge. The short <i>basket</i> is shown as its own return; a short position "
            "profits when it falls.")

    # ---- per-rebalance table ----
    ui.section("Per-rebalance long-short")
    net_col = f"Net LS ({cost}bps)"
    pt = pd.DataFrame({
        "Period": per["period"],
        "Universe": per["n_universe"],
        "Long ret": per["long_ret"],
        "Short ret": per["short_ret"],
        "Gross LS": per["gross_ls"],
        net_col: net_ls,
        "Int'l L/S": [f"{a}/{b}" for a, b in zip(per["intl_in_long"], per["intl_in_short"])],
    })
    sty = (pt.style
           .format({c: "{:+.2%}" for c in ["Long ret", "Short ret", "Gross LS", net_col]})
           .map(lambda v: f"color:{P['up'] if v >= 0 else P['down']}",
                subset=["Gross LS", net_col]))
    st.dataframe(sty, hide_index=True, width="stretch")

    # ---- holdings explorer ----
    ui.section("Holdings · what the book actually held")
    hold = data.load_backtest_holdings()
    period_pick = st.selectbox("Rebalance", per["period"].tolist(), key="bt_period")
    cL, cR = st.columns(2, gap="large")
    for col, leg, color, label in [(cL, "long", P["up"], "LONG · top 10"),
                                   (cR, "short", P["down"], "SHORT · bottom 10")]:
        with col:
            st.markdown(f'<div style="font-size:.7rem;letter-spacing:.14em;font-weight:700;'
                        f'text-transform:uppercase;color:{color};margin-bottom:6px;">{label}</div>',
                        unsafe_allow_html=True)
            g = hold[(hold["period"] == period_pick) & (hold["leg"] == leg)].copy()
            show = pd.DataFrame({
                "Logo": [logos.get(t, "") for t in g["ticker"]],
                "Ticker": g["ticker"].values,
                "Sector": g["sector"].values,
                "Realized 63d": g["realized_63d_return"].values,
                "OOD": ["●" if o else "" for o in g["out_of_training_dist"]],
            })
            gsty = (show.style
                    .format({"Realized 63d": "{:+.1%}"})
                    .map(lambda v: f"color:{P['up'] if v >= 0 else P['down']}", subset=["Realized 63d"]))
            st.dataframe(gsty, hide_index=True, width="stretch", height=390,
                         column_config={
                             "Logo": st.column_config.ImageColumn("", width="small"),
                             "OOD": st.column_config.TextColumn("OOD", width="small",
                                    help="Out-of-training international (lower confidence)."),
                         })

    with st.expander("Reference figure (matplotlib equity curve)"):
        st.image(str(data.PRED_DIR / "fig_backtest_equity.png"), width="stretch")

    ui.note("<b>Honest read:</b> per-rebalance long-short flips sign (+15%, −5%, −21%, +13%) "
            "with no persistence; over 4 quarters the strategy adds no spread. Consistent "
            "with the near-null model and market efficiency — the backtest confirms the "
            "pipeline runs end-to-end and leak-free, nothing more.")


def view_detail(companies) -> None:
    st.markdown('<div class="sd-view-title">Company Detail</div>'
                '<div class="sd-view-sub">Per-company signals, scores and history.</div>',
                unsafe_allow_html=True)
    tk = st.session_state.get("selected")
    if not tk:
        st.markdown('<div class="sd-empty">Select a company from the watchlist to view its '
                    'detail.</div>', unsafe_allow_html=True)
        return
    import pandas as pd
    import charts
    mode = st.session_state["mode"]
    P = ui.palette(mode)
    r = companies[companies["ticker"] == tk].iloc[0]
    badge = ui.hero_badge(tk, r["sector"], data.logo_uris().get(tk))
    intl = ("<span class=\"sd-chip\">Int'l · out-of-training</span>" if r["is_intl"]
            else '<span class="sd-chip">US · train-eligible</span>')
    st.markdown(
        f'<div class="sd-hero">{badge}<div><div class="nm">{r["name"]}</div>'
        f'<div class="sub">{tk} &nbsp;·&nbsp; {r["sector"]} &nbsp;·&nbsp; '
        f'{r["company_group"]} {intl}</div></div></div>',
        unsafe_allow_html=True)

    rank = data.load_ranking()
    rr = rank[rank["ticker"] == tk].iloc[0]
    hist = data.company_history(tk)
    latest = hist.iloc[-1] if len(hist) else None

    basket = rr["basket"] or "—"
    bcol = P["up"] if basket == "LONG" else P["down"] if basket == "SHORT" else P["muted"]
    op = latest["operative_score"] if latest is not None else None
    ui.stat_tiles([
        (f"{rr['pred_ensemble']:+.2f}", "Predicted fwd-63d Sharpe", "ensemble · low-confidence"),
        (f"#{int(rr['rank_ensemble'])}", "Rank of 89",
         f"<span style='color:{bcol}'>{basket}</span>" if basket != "—" else "mid-book"),
        (f"{latest['financial_score']:.2f}" if latest is not None and pd.notna(latest['financial_score']) else "—",
         "Financial score", "sector percentile (latest)"),
        (f"{op:.2f}" if op is not None and pd.notna(op) else "N/A",
         "Operative score", "qualitative 1–5 → [0,1]"),
    ])

    # ---- price ----
    ui.section("Price · adjusted close")
    px = data.company_prices(tk)
    if len(px):
        st.altair_chart(charts.price_line(px, mode), width="stretch")
        ret = px["adjusted_close"].iloc[-1] / px["adjusted_close"].iloc[0] - 1
        ui.note(f"{px['date'].min():%b %Y} – {px['date'].max():%b %Y} · "
                f"total change <b>{ret:+.0%}</b> (own listing currency; price level, not a "
                "model input).")
    else:
        st.caption("No price history.")

    # ---- score profile + history ----
    ui.section("Signal profile")
    c1, c2 = st.columns([1, 1], gap="large")
    with c1:
        ui.note("<b>Sub-score profile</b> — latest report, percentile within sector peers "
                "(0.5 = median).")
        subs = ["profitability_score", "growth_score", "cash_flow_score",
                "leverage_score", "efficiency_score", "investment_score"]
        if latest is not None:
            prof = pd.DataFrame({
                "sub": [s.replace("_score", "").replace("_", " ") for s in subs],
                "val": [latest[s] for s in subs],
            }).dropna(subset=["val"])
            if len(prof):
                st.altair_chart(charts.profile_bars(prof, "sub", "val", mode), width="stretch")
            else:
                st.caption("Sub-scores not computable for the latest report.")
    with c2:
        ui.note("<b>Financial score over time</b> — the company's fundamental percentile "
                "trajectory across reports.")
        fs = hist[["rd", "financial_score"]].dropna()
        if len(fs) >= 2:
            st.altair_chart(charts.time_line(fs, "rd", "financial_score", mode,
                            y_title="financial score", y_domain=(0, 1), ref=0.5), width="stretch")
        else:
            st.caption("Not enough history.")

    # ---- fundamentals snapshot ----
    with st.expander("Latest fundamentals (KPI snapshot)"):
        if latest is not None:
            kpis = [("Gross margin", "gross_margin", "{:+.1%}"),
                    ("Operating margin", "operating_margin", "{:+.1%}"),
                    ("Return on assets", "return_on_assets", "{:+.1%}"),
                    ("Return on equity", "return_on_equity", "{:+.1%}"),
                    ("Revenue growth YoY", "revenue_growth_yoy", "{:+.1%}"),
                    ("Op. cash-flow margin", "operating_cash_flow_margin", "{:+.1%}"),
                    ("Debt / assets", "debt_to_assets", "{:.2f}"),
                    ("Equity ratio", "equity_ratio", "{:.2f}"),
                    ("ROIC", "ROIC", "{:+.1%}")]
            rows = [{"KPI": lbl, "Value": (fmt.format(latest[col])
                    if pd.notna(latest[col]) else "n/a")} for lbl, col, fmt in kpis]
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
            st.caption(f"As of the {latest['report_release_date']} report "
                       f"({latest['frequency']}).")

    ood = (" This is a held-out international (out-of-training) name — its prediction is "
           "especially low-confidence." if r["is_intl"] else "")
    ui.note("<b>Note:</b> the predicted Sharpe is the near-null model's output and should be "
            "read as low-confidence (see Model &amp; EDA)." + ood)


def main() -> None:
    st.set_page_config(page_title="Signal Desk · Equity Research", page_icon="◧",
                       layout="wide", initial_sidebar_state="collapsed")
    st.session_state.setdefault("mode", "dark")
    st.session_state.setdefault("view", "Ranking")
    st.session_state.setdefault("selected", None)
    # apply a pending view switch BEFORE the nav widget (key 'view') is instantiated
    if "_pending_view" in st.session_state:
        st.session_state["view"] = st.session_state.pop("_pending_view")

    companies = data.load_companies()
    logos = data.logo_uris()
    ui.inject_theme(companies, st.session_state["mode"], logos)

    view = top_bar()

    left, right = st.columns([1.15, 5.0], gap="medium")
    with left:
        watchlist(companies)
    with right:
        if view == "Ranking":
            view_ranking(logos)
        elif view == "Model & EDA":
            view_model()
        elif view == "Backtest":
            view_backtest(logos)
        else:
            view_detail(companies)


if __name__ == "__main__":
    main()
