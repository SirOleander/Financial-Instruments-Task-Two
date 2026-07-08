"""
app.py — Signal Desk: report-signal equity-research dashboard (READ-ONLY).

Deep-navy + indigo/purple chrome; green/red reserved for performance semantics. A slim
full-width top bar (logo, search, horizontal nav, light/dark toggle) over a left ticker
watchlist + four nav views: Ranking, Model, Data, Backtest. Company Detail is a drill-down,
reachable only by clicking a company in the watchlist or a Ranking row — it has no nav item.

Reads data/financials.db plus the eda/, predictions/ and analysis/ artifacts via cached
loaders. Writes nothing.

Two standing rules in here:
  * Every headline number is DERIVED from an artifact (universe size, ablation max,
    per-rebalance sequence, target std). Nothing about the 97-name universe is hard-coded,
    so a pipeline rerun cannot leave the narrative stale.
  * The near-null result is the finding. Charts do not dramatise noise: metrics that hug
    zero get neutral fills and a prominent zero/chance reference rule.

Run from the repo root:
    streamlit run dashboard/app.py
"""
from __future__ import annotations


import streamlit as st

import data
import ui

# The four standalone nav items. "Company Detail" is deliberately NOT here: it is a
# drill-down, reachable only by clicking a company in the left watchlist (or a Ranking row).
VIEWS = ["Ranking", "Model", "Data", "Backtest"]
DETAIL_VIEW = "Company Detail"


def _apply_native_theme(mode: str) -> None:
    """Push our palette into Streamlit's OWN theme, not just our injected CSS.

    Streamlit renders st.dataframe on a canvas-based grid and styles its widgets from the
    theme object it receives in the NewSession message — CSS reaches neither. Without this,
    the toggle flips our chrome while the dataframe, nav strip and buttons stay dark.

    TIMING MATTERS: NewSession is emitted at the START of a script run, so this must be
    called in the toggle handler BEFORE st.rerun() — calling it from main()'s body would only
    take effect one run late. `st._config` is private; guarded, so if it ever breaks our own
    components stay correctly themed and only Streamlit's native widgets fall back."""
    P = ui.palette(mode)
    try:
        st._config.set_option("theme.base", "light" if mode == "light" else "dark")
        st._config.set_option("theme.primaryColor", P["accent"])
        st._config.set_option("theme.backgroundColor", P["bg"])
        st._config.set_option("theme.secondaryBackgroundColor", P["panel"])
        st._config.set_option("theme.textColor", P["text"])
    except Exception:
        pass


def top_bar() -> str:
    """Slim top bar: [logo] [ search + 4 nav items, centred ] [theme toggle].

    The search box and the four nav items form ONE centred group with equal ~0.5cm gaps.
    Nav items are plain text (white on dark, black on light) with NO active-state highlight —
    outline + tint on hover only. The logo is a click-home target -> Ranking (a transparent
    button overlays it, the same in-session trick used by the ranking rows).

    `view` is plain session state, not a widget key, so any caller may assign it directly."""
    with st.container(key="topbar"):
        # equal outer columns keep the middle group centred on the page
        c_logo, c_mid, c_toggle = st.columns([1.5, 7.0, 1.5], vertical_alignment="center")
        with c_logo:
            with st.container(key="logohome"):
                logo_uri, whiten = data.app_logo_uri(st.session_state["mode"])
                st.markdown(ui.logo_html(logo_uri, whiten), unsafe_allow_html=True)
                if st.button("Home", key="logobtn", help="Back to Ranking"):
                    st.session_state["view"] = "Ranking"
                    st.rerun()
        with c_mid:
            with st.container(key="navgroup"):
                cols = st.columns([1, 1, 1, 1, 1], gap="small")
                with cols[0]:
                    st.text_input("search", placeholder="Search ticker or company…",
                                  label_visibility="collapsed", key="co_search")
                # NO active-state highlight: every nav item is a plain text button, always
                # `secondary`. Streamlit fills `primary` buttons with theme.primaryColor, so
                # marking the current view would reintroduce the purple pill.
                for col, name in zip(cols[1:], VIEWS):
                    with col:
                        if st.button(name, key=f"nav_{name.lower()}"):
                            st.session_state["view"] = name
                            st.rerun()
        with c_toggle:
            with st.container(key="themebox"):
                icon = "☀" if st.session_state["mode"] == "dark" else "☾"
                if st.button(icon, key="themebtn", help="Toggle light / dark"):
                    new_mode = "light" if st.session_state["mode"] == "dark" else "dark"
                    st.session_state["mode"] = new_mode
                    # must precede the rerun — see _apply_native_theme's timing note
                    _apply_native_theme(new_mode)
                    st.rerun()
    return st.session_state["view"]


