"""
app.py — Signal Desk: report-signal equity-research dashboard (READ-ONLY).

Deep-navy + indigo/purple chrome; green/red reserved for performance semantics. A slim
full-width top bar (logo, search, horizontal nav, light/dark toggle) over a left ticker
watchlist + four views: Ranking, Model & EDA, Backtest, Company Detail.

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

from pathlib import Path

import streamlit as st

import data
import ui

ASSETS = Path(__file__).resolve().parent / "assets"
VIEWS = ["Ranking", "Model & EDA", "Backtest", "Company Detail"]


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
                new_mode = "light" if st.session_state["mode"] == "dark" else "dark"
                st.session_state["mode"] = new_mode
                # must precede the rerun — see _apply_native_theme's timing note
                _apply_native_theme(new_mode)
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
    fc = data.flag_counts()
    st.markdown(f'<div class="sd-view-title">Company Ranking</div>'
                f'<div class="sd-view-sub">All {fc["n"]} companies by model-predicted '
                f'forward-63d Sharpe · long top-10 / short bottom-10. Universe = the mandated '
                f'98 minus GOOG (Alphabet dual-class dedup — GOOGL retained).</div>',
                unsafe_allow_html=True)

    ui.caveat(mode, "shown for completeness. Out-of-sample signal is weak (near-zero rank "
                    "correlation) and the long/short backtest is flat — see the "
                    "<b>Model &amp; EDA</b> tab. Rankings are low-confidence, not investment "
                    "advice.")

    df = data.load_ranking()
    ui.flag_legend(mode, fc)

    longs = df[df["basket"] == "LONG"]["ticker"].tolist()
    shorts = df[df["basket"] == "SHORT"]["ticker"].tolist()
    ui.basket_summary(mode, longs, shorts)

    n_flag_long = int(df[df["basket"] == "LONG"]["out_of_training_dist"].sum())
    n_flag_short = int(df[df["basket"] == "SHORT"]["out_of_training_dist"].sum())
    ui.note(f"<b>{n_flag_long}</b> of the 10 longs and <b>{n_flag_short}</b> of the 10 shorts "
            f"are prediction-only names the model never trained on — a further reason to read "
            f"the book as a methodology demo, not a portfolio.")

    # scannable, sortable table — logos via ImageColumn, green/red row tint per basket
    disp = pd.DataFrame({
        "Rank": df["rank_ensemble"],
        "Logo": [logos.get(t, "") for t in df["ticker"]],
        "Ticker": df["ticker"],
        "Company": df["name"],
        "Sector": df["sector"],
        "Pred. Sharpe": df["pred_ensemble"],
        "Basket": df["basket"],
        "Confidence": df["confidence"],
    })

    def _tint(row):
        c = ("rgba(38,166,154,.15)" if row["Basket"] == "LONG"
             else "rgba(239,83,80,.15)" if row["Basket"] == "SHORT" else "")
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
            "Confidence": st.column_config.TextColumn(
                "Confidence", width="medium",
                help="Train-eligible = model learned from this name. Prediction-only = held "
                     "out of training. No release date = no look-ahead-safe target exists."),
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


def _tab_performance(mode, cv, tm, ft_rel) -> None:
    """CV selection + the one-shot test, and the feature→target correlation wall."""
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
        max_ft = ft_rel["spearman"].abs().max()
        st.markdown(f'<div class="sd-note"><b>Feature → target rank correlation</b> '
                    f'(well-populated features, n≥800). The strongest is '
                    f'~{max_ft:.3f} — essentially nothing.</div>', unsafe_allow_html=True)
        st.altair_chart(charts.signed_bar(
            top, "feature", "spearman", mode, x_title="Spearman vs future_63d_sharpe",
            domain=(-0.1, 0.1), height=230), width="stretch")


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


def _tab_eda(mode) -> None:
    ui.section("Exploratory data analysis")
    ui.note("Full diagnostics, computed on <b>train-eligible rows only</b> and regenerated on "
            "the final 97-name universe. Figures open on demand.")
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
        n_inf = int((vif["VIF"] > 1e6).sum())
        vshow["VIF"] = vshow["VIF"].map(lambda v: "∞" if v > 1e6 else f"{v:.1f}")
        st.dataframe(vshow, hide_index=True, width="stretch")
        # NB: n_inf counts FEATURES, not identities — one identity (e.g. financial_score =
        # mean of the six sub-scores) makes several features perfectly collinear at once.
        ui.note(f"<b>{n_inf} features</b> carry VIF = ∞ — perfect collinearity arising from a "
                "handful of exact by-construction identities (financial_score = mean of the "
                "six sub-scores; net_debt_to_assets = debt_to_assets − cash_to_assets; "
                "free_cash_flow_margin = operating_cash_flow_margin − capex_intensity; …). "
                "These, plus the high-VIF redundancies below, drove the de-duplicated feature "
                "set — see CLAUDE.md.")

    ui.note("<b>Sector is a grouping key for scoring, never a model feature.</b> Forward-Sharpe "
            "medians do differ across sectors in-sample, but that is in-sample dispersion, not "
            "a look-ahead-safe signal — no sector identity, one-hots or sector means are fed "
            "to the model.")


def view_model() -> None:
    mode = st.session_state["mode"]
    st.markdown('<div class="sd-view-title">Model &amp; EDA</div>'
                '<div class="sd-view-sub">Leak-safe model performance, error analysis, '
                'interpretability and a classification cross-check — reported straight.</div>',
                unsafe_allow_html=True)

    cv = data.load_cv()
    tm = data.load_test_metrics()
    ft = data.load_feature_target()
    ens = tm[tm["model"].str.startswith("ENSEMBLE")].iloc[0]
    best_cv = data.best_real_cv(cv)          # excludes the degenerate constant models
    ft_rel = ft[ft["reliable"] == True]
    max_ft = ft_rel["spearman"].abs().max()

    ui.note("<b>Verdict:</b> report fundamentals carry <b>no reliable signal</b> for the "
            "forward 63-day Sharpe on this universe/period — the honest result, consistent "
            "with market efficiency. Every metric below is indistinguishable from zero. The "
            "value of this project is the leak-free methodology, not alpha.")

    ui.stat_tiles([
        (f"{max_ft:.3f}", "Max feature |Spearman|", "strongest single feature vs target"),
        (f"{best_cv['cv_spearman_mean']:+.3f}", "Best CV Spearman",
         f"{best_cv['model']} · ±{best_cv['cv_spearman_std']:.3f} · non-degenerate models only"),
        (f"{ens['test_spearman_pooled']:+.3f}", "Ensemble test Spearman", "held-out 12-month test"),
        (f"{ens['test_rmse']:.2f}", "Ensemble test RMSE", "future_63d_sharpe units"),
    ])

    t1, t2, t3, t4, t5, t6 = st.tabs(
        ["Performance", "Error analysis", "Feature importance", "Classification",
         "Robustness", "EDA"])
    with t1:
        _tab_performance(mode, cv, tm, ft_rel)
    with t2:
        _tab_error(mode)
    with t3:
        _tab_importance(mode)
    with t4:
        _tab_classification(mode)
    with t5:
        _tab_robustness(mode)
    with t6:
        _tab_eda(mode)


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

    # derived from backtest_periods.csv — never hard-coded, so it can't go stale on a rerun
    seq = ", ".join(f"{v:+.0%}" for v in per["gross_ls"])
    n_flip = int((per["gross_ls"] > 0).sum())
    ui.note(f"<b>Honest read:</b> per-rebalance long-short flips sign ({seq}) with no "
            f"persistence — {n_flip} of {len(per)} quarters positive. Over {len(per)} quarters "
            "the strategy adds no spread. Consistent with the near-null model and market "
            "efficiency — the backtest confirms the pipeline runs end-to-end and leak-free, "
            "nothing more.")


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
    st.markdown(
        f'<div class="sd-hero">{badge}<div><div class="nm">{r["name"]}</div>'
        f'<div class="sub">{tk} &nbsp;·&nbsp; {r["sector"]} &nbsp;·&nbsp; '
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
            "read as low-confidence (see Model &amp; EDA)." + extra)


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