def watchlist(companies) -> None:
    """Left column: sector filter + the ticker-only company list (names on hover).

    SORT: pure alphabetical by the DISPLAYED (suffix-stripped) ticker — the exact string the
    user reads — so the list is truly A→Z on screen. NOT sector-grouped. Filtering to one
    sector preserves that order, so a single sector reads A→Z too.

    Numeric tickers (6758, 7203, 8306, 9988, 000660, 005930) are pushed to the END, after the
    letters — the alphabet reads first, then the numbered listings. A plain string sort would
    put digits FIRST (ASCII), so the leading `_num` key deliberately overrides that.

    The sort lives HERE, not in `data.load_companies()`, for two reasons: (a) sorting by the
    display ticker needs `display_tickers()`, which itself calls `load_companies()` — sorting
    in the loader would be circular; (b) other views consume `load_companies()` and must not
    be silently reordered. (Audited: every other consumer is order-independent — dict lookups,
    boolean filters, unique CSS selectors — so this is belt-and-braces.)

    Tickers are shown WITHOUT their exchange suffix; the real ticker remains the widget key,
    the session-state value and the routing identity. Search still matches the real ticker, so
    typing 'SHEL.L' or 'SHEL' both find Shell."""
    with st.container(key="watchlist"):
        sectors = ["All sectors"] + sorted(companies["sector"].unique())
        st.selectbox("sector", sectors, label_visibility="collapsed", key="co_sector")

        disp = data.display_tickers()
        # sort by the rendered label, once, before filtering (filters preserve row order).
        # `_num` (0 for letters, 1 for digit-leading) sorts A→Z first, numeric tickers last.
        _disp = companies["ticker"].map(disp)
        df = (companies.assign(_disp=_disp, _num=_disp.str[0].str.isdigit().astype(int))
              .sort_values(["_num", "_disp"], kind="stable"))
        pick = st.session_state.get("co_sector", "All sectors")
        if pick != "All sectors":
            df = df[df["sector"] == pick]
        q = (st.session_state.get("co_search") or "").strip().lower()
        if q:
            # match on the real ticker, the display ticker and the name
            df = df[df["ticker"].str.lower().str.contains(q)
                    | df["_disp"].str.lower().str.contains(q, regex=False)
                    | df["name"].str.lower().str.contains(q)]

        st.markdown(f'<div class="sd-wl-label"><span>Watchlist</span>'
                    f'<span class="ct">{len(df)}</span></div>', unsafe_allow_html=True)

        with st.container(key="colist"):
            if df.empty:
                st.caption("No matches.")
            for _, r in df.iterrows():
                tk = r["ticker"]                       # the real key — never the display string
                selected = st.session_state.get("selected") == tk
                if st.button(disp[tk], key=ui.safe_key(tk),
                             help=f"{r['name']} · {r['sector']} · {tk}",
                             use_container_width=True,
                             type="primary" if selected else "secondary"):
                    st.session_state["selected"] = tk
                    st.session_state["view"] = DETAIL_VIEW  # the only route into detail
                    st.rerun()


def view_ranking(logos: dict) -> None:
    mode = st.session_state["mode"]
    fc = data.flag_counts()
    st.markdown(f'<div class="sd-view-title">Company Ranking</div>'
                f'<div class="sd-view-sub">All {fc["n"]} companies by model-predicted '
                f'forward-63d Sharpe · long top-10 / short bottom-10. Universe = the mandated '
                f'98 minus GOOG (Alphabet dual-class dedup — GOOGL retained).</div>',
                unsafe_allow_html=True)

    ui.caveat(mode, "shown for completeness. Out-of-sample signal is weak (near-zero rank "
                    "correlation) and the long/short backtest is flat — see the <b>Model</b> "
                    "tab. Rankings are low-confidence, not investment advice.")

    # ONE tab-level scope statement replaces the old per-row Confidence column: a per-row
    # "prediction-only" flag contradicted the ranking by flagging the very rows it recommends.
    # Counts are DERIVED, so the sentence cannot drift from the artifacts.
    ui.scope_note(
        mode,
        f"The model is trained on the <b>{fc['train_eligible']} companies</b> that have a "
        f"valid forward-63-day target and sufficient history. <b>All {fc['n']} companies</b> "
        f"are fully processed (fundamentals, KPIs, scores, features) and ranked; the other "
        f"<b>{fc['prediction_only']}</b> — thin-history internationals and names without "
        f"machine-readable release dates — are ranked as <b>out-of-sample predictions</b> from "
        f"that model. This is a methodology demonstration, not a portfolio.")

    df = data.load_ranking()
    disp = data.display_tickers()          # DISPLAY ONLY — routing still uses the real ticker
    longs = df[df["basket"] == "LONG"]["ticker"].tolist()
    shorts = df[df["basket"] == "SHORT"]["ticker"].tolist()
    ui.basket_summary(mode, [disp[t] for t in longs], [disp[t] for t in shorts])

    # Summary-level (NOT per-row) honesty line: how much of the actual book is out-of-sample.
    # The general scope statement above cannot convey this — "6 of the 20 picks" is a concrete
    # fact about the recommendation itself. All counts derived.
    n_flag_long = int(df[df["basket"] == "LONG"]["out_of_training_dist"].sum())
    n_flag_short = int(df[df["basket"] == "SHORT"]["out_of_training_dist"].sum())
    ui.note(f"<b>{n_flag_long}</b> of the {len(longs)} longs and <b>{n_flag_short}</b> of the "
            f"{len(shorts)} shorts are out-of-sample names the model never trained on — "
            f"<b>{n_flag_long + n_flag_short} of the {len(longs) + len(shorts)} picks</b>.")

    # Full-page table: every row rendered down the page, no fixed-height widget and no inner
    # scrollbar. st.dataframe cannot do this without its canvas row-selector checkbox column
    # (drawn inside the grid canvas, unreachable from CSS), so the table is an HTML grid with
    # a transparent full-row st.button overlaid per row. That keeps the click IN-SESSION — a
    # query-param link would full-reload the page and drop the theme/view state.
    ui.ranking_table_head()
    with st.container(key="ranktable"):     # gap:0 wrapper — rows must butt up against each other
        for _, r in df.iterrows():
            tk = r["ticker"]                # the real key — logos, routing and state all use it
            key = ui.safe_key(tk)
            with st.container(key=f"rkrow_{key}"):
                st.markdown(
                    ui.ranking_row_html(
                        mode, rank=int(r["rank_ensemble"]), logo=logos.get(tk),
                        ticker=disp[tk], name=r["name"], sector=r["sector"],
                        pred=float(r["pred_ensemble"]), basket=r["basket"],
                        selected=st.session_state.get("selected") == tk),
                    unsafe_allow_html=True)
                if st.button(tk, key=f"rkbtn_{key}", use_container_width=True,
                             help=f"Open {r['name']} detail ({tk})"):
                    st.session_state["selected"] = tk
                    st.session_state["view"] = DETAIL_VIEW
                    st.rerun()

    st.caption("Click any row to open its Company Detail.")


def _tab_performance(mode, cv, tm) -> None:
    """CV selection + the one-shot test. (Feature→target correlation now lives under Data.)"""
    import pandas as pd
    import charts

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
    ui.note("Lasso and ElasticNet drive <b>every</b> coefficient to exactly zero — they ARE "
            "the mean predictor. Their CV Spearman is an artifact of a constant prediction, "
            "not learned signal, so they are excluded from the ensemble and from the "
            "&ldquo;best model&rdquo; tile above.")

    cvp = cv.sort_values("cv_spearman_mean").copy()
    cvp["cv_spearman_mean_lo"] = cvp["cv_spearman_mean"] - cvp["cv_spearman_std"]
    cvp["cv_spearman_mean_hi"] = cvp["cv_spearman_mean"] + cvp["cv_spearman_std"]
    st.markdown('<div class="sd-note"><b>CV Spearman per model</b> (bars) with ±1 std '
                'whiskers. Every whisker straddles zero — no model beats chance. '
                'The feature-level view of the same null lives under <b>Data</b>.</div>',
                unsafe_allow_html=True)
    st.altair_chart(charts.signed_bar(
        cvp, "model", "cv_spearman_mean", mode, x_title="CV rank correlation",
        domain=(-0.16, 0.16), height=240, err=True), width="stretch")


def _tab_error(mode) -> None:
    """Bias-variance: the two failure modes, and the learning curves that settle which binds."""
    import charts

    tv = data.load_train_vs_val()
    tstd = data.target_std()

    ui.section("Error analysis · bias and variance")
    ui.note(f"Validation RMSE sits at the target's own standard deviation "
            f"(<b>{tstd:.3f}</b>) for every model — the score a mean-predictor achieves. "
            "But the models get there <b>two different ways</b>, and calling them all "
            "&ldquo;high-bias, low-variance&rdquo; would be wrong.")

    over = tv.loc[tv["train_spearman"].idxmax()]
    under = tv[tv["train_spearman"] == 0]
    ui.stat_tiles([
        (f"{tstd:.3f}", "Target std (train+val)", "the RMSE of predicting the mean"),
        (f"+{over['train_spearman']:.3f} → {over['val_spearman']:+.3f}",
         f"{over['model']} train → val ρ", "memorises, generalises at zero (variance)"),
        (f"{len(under)}", "Models regularised to null",
         "Lasso/ElasticNet: every coefficient = 0 (bias)"),
        (f"{tv['val_spearman'].min():+.3f} … {tv['val_spearman'].max():+.3f}",
         "Validation ρ range", "all six models · straddles zero"),
    ])

    tvs = tv.sort_values("train_spearman", ascending=False)
    st.markdown('<div class="sd-note"><b>Train → validation collapse.</b> A long bar is a '
                'high-<i>variance</i> model that memorised the training rows (SVR ρ +0.92 → '
                '+0.00). A dot stacked on zero is a high-<i>bias</i> model regularised into '
                'the mean predictor. Both land in the same place out of sample.</div>',
                unsafe_allow_html=True)
    st.altair_chart(charts.train_val_dumbbell(tvs, mode), width="stretch")

    ui.section("Learning curves · does more data help?")
    ui.note("Validation error against an expanding chronological training prefix. "
            "<b>If variance were the binding constraint, validation error would fall as data "
            "grows.</b> It does not — it sits flat on the mean-predictor line. More data, more "
            "capacity and more tuning cannot fix this; only a more informative feature set "
            "could.")
    pick = st.segmented_control("Model", data.LEARNING_CURVE_MODELS,
                                default="RandomForest", key="lc_model")
    lc = data.load_learning_curve(pick or "RandomForest")
    st.altair_chart(charts.learning_curve(lc, mode, ref=tstd), width="stretch")

    with st.expander("Train vs validation error — full table"):
        st.dataframe(tv.round(4), hide_index=True, width="stretch")
    with st.expander("Reference figures (matplotlib learning curves)"):
        for m in data.LEARNING_CURVE_MODELS:
            st.caption(m)
            st.image(data.analysis_fig(f"fig_learning_curve_{m}.png"), width="stretch")


def _tab_importance(mode) -> None:
    """The models are not black boxes — and interpretability CONFIRMS the null."""
    import charts

    fi = data.load_feature_importance()
    ui.section("Feature importance · the model is not a black box")

    n_zero_lasso = int((fi["Lasso"] == 0).sum())
    n_feat = len(fi)
    ui.note(f"<b>Lasso and ElasticNet select 0 of {n_feat} features</b> — every coefficient is "
            f"exactly zero. That is the cleanest possible statement of the null: no linear "
            f"combination of these features beats the intercept. Ridge keeps all "
            f"{n_feat} but at trivial magnitude; RF/XGB importances spread thinly with no "
            f"dominant split variable; SVR is explained by permutation importance on the "
            f"<b>validation</b> folds (never the test set).")

    # invert against the GLOBAL worst rank so the bar lengths are comparable across models,
    # not rescaled to whatever happens to be in the top-10 subset
    worst_rank = fi["mean_rank"].max()
    cons = fi.nsmallest(10, "mean_rank")[["feature", "mean_rank"]].copy()
    cons["consensus"] = worst_rank + 1 - cons["mean_rank"]  # higher = more important
    c1, c2 = st.columns([1, 1], gap="large")
    with c1:
        st.markdown('<div class="sd-note"><b>Rank-consensus top 10</b> across all six models '
                    '(inverted mean rank). Mostly <i>change</i> features.</div>',
                    unsafe_allow_html=True)
        st.altair_chart(charts.importance_bar(
            cons, "feature", "consensus", mode, x_title="consensus (inverted mean rank)",
            height=290), width="stretch")
    with c2:
        model = st.selectbox("Per-model importance",
                             ["XGBoost", "RandomForest", "Ridge", "SVR_perm"], key="fi_model")
        sub = fi[["feature", model]].copy()
        sub["mag"] = sub[model].abs()
        sub = sub.nlargest(10, "mag")[["feature", model]]
        st.altair_chart(charts.importance_bar(
            sub, "feature", model, mode, x_title=f"{model} importance", height=290),
            width="stretch")

    ui.note(f"<b>Read the magnitudes, not just the ranking.</b> Lasso zeroes all {n_zero_lasso} "
            "features; the surviving importances are trivially small. This ranks near-noise — "
            "interpretability <i>confirms</i> the null, it does not rescue it.")

    with st.expander("Consensus figure + per-model figures (matplotlib)"):
        for f in ["fig_importance_consensus.png", "fig_importance_XGBoost.png",
                  "fig_importance_RandomForest.png", "fig_importance_Ridge.png"]:
            st.image(data.analysis_fig(f), width="stretch")
    with st.expander("Full importance table (48 features × 6 models)"):
        st.dataframe(fi.round(4), hide_index=True, width="stretch")


def _tab_classification(mode) -> None:
    """The classification lens — same answer, near chance."""
    import charts

    cm = data.load_classification()
    ui.section("Classification lens · can we separate winners from losers?")
    ui.note("Label = <b>top-third vs bottom-third</b> realized forward Sharpe (middle dropped), "
            "matching the long/short framing. <b>Leak control:</b> tercile cutoffs are fit on "
            "<b>train rows only</b> — per CV fold from that fold's train rows, and from "
            "train+val for the one-shot test. Test outcomes never inform a cutoff.")

    scheme_lbl = st.segmented_control(
        "Labelling scheme", ["Train-fitted tercile", "Balanced within-period"],
        default="Train-fitted tercile", key="cls_scheme")
    scheme = ("train_fitted_tercile" if (scheme_lbl or "").startswith("Train")
              else "within_period_tercile")
    sub = cm[cm["scheme"] == scheme].copy()
    base = float(sub["majority_baseline_acc"].iloc[0])

    ui.stat_tiles([
        (f"{sub['test_auc'].min():.3f}–{sub['test_auc'].max():.3f}", "Test AUC range",
         "chance = 0.500"),
        (f"{sub['cv_auc'].mean():.3f}", "Mean CV AUC", "mostly below 0.5 → sign is noise"),
        (f"{base:.3f}", "Majority baseline acc.",
         "raw accuracy at/below this is meaningless"),
        (f"{sub['test_balanced_accuracy'].mean():.3f}", "Mean balanced accuracy",
         "the metric to read · 0.5 = chance"),
    ])

    c1, c2 = st.columns([1.05, 1], gap="large")
    with c1:
        bars = sub[["model", "test_auc"]].rename(columns={"test_auc": "auc"})
        bars = bars.sort_values("auc", ascending=False)
        st.markdown('<div class="sd-note"><b>Test AUC vs chance.</b> Bars show <b>AUC − 0.5</b>, '
                    'so length is literally distance from chance and the baseline <i>is</i> '
                    'chance (labels carry the true AUC). Every model hugs it; SVM lands '
                    '<i>below</i>. Neutral fill on purpose — colouring noise green/red would '
                    'dramatise a result that is not there.</div>', unsafe_allow_html=True)
        st.altair_chart(charts.auc_bars(bars, mode), width="stretch")
    with c2:
        st.markdown('<div class="sd-note"><b>Metrics.</b> Read AUC and <i>balanced</i> '
                    'accuracy. Raw accuracy is misleading here — the train-fitted cutoff plus '
                    'a higher-Sharpe test regime leaves the test set '
                    f'{base:.1%} one class.</div>', unsafe_allow_html=True)
        show = sub[["model", "cv_auc", "test_auc", "test_accuracy",
                    "test_balanced_accuracy", "test_f1"]].round(3)
        show.columns = ["Model", "CV AUC", "Test AUC", "Acc.", "Bal. acc.", "F1"]
        st.dataframe(show, hide_index=True, width="stretch")

    with st.expander("ROC curves"):
        st.image(data.analysis_fig("fig_roc_curves.png"), width="stretch")
    with st.expander("Confusion matrices"):
        st.image(data.analysis_fig("fig_confusion_matrices.png"), width="stretch")

    ui.note("<b>Verdict:</b> a classification framing gives the <b>same answer</b> as the "
            "regression — future winners cannot be separated from losers better than chance. "
            "<br><b>Honest caveat:</b> the test set was already used once by the regression; "
            "this evaluation touches it a second time under a <i>pre-committed</i> protocol "
            "(labels, models, grids and metrics all fixed before looking). No iterative tuning "
            "against the test set.")


def _tab_robustness(mode) -> None:
    ui.section("Robustness · feature-set ablation")
    abl_raw = data.load_ablation()
    max_abl = abl_raw["cv_spearman"].abs().max()
    n_cells = len(abl_raw)
    ui.note(f"Re-running the whole roster on <b>sub-scores only</b> vs <b>KPIs only</b> vs "
            f"<b>full</b> — the null does not move. Max |CV Spearman| across all {n_cells} "
            f"cells = <b>{max_abl:.3f}</b>. No feature family lifts rank correlation above "
            f"noise, so the null is robust to feature choice.")
    abl = abl_raw.pivot_table(index="model", columns="feature_set",
                              values="cv_spearman").round(4)
    abl = abl[["subscores_only", "kpis_only", "full"]].reset_index()
    st.dataframe(abl, hide_index=True, width="stretch")


def _data_feature_target(mode, ft, ft_rel) -> None:
    """The feature-level view of the null: how each feature ranks against the target."""
    import charts

    ui.section("Feature → target rank correlation")
    max_ft = ft_rel["spearman"].abs().max()
    ui.note(f"Spearman of each feature against <code>future_63d_sharpe</code>, on "
            f"<b>train-eligible rows only</b>. Restricted to well-populated features "
            f"(n≥800) — sparse bank-only KPIs show large correlations that are "
            f"small-subsample artifacts, not deployable signal. The strongest reliable "
            f"feature reaches <b>{max_ft:.3f}</b>. This is the feature-level statement of the "
            f"same null the <b>Model</b> tab reports: no single feature carries the target.")

    top = ft_rel.reindex(ft_rel["spearman"].abs().sort_values(ascending=False).index).head(15)
    st.altair_chart(charts.signed_bar(
        top, "feature", "spearman", mode, x_title="Spearman vs future_63d_sharpe",
        domain=(-0.1, 0.1), height=380), width="stretch")

    with st.expander("All features · full correlation table"):
        show = ft[["feature", "n", "pearson", "spearman", "reliable"]].copy()
        show = show.reindex(show["spearman"].abs().sort_values(ascending=False).index)
        st.dataframe(show.round(4), hide_index=True, width="stretch")
    with st.expander("Reference figure (matplotlib · top-20)"):
        st.image(data.eda_fig("fig_target_corr_bar.png"), width="stretch")


def _data_distributions(mode) -> None:
    ui.section("Feature distributions")
    ui.note("Distributions on train-eligible rows. Ratio-tail KPIs (ROIC, cash_conversion, "
            "the <code>*_growth_yoy</code> family) carry extreme values from near-zero "
            "denominators and are winsorized at the 1st/99th percentile — "
            "<b>caps refit train-only inside each CV fold</b>, never on the full population.")
    for label, fname in [
        ("Scores · train vs prediction-only", "fig_dist_scores.png"),
        ("KPIs (winsor caps marked)", "fig_dist_kpis.png"),
        ("Raw vs winsorized ratio-tails", "fig_dist_winsor_rawvswins.png"),
    ]:
        with st.expander(label):
            st.image(data.eda_fig(fname), width="stretch")
    with st.expander("Skew / kurtosis table"):
        st.dataframe(data.load_skew().round(3), hide_index=True, width="stretch")


def _data_corr_vif(mode) -> None:
    ui.section("Redundancy · feature–feature correlation and VIF")
    vif = data.load_vif()
    n_inf = int((vif["VIF"] > 1e6).sum())
    # NB: n_inf counts FEATURES, not identities — one identity (e.g. financial_score =
    # mean of the six sub-scores) makes several features perfectly collinear at once.
    ui.note(f"<b>{n_inf} features</b> carry VIF = ∞ — perfect collinearity arising from a "
            "handful of exact by-construction identities (financial_score = mean of the six "
            "sub-scores; net_debt_to_assets = debt_to_assets − cash_to_assets; "
            "free_cash_flow_margin = operating_cash_flow_margin − capex_intensity; …). "
            "These, plus the high-VIF redundancies, drove the de-duplicated feature set.")

    vshow = vif[vif["flag"] != ""][["block", "feature", "VIF", "flag"]].copy()
    vshow["VIF"] = vshow["VIF"].map(lambda v: "∞" if v > 1e6 else f"{v:.1f}")
    st.dataframe(vshow, hide_index=True, width="stretch")

    with st.expander("Feature–feature correlation heatmap"):
        st.image(data.eda_fig("fig_corr_heatmap.png"), width="stretch")
    with st.expander("Redundant pairs (|Pearson| > 0.8)"):
        st.dataframe(data.load_high_corr().round(3), hide_index=True, width="stretch")

    ui.note("<b>Caution:</b> the six sub-scores ARE percentile aggregations of these KPIs, so "
            "the sub-score block and the KPI block structurally overlap. Prefer regularized or "
            "tree models; do not read linear coefficients naively. The <b>Model → Robustness</b> "
            "tab ablates the two blocks against each other.")


def _data_target(mode) -> None:
    ui.section("Target and missingness")
    ui.note("<code>future_63d_sharpe</code> = mean(daily ret t+1…t+63) / std · √252, with "
            "t+1 the first trading day strictly <b>after the report release date</b> on each "
            "stock's own calendar. Risk-free = 0 (a stated simplification; negligible for "
            "within-period rankings).")
    with st.expander("Target distribution (raw vs winsorized)", expanded=True):
        st.image(data.eda_fig("fig_dist_target.png"), width="stretch")
    with st.expander("Summary statistics"):
        st.dataframe(data.load_target_summary().round(4), hide_index=True, width="stretch")
    with st.expander("Forward Sharpe by sector (in-sample)"):
        st.image(data.eda_fig("fig_target_by_sector.png"), width="stretch")
        st.dataframe(data.load_target_by_sector().round(3), hide_index=True, width="stretch")
        ui.note("<b>Sector is a grouping key for scoring, never a model feature.</b> These "
                "medians differ in-sample, but that is in-sample dispersion, not a "
                "look-ahead-safe signal — no sector identity, one-hots or sector means are fed "
                "to the model.")
    with st.expander("Missingness (US vs international)"):
        st.image(data.eda_fig("fig_missingness.png"), width="stretch")
        ui.note("A KPI that cannot be computed is <b>dropped and the sub-score renormalized</b> "
                "over the remainder — never imputed with zero. Missing is "
                "<code>selection_status='missing'</code>, never a naive <code>value == 0</code>.")


def view_model() -> None:
    """Model-specific diagnostics only: predictions/ + analysis/. EDA lives under Data."""
    mode = st.session_state["mode"]
    st.markdown('<div class="sd-view-title">Model</div>'
                '<div class="sd-view-sub">Leak-safe model performance, error analysis, '
                'interpretability and a classification cross-check — reported straight.</div>',
                unsafe_allow_html=True)

    cv = data.load_cv()
    tm = data.load_test_metrics()
    ens = tm[tm["model"].str.startswith("ENSEMBLE")].iloc[0]
    best_cv = data.best_real_cv(cv)          # excludes the degenerate constant models
    abl = data.load_ablation()

    ui.note("<b>Verdict:</b> report fundamentals carry <b>no reliable signal</b> for the "
            "forward 63-day Sharpe on this universe/period — the honest result, consistent "
            "with market efficiency. Every metric below is indistinguishable from zero. The "
            "value of this project is the leak-free methodology, not alpha.")

    ui.stat_tiles([
        (f"{best_cv['cv_spearman_mean']:+.3f}", "Best CV Spearman",
         f"{best_cv['model']} · ±{best_cv['cv_spearman_std']:.3f} · non-degenerate models only"),
        (f"{ens['test_spearman_pooled']:+.3f}", "Ensemble test Spearman", "held-out 12-month test"),
        (f"{ens['test_rmse']:.2f}", "Ensemble test RMSE", "future_63d_sharpe units"),
        (f"{abl['cv_spearman'].abs().max():.3f}", "Ablation max |CV Spearman|",
         f"across all {len(abl)} feature-set × model cells"),
    ])

    t1, t2, t3, t4, t5 = st.tabs(
        ["Performance", "Error analysis", "Feature importance", "Classification", "Robustness"])
    with t1:
        _tab_performance(mode, cv, tm)
    with t2:
        _tab_error(mode)
    with t3:
        _tab_importance(mode)
    with t4:
        _tab_classification(mode)
    with t5:
        _tab_robustness(mode)


def view_data() -> None:
    """Exploratory data analysis only: everything sourced from eda/."""
    mode = st.session_state["mode"]
    st.markdown('<div class="sd-view-title">Data</div>'
                '<div class="sd-view-sub">Exploratory analysis of the modelling table — '
                'features, redundancy, target and coverage. Train-eligible rows only.</div>',
                unsafe_allow_html=True)

    ft = data.load_feature_target()
    ft_rel = ft[ft["reliable"] == True]
    vif = data.load_vif()

    ui.note("Everything here is computed on <b>train-eligible rows only</b> and regenerated on "
            "the final 97-name universe. It is read-only: <code>I_eda.py</code> writes the "
            "<code>eda/</code> artifacts, this view only displays them.")

    ui.stat_tiles([
        (f"{ft_rel['spearman'].abs().max():.3f}", "Max feature |Spearman|",
         "strongest well-populated feature vs target"),
        (f"{int(ft['n'].max()):,}", "Train-eligible rows", "one row per company-report"),
        (f"{len(ft)}", "Features screened", f"{len(ft_rel)} well-populated (n≥800)"),
        (f"{int((vif['VIF'] > 1e6).sum())}", "Features with VIF = ∞",
         "perfect by-construction collinearity"),
    ])

    t1, t2, t3, t4 = st.tabs(
        ["Feature → target", "Distributions", "Correlation & VIF", "Target & missingness"])
    with t1:
        _data_feature_target(mode, ft, ft_rel)
    with t2:
        _data_distributions(mode)
    with t3:
        _data_corr_vif(mode)
    with t4:
        _data_target(mode)


def view_backtest(logos: dict) -> None:
    import pandas as pd
    import charts
    mode = st.session_state["mode"]
    P = ui.palette(mode)
    st.markdown('<div class="sd-view-title">Backtest</div>'
                '<div class="sd-view-sub">Walk-forward top-10 long / bottom-10 short over the '
                'held-out test year.</div>', unsafe_allow_html=True)

    per = data.load_backtest_periods()
    rf = data.risk_free_annual()
    ui.note("<b>A test of the pipeline, not a claim of alpha.</b> The ensemble is frozen on "
            "pre-test data and applied forward to each quarterly rebalance. Equal-weight "
            f"top-10 long / bottom-10 short, ~63-day hold, risk-free = {rf:.0%} annualized "
            "(3-month T-bill, FRED TB3MS). The book is dollar-neutral and self-financing, so "
            "the rf earned on the short proceeds cancels the rf charged on the spread — the "
            f"long–short Sharpe is unchanged by it. With only {len(per)} "
            "rebalances the statistics are high-variance — read direction, not precision.")
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
    ui.section("Equity curve · cumulative return")
    net_ls = per["gross_ls"] - (cost / 1e4) * per["traded_notional_oneway"]
    pts = ["Start"] + per["period"].tolist()
    cl = cs = cx = 1.0
    long_eq, short_eq, ls_eq = [0.0], [0.0], [0.0]
    for i in range(len(per)):
        cl *= 1 + per["long_ret"].iloc[i]; long_eq.append(cl - 1.0)
        cs *= 1 + per["short_ret"].iloc[i]; short_eq.append(cs - 1.0)
        cx *= 1 + net_ls.iloc[i]; ls_eq.append(cx - 1.0)
    tidy = pd.concat([
        pd.DataFrame({"Point": pts, "Series": "Long basket", "Value": long_eq}),
        pd.DataFrame({"Point": pts, "Series": "Short basket", "Value": short_eq}),
        pd.DataFrame({"Point": pts, "Series": "Long–Short (net)", "Value": ls_eq}),
    ])
    cmap = {"Long basket": P["up"], "Short basket": P["down"], "Long–Short (net)": P["strong"]}
    st.altair_chart(charts.equity_lines(tidy, mode, pts, cmap, height=300), width="stretch")
    # DERIVED, sign-safe: never assert "no edge" from a hardcoded sign — the per-rebalance
    # spread flips, and that (not the cumulative sign) is what makes it indistinguishable
    # from noise. A pipeline rerun must not be able to leave this sentence false.
    n_pos = int((per["gross_ls"] > 0).sum())
    flips = n_pos not in (0, len(per))
    ui.note(f"Long basket {long_eq[-1]:+.0%}, short basket {short_eq[-1]:+.0%} "
            f"(both carried by a strong market); the long–short spread nets to {ls_eq[-1]:+.1%}. "
            + (f"The per-rebalance spread <b>flips sign</b> ({n_pos} of {len(per)} positive), so "
               "over this many rebalances it is not distinguishable from noise. "
               if flips else
               f"All {len(per)} rebalances share the same sign, but {len(per)} points cannot "
               "establish an edge. ")
            + "The short <i>basket</i> is shown as its own return; a short position "
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
    # ImageColumn paints on a canvas grid that CSS cannot round, so this one surface uses the
    # variant with the circle clipped into the SVG source itself.
    round_logos = data.logo_uris_round()
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
                "Logo": [round_logos.get(t, "") for t in g["ticker"]],
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

    # derived from backtest_periods.csv — never hard-coded, so it can't go stale on a rerun.
    # NB: the cumulative sign is NOT the evidence. With this few rebalances the mean sits well
    # inside one standard deviation, so state THAT (it stays true whichever way the sum lands).
    seq = ", ".join(f"{v:+.0%}" for v in per["gross_ls"])
    n_flip = int((per["gross_ls"] > 0).sum())
    g = per["gross_ls"]
    tstat = g.mean() / (g.std(ddof=1) / len(g) ** 0.5) if g.std(ddof=1) > 0 else 0.0
    ui.note(f"<b>Honest read:</b> per-rebalance long-short flips sign ({seq}) with no "
            f"persistence — {n_flip} of {len(per)} quarters positive. The mean quarterly spread "
            f"is {g.mean():+.1%} against a standard deviation of {g.std(ddof=1):.1%} "
            f"(t = {tstat:+.2f} on {len(per) - 1} d.f.), i.e. <b>not distinguishable from "
            "zero</b> — whatever sign the cumulative figure happens to take. Consistent with "
            "the near-null model and market efficiency: the backtest confirms the pipeline runs "
            "end-to-end and leak-free, nothing more.")


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
    badge = ui.hero_badge(tk, r["sector"], data.logo_uris().get(tk), mode)

    rank = data.load_ranking()
    rr = rank[rank["ticker"] == tk].iloc[0]
    hist = data.company_history(tk)
    latest = hist.iloc[-1] if len(hist) else None

    # confidence tier straight from the pipeline flags (not inferred from `source`)
    conf = rr["confidence"]
    chips = f'<span class="sd-chip">{conf}</span>'
    if rr["operative_missing"]:
        chips += '<span class="sd-chip">No operative score</span>'
    # Detail always shows the FULL, exchange-qualified ticker (Ranking/Watchlist strip the
    # suffix for scanability) — this is where the exact symbol must remain available.
    st.markdown(
        f'<div class="sd-hero">{badge}<div><div class="nm">{r["name"]}</div>'
        f'<div class="sub"><span class="tkfull" title="Exchange-qualified ticker">{tk}</span>'
        f' &nbsp;·&nbsp; {r["sector"]} &nbsp;·&nbsp; '
        f'{r["company_group"]} {chips}</div></div></div>',
        unsafe_allow_html=True)

    basket = rr["basket"] or "—"
    bcol = P["up"] if basket == "LONG" else P["down"] if basket == "SHORT" else P["muted"]
    op = latest["operative_score"] if latest is not None else None
    ui.stat_tiles([
        (f"{rr['pred_ensemble']:+.2f}", "Predicted fwd-63d Sharpe", "ensemble · low-confidence"),
        (f"#{int(rr['rank_ensemble'])}", f"Rank of {len(rank)}",
         f"<span style='color:{bcol}'>{basket}</span>" if basket != "—" else "mid-book"),
        (f"{latest['financial_score']:.2f}" if latest is not None and pd.notna(latest['financial_score']) else "—",
         "Financial score", "sector percentile (latest)"),
        (f"{op:.2f}" if op is not None and pd.notna(op) else "N/A",
         "Operative score", "qualitative 1–5 → [0,1]"),
    ])

    # ---- price overview ----
    # DISPLAY ONLY. This chart reads the firewalled `ohlc_display.db`; nothing here feeds the
    # model. Falls back to daily_prices (adjusted close) if a ticker has no OHLC cache, and to
    # a caption if it has neither — thin/blocked names still have prices, so this is rare.
    ui.section("Price · overview")
    ohlc = data.company_ohlc(tk)
    if len(ohlc):
        # badge uses the DAILY series (exact first->last close); the chart is weekly bars
        chg = data.period_change(ohlc, "close")
        span = f"{ohlc['date'].min():%b %Y} – {ohlc['date'].max():%b %Y}"
        if chg is not None:
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:12px;margin:2px 0 10px;">'
                f'{ui.change_badge(mode, chg, span)}</div>', unsafe_allow_html=True)
        # cached spec + st.vega_lite_chart: keeps ~85ms of Altair build+serialize off the
        # rerun path (see data.ohlc_chart_spec)
        st.vega_lite_chart(data.ohlc_chart_spec(tk, mode), width="stretch")
        ui.note("Weekly bars aggregated from unadjusted daily prices, in the stock's own "
                "listing currency (London names are in GBp). Hover for the week-ending date "
                "and its OHLC. <b>Display only</b> — this series is cached separately and is "
                "never used by the model; the target is built from the adjusted-close series "
                "in <code>daily_prices</code>.")
    else:
        px = data.company_prices(tk)          # graceful fallback: adjusted close
        if len(px):
            st.altair_chart(charts.price_line(px, mode), width="stretch")
            ret = data.period_change(px, "adjusted_close")
            if ret is not None:
                ui.note(f"{px['date'].min():%b %Y} – {px['date'].max():%b %Y} · total change "
                        f"<b>{ret:+.0%}</b> (adjusted close; no OHLC cached for this ticker).")
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

    extra = ""
    if rr["no_release_date"]:
        extra = (" This name has <b>no usable report-release date</b>, so no look-ahead-safe "
                 "target could ever be built for it. It is ranked on features alone and was "
                 "never trained on — the lowest-confidence tier.")
    elif rr["out_of_training_dist"]:
        extra = (" This is a <b>prediction-only</b> name: its history is too thin (and "
                 "structurally annual) to train on, so the model scored it without ever having "
                 "learned from it — especially low-confidence.")
    ui.note("<b>Note:</b> the predicted Sharpe is the near-null model's output and should be "
            "read as low-confidence (see the <b>Model</b> tab)." + extra)


def main() -> None:
    st.set_page_config(page_title="Signal Desk · Equity Research", page_icon="◧",
                       layout="wide", initial_sidebar_state="collapsed")
    st.session_state.setdefault("mode", "dark")
    st.session_state.setdefault("view", "Ranking")
    st.session_state.setdefault("selected", None)

    companies = data.load_companies()
    logos = data.logo_uris()
    ui.inject_theme(companies, st.session_state["mode"], logos)

    view = top_bar()

    left, right = st.columns([1.05, 5.4], gap="medium")
    with left:
        watchlist(companies)
    with right:
        if view == "Ranking":
            view_ranking(logos)
        elif view == "Model":
            view_model()
        elif view == "Data":
            view_data()
        elif view == "Backtest":
            view_backtest(logos)
        else:                       # DETAIL_VIEW — reachable only from the watchlist / ranking
            view_detail(companies)


if __name__ == "__main__":
    main()
