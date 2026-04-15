from __future__ import annotations

import os
from typing import Any

import pandas as pd
import requests
import streamlit as st


API_BASE = os.getenv("TRADEOS_API_URL", "http://127.0.0.1:8000").rstrip("/")
PAGES = [
    ("dashboard", "Dashboard"),
    ("pipeline", "Pipeline"),
    ("arbitration", "Arbitration"),
    ("strategy_pool", "Strategy Pool"),
    ("audit", "Audit"),
    ("feedback", "Feedback"),
]


def _setup_page() -> None:
    st.set_page_config(
        page_title="TradeOS Console",
        page_icon="T",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
    <style>
        .stApp {
            background: linear-gradient(180deg, #08111f 0%, #0d1726 35%, #f3f6f9 35%, #f6f8fb 100%);
        }
        .top-shell {
            background: linear-gradient(135deg, #0f172a 0%, #12253f 55%, #184a7a 100%);
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 22px;
            padding: 22px 24px 18px 24px;
            color: white;
            box-shadow: 0 20px 60px rgba(8,17,31,0.28);
            margin-bottom: 18px;
        }
        .eyebrow {
            text-transform: uppercase;
            letter-spacing: 0.14em;
            font-size: 12px;
            opacity: 0.75;
            margin-bottom: 6px;
        }
        .hero-title {
            font-size: 34px;
            font-weight: 700;
            margin-bottom: 8px;
        }
        .hero-sub {
            font-size: 15px;
            max-width: 980px;
            opacity: 0.9;
            line-height: 1.5;
        }
        .page-card {
            background: white;
            border: 1px solid #dbe4ee;
            border-radius: 18px;
            padding: 18px 18px 14px 18px;
            box-shadow: 0 8px 30px rgba(15,23,42,0.06);
            margin-bottom: 16px;
        }
        .metric-card {
            background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
            border: 1px solid #d8e3ef;
            border-radius: 16px;
            padding: 16px 18px;
            min-height: 120px;
            box-shadow: 0 10px 26px rgba(15,23,42,0.05);
        }
        .metric-label {
            text-transform: uppercase;
            letter-spacing: 0.12em;
            color: #5d6b7b;
            font-size: 11px;
            margin-bottom: 8px;
            font-weight: 700;
        }
        .metric-value {
            font-size: 28px;
            font-weight: 700;
            color: #112236;
            margin-bottom: 5px;
        }
        .metric-sub {
            color: #607184;
            font-size: 13px;
            line-height: 1.45;
        }
        .section-title {
            font-size: 22px;
            font-weight: 700;
            color: #102033;
            margin-bottom: 8px;
        }
        .section-sub {
            color: #5c6b7a;
            font-size: 14px;
            margin-bottom: 16px;
        }
        .nav-caption {
            color: #dfe8f5;
            font-size: 13px;
            margin-top: 8px;
        }
        .empty-box {
            background: #f5f8fc;
            border: 1px dashed #c4d2e2;
            border-radius: 16px;
            padding: 18px;
            color: #617486;
        }
        .tag {
            display: inline-block;
            background: #e8f1fb;
            color: #1c4a73;
            border-radius: 999px;
            padding: 4px 10px;
            font-size: 12px;
            margin-right: 6px;
            margin-bottom: 6px;
        }
    </style>
    """,
        unsafe_allow_html=True,
    )


def _init_state() -> None:
    defaults = {
        "page": "dashboard",
        "result_pipeline_full": None,
        "result_pipeline_live": None,
        "result_arbitration": None,
        "result_arbitration_portfolio": None,
        "result_strategy_pool": None,
        "result_audit_feedback_task": None,
        "result_audit_feedback_status": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _read_page() -> str:
    query_page = st.query_params.get("page", st.session_state.get("page", "dashboard"))
    valid_pages = {key for key, _ in PAGES}
    if query_page not in valid_pages:
        query_page = "dashboard"
    st.session_state.page = query_page
    return query_page


def _set_page(page: str) -> None:
    st.session_state.page = page
    st.query_params["page"] = page


def _request(method: str, path: str, *, params: dict[str, Any] | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any] | None:
    url = f"{API_BASE}{path}"
    try:
        response = requests.request(method, url, params=params, json=payload, timeout=45)
        try:
            body = response.json()
        except Exception:
            body = {"raw_text": response.text}
        if response.status_code >= 400:
            st.error(f"{method} {path} failed: HTTP {response.status_code}")
            st.json(body)
            return None
        return body if isinstance(body, dict) else {"data": body}
    except requests.RequestException as exc:
        st.error(f"{method} {path} failed: {exc}")
        return None


def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    return _request("GET", path, params=params)


def _post(path: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    return _request("POST", path, payload=payload)


def _nav_button(page_key: str, label: str) -> None:
    button_type = "primary" if st.session_state.page == page_key else "secondary"
    if st.button(label, key=f"nav-{page_key}", use_container_width=True, type=button_type):
        _set_page(page_key)
        st.rerun()


def _render_shell() -> None:
    st.markdown(
        """
    <div class="top-shell">
        <div class="eyebrow">Frozen Product Surface</div>
        <div class="hero-title">TradeOS Console</div>
        <div class="hero-sub">
            This console only calls the frozen product API. Every button, form, result panel, and read-only table below is mapped to a real backend endpoint verified against the current application.
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )
    nav_cols = st.columns(len(PAGES))
    for col, (key, label) in zip(nav_cols, PAGES):
        with col:
            _nav_button(key, label)
    st.markdown(
        f'<div class="nav-caption">API base: <code>{API_BASE}</code> · Current page: <strong>{dict(PAGES)[st.session_state.page]}</strong></div>',
        unsafe_allow_html=True,
    )


def _json_box(data: Any, *, expanded: bool = True, title: str = "Raw Response") -> None:
    if data is None:
        st.markdown('<div class="empty-box">No result yet. Submit the form to see the live response.</div>', unsafe_allow_html=True)
        return
    with st.expander(title, expanded=expanded):
        st.json(data)


def _safe_df(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    return pd.json_normalize(rows)


def _tags(items: list[str]) -> None:
    if not items:
        st.caption("No tags")
        return
    html = "".join(f'<span class="tag">{item}</span>' for item in items)
    st.markdown(html, unsafe_allow_html=True)


def render_dashboard() -> None:
    st.markdown('<div class="page-card"><div class="section-title">Dashboard</div><div class="section-sub">Health, module readiness, auth read views, and the product surface summary users can verify before running actions.</div></div>', unsafe_allow_html=True)
    health = _get("/health") or {}
    version = _get("/version") or {}
    modules = _get("/system/modules") or {}
    metric_cols = st.columns(4)
    with metric_cols[0]:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Health</div><div class="metric-value">{health.get("status", "n/a")}</div><div class="metric-sub">Environment: {health.get("environment", "n/a")}</div></div>', unsafe_allow_html=True)
    with metric_cols[1]:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Version</div><div class="metric-value">{version.get("version", "n/a")}</div><div class="metric-sub">API: {version.get("api", "n/a")}</div></div>', unsafe_allow_html=True)
    with metric_cols[2]:
        module_items = modules.get("modules", [])
        ready_count = len([item for item in module_items if item.get("status") == "ready"])
        st.markdown(f'<div class="metric-card"><div class="metric-label">Modules Ready</div><div class="metric-value">{ready_count}</div><div class="metric-sub">Total modules listed: {len(module_items)}</div></div>', unsafe_allow_html=True)
    with metric_cols[3]:
        services = health.get("services", {})
        service_count = len([name for name, ok in services.items() if ok])
        st.markdown(f'<div class="metric-card"><div class="metric-label">Core Services</div><div class="metric-value">{service_count}</div><div class="metric-sub">Healthy services reported by /health</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="page-card"><div class="section-title">Visible Modules</div><div class="section-sub">These labels are visible from the first screen and match the frozen backend capabilities.</div></div>', unsafe_allow_html=True)
    module_cols = st.columns(6)
    for col, (_, label) in zip(module_cols, PAGES):
        with col:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Panel</div><div class="metric-value" style="font-size:20px;">{label}</div><div class="metric-sub">Directly reachable from the first-screen navigation.</div></div>', unsafe_allow_html=True)
    left, right = st.columns([1.4, 1.0])
    with left:
        st.subheader("System modules")
        modules_df = _safe_df(modules.get("modules", []))
        if not modules_df.empty:
            st.dataframe(modules_df, use_container_width=True, hide_index=True)
        else:
            st.info("No module rows returned.")
        _json_box(modules, expanded=False, title="system/modules raw response")
    with right:
        st.subheader("Auth users")
        users = _get("/api/v1/auth/users") or {}
        users_df = _safe_df(users.get("users", []))
        if not users_df.empty:
            st.dataframe(users_df, use_container_width=True, hide_index=True)
        else:
            st.info("No user rows returned.")
        _json_box(users, expanded=False, title="auth/users raw response")


def render_pipeline() -> None:
    st.markdown('<div class="page-card"><div class="section-title">Pipeline</div><div class="section-sub">Two real entry points are available here: <code>/api/v1/pipeline/run-full</code> and <code>/api/v1/pipeline/run-live</code>.</div></div>', unsafe_allow_html=True)
    tab_full, tab_live = st.tabs(["Run Full", "Run Live"])
    with tab_full:
        with st.form("pipeline-full-form"):
            col1, col2, col3 = st.columns(3)
            symbol = col1.text_input("Symbol", value="AAPL")
            direction = col2.selectbox("Direction", ["LONG", "SHORT", "FLAT"], index=0)
            regime = col3.selectbox("Regime", ["trending_up", "trending_down", "ranging", "volatile", "unknown"], index=0)
            col4, col5 = st.columns(2)
            confidence = col4.slider("Confidence", 0.0, 1.0, 0.75, 0.05)
            strength = col5.slider("Strength", 0.0, 1.0, 0.60, 0.05)
            submit = st.form_submit_button("Run Pipeline", use_container_width=True, type="primary")
        if submit:
            st.session_state.result_pipeline_full = _post("/api/v1/pipeline/run-full", {"symbol": symbol, "direction": direction, "confidence": confidence, "strength": strength, "regime": regime})
        result = st.session_state.result_pipeline_full
        left, right = st.columns([1.1, 1.0])
        with left:
            st.subheader("Summary")
            if result:
                phases = result.get("phases", [])
                decision = result.get("decision") or {}
                plan = result.get("plan") or {}
                st.success(f"Status: {result.get('status', 'n/a')}")
                st.write(f"Task ID: `{result.get('task_id', 'n/a')}`")
                st.write(f"Symbol: `{result.get('symbol', 'n/a')}`")
                st.write(f"Phases returned: `{len(phases)}`")
                if decision:
                    st.write(f"Decision bias: `{decision.get('bias', 'n/a')}`")
                    st.write(f"Decision confidence: `{decision.get('confidence', 'n/a')}`")
                if plan:
                    st.write(f"Final quantity: `{plan.get('final_quantity', 'n/a')}`")
                    st.write(f"Veto triggered: `{plan.get('veto_triggered', 'n/a')}`")
            else:
                st.info("Use the form to run the synchronous pipeline DTO path.")
        with right:
            st.subheader("Phase table")
            if result and result.get("phases"):
                st.dataframe(_safe_df(result["phases"]), use_container_width=True, hide_index=True)
            else:
                st.info("No phase rows yet.")
        _json_box(result, expanded=False)
    with tab_live:
        with st.form("pipeline-live-form"):
            col1, col2, col3, col4 = st.columns(4)
            symbol = col1.text_input("Symbol", value="CL=F")
            timeframe = col2.selectbox("Timeframe", ["1d", "1h", "1m"], index=0)
            lookback = col3.number_input("Lookback", min_value=30, max_value=365, value=90, step=10)
            news_limit = col4.number_input("News Limit", min_value=1, max_value=20, value=6, step=1)
            submit_live = st.form_submit_button("Run Live Pipeline", use_container_width=True, type="primary")
        if submit_live:
            st.session_state.result_pipeline_live = _post("/api/v1/pipeline/run-live", {"symbol": symbol, "timeframe": timeframe, "lookback": int(lookback), "news_limit": int(news_limit)})
        result = st.session_state.result_pipeline_live
        left, right = st.columns([1.0, 1.1])
        with left:
            st.subheader("Live decision")
            if result:
                decision = result.get("decision") or {}
                plan = result.get("plan") or {}
                audit = result.get("audit") or {}
                st.success("Live pipeline completed")
                st.write(f"Bias: `{decision.get('bias', 'n/a')}`")
                st.write(f"Direction: `{decision.get('bias_direction', 'n/a')}`")
                st.write(f"Confidence: `{decision.get('confidence', 'n/a')}`")
                st.write(f"Final quantity: `{plan.get('final_quantity', 'n/a')}`")
                st.write(f"Decision record: `{audit.get('decision_record_id', 'n/a')}`")
            else:
                st.info("Run the real-data path to see live data, six-module participation, decision, plan, and audit summary.")
        with right:
            st.subheader("Six-module matrix")
            modules_df = _safe_df((result or {}).get("modules", []))
            if not modules_df.empty:
                st.dataframe(modules_df, use_container_width=True, hide_index=True)
            else:
                st.info("No live module rows yet.")
        _json_box(result, expanded=False)


def render_arbitration() -> None:
    st.markdown('<div class="page-card"><div class="section-title">Arbitration</div><div class="section-sub">This page exposes both arbitration entry points. The backend response is flat, so the UI reads the response directly instead of assuming a nested <code>decision</code> object.</div></div>', unsafe_allow_html=True)
    tab_single, tab_portfolio = st.tabs(["Single Signal", "Portfolio Entry"])
    with tab_single:
        with st.form("arbitration-single-form"):
            col1, col2, col3 = st.columns(3)
            symbol = col1.text_input("Symbol", value="AAPL")
            direction = col2.selectbox("Direction", ["LONG", "SHORT", "FLAT"], index=0)
            regime = col3.selectbox("Regime", ["trending_up", "trending_down", "ranging", "volatile", "unknown"], index=0)
            confidence = st.slider("Confidence", 0.0, 1.0, 0.80, 0.05)
            strength = st.slider("Strength", 0.0, 1.0, 0.60, 0.05)
            col4, col5, col6, col7 = st.columns(4)
            fundamental_score = col4.slider("Fundamental score", 0.0, 1.0, 0.55, 0.05)
            macro_score = col5.slider("Macro score", 0.0, 1.0, 0.60, 0.05)
            sentiment_score = col6.slider("Sentiment score", 0.0, 1.0, 0.58, 0.05)
            orderflow_score = col7.slider("OrderFlow score", 0.0, 1.0, 0.57, 0.05)
            submit = st.form_submit_button("Run Arbitration", use_container_width=True, type="primary")
        if submit:
            st.session_state.result_arbitration = _post("/api/v1/arbitration/run", {"symbol": symbol, "direction": direction, "confidence": confidence, "strength": strength, "regime": regime, "fundamental_score": fundamental_score, "macro_score": macro_score, "sentiment_score": sentiment_score, "orderflow_score": orderflow_score})
        result = st.session_state.result_arbitration
        left, right = st.columns([0.9, 1.1])
        with left:
            st.subheader("Decision summary")
            if result:
                st.success("Arbitration completed")
                st.write(f"Decision ID: `{result.get('decision_id', 'n/a')}`")
                st.write(f"Bias: `{result.get('bias', 'n/a')}`")
                st.write(f"Confidence: `{result.get('confidence', 'n/a')}`")
                st.write(f"Signal count: `{result.get('signal_count', 'n/a')}`")
                st.write("Rules applied")
                _tags(result.get("rules_applied", []))
            else:
                st.info("Submit the single-signal arbitration form.")
        with right:
            st.subheader("Rationale rows")
            rationale_df = _safe_df((result or {}).get("rationale", []))
            if not rationale_df.empty:
                st.dataframe(rationale_df, use_container_width=True, hide_index=True)
            else:
                st.info("No rationale rows yet.")
        _json_box(result, expanded=False)
    with tab_portfolio:
        with st.form("arbitration-portfolio-form"):
            col1, col2 = st.columns(2)
            portfolio_id = col1.text_input("Portfolio ID", value="AAPL-SP")
            symbol = col2.text_input("Symbol", value="AAPL")
            proposal_one = st.columns(4)
            p1_direction = proposal_one[0].selectbox("Trend direction", ["LONG", "SHORT", "FLAT"], index=0)
            p1_strength = proposal_one[1].slider("Trend strength", 0.0, 1.0, 0.72, 0.05)
            p1_confidence = proposal_one[2].slider("Trend confidence", 0.0, 1.0, 0.76, 0.05)
            p1_weight = proposal_one[3].slider("Trend weight", 0.0, 1.0, 0.55, 0.05)
            proposal_two = st.columns(4)
            p2_direction = proposal_two[0].selectbox("Mean reversion direction", ["LONG", "SHORT", "FLAT"], index=2)
            p2_strength = proposal_two[1].slider("Mean strength", 0.0, 1.0, 0.35, 0.05)
            p2_confidence = proposal_two[2].slider("Mean confidence", 0.0, 1.0, 0.48, 0.05)
            p2_weight = proposal_two[3].slider("Mean weight", 0.0, 1.0, 0.45, 0.05)
            submit_portfolio = st.form_submit_button("Run Portfolio Arbitration", use_container_width=True, type="primary")
        if submit_portfolio:
            st.session_state.result_arbitration_portfolio = _post("/api/v1/arbitration/run-portfolio", {"portfolio_id": portfolio_id, "symbol": symbol, "proposals": [{"proposal_id": "trend-proposal", "strategy_id": "trend", "aggregate_direction": p1_direction, "aggregate_strength": p1_strength, "aggregate_confidence": p1_confidence, "portfolio_weight": p1_weight, "bundle_count": 1}, {"proposal_id": "mean-reversion-proposal", "strategy_id": "mean_reversion", "aggregate_direction": p2_direction, "aggregate_strength": p2_strength, "aggregate_confidence": p2_confidence, "portfolio_weight": p2_weight, "bundle_count": 1}]})
        result = st.session_state.result_arbitration_portfolio
        if result:
            st.success("Portfolio arbitration completed")
            cols = st.columns(4)
            cols[0].metric("Bias", result.get("bias", "n/a"))
            cols[1].metric("Confidence", result.get("confidence", "n/a"))
            cols[2].metric("Signal count", result.get("signal_count", "n/a"))
            cols[3].metric("Source", result.get("source", "n/a"))
        else:
            st.info("Submit the portfolio arbitration form.")
        _json_box(result, expanded=False)


def render_strategy_pool() -> None:
    st.markdown('<div class="page-card"><div class="section-title">Strategy Pool</div><div class="section-sub">The backend exposes <code>/api/v1/strategy-pool/propose</code> as an immediate DTO call. This page shows the submit action and the returned portfolio arbitration bundle.</div></div>', unsafe_allow_html=True)
    with st.form("strategy-pool-form"):
        col1, col2, col3 = st.columns(3)
        portfolio_id = col1.text_input("Portfolio ID", value="NVDA-SP")
        symbol = col2.text_input("Symbol", value="NVDA")
        weight_method = col3.selectbox("Weight method", ["equal", "ir", "risk_parity", "manual"], index=0)
        alpha_cols = st.columns(4)
        alpha_direction = alpha_cols[0].selectbox("Alpha direction", ["LONG", "SHORT", "FLAT"], index=0)
        alpha_strength = alpha_cols[1].slider("Alpha strength", 0.0, 1.0, 0.70, 0.05)
        alpha_confidence = alpha_cols[2].slider("Alpha confidence", 0.0, 1.0, 0.78, 0.05)
        alpha_weight = alpha_cols[3].slider("Alpha weight", 0.0, 1.0, 0.60, 0.05)
        hedge_cols = st.columns(4)
        hedge_direction = hedge_cols[0].selectbox("Hedge direction", ["LONG", "SHORT", "FLAT"], index=2)
        hedge_strength = hedge_cols[1].slider("Hedge strength", 0.0, 1.0, 0.30, 0.05)
        hedge_confidence = hedge_cols[2].slider("Hedge confidence", 0.0, 1.0, 0.45, 0.05)
        hedge_weight = hedge_cols[3].slider("Hedge weight", 0.0, 1.0, 0.40, 0.05)
        submit = st.form_submit_button("Submit Strategy Pool", use_container_width=True, type="primary")
    if submit:
        st.session_state.result_strategy_pool = _post("/api/v1/strategy-pool/propose", {"portfolio_id": portfolio_id, "symbol": symbol, "weight_method": weight_method, "proposals": [{"proposal_id": "alpha-proposal", "strategy_id": "alpha_core", "aggregate_direction": alpha_direction, "aggregate_strength": alpha_strength, "aggregate_confidence": alpha_confidence, "portfolio_weight": alpha_weight, "bundles": [{"bundle_id": "alpha-bundle", "source_strategy_id": "alpha_core", "symbol": symbol, "direction": alpha_direction, "strength": alpha_strength, "confidence": alpha_confidence}]}, {"proposal_id": "hedge-proposal", "strategy_id": "hedge_overlay", "aggregate_direction": hedge_direction, "aggregate_strength": hedge_strength, "aggregate_confidence": hedge_confidence, "portfolio_weight": hedge_weight, "bundles": [{"bundle_id": "hedge-bundle", "source_strategy_id": "hedge_overlay", "symbol": symbol, "direction": hedge_direction, "strength": hedge_strength, "confidence": hedge_confidence}]}]})
    result = st.session_state.result_strategy_pool
    left, right = st.columns([0.85, 1.15])
    with left:
        st.subheader("Submit result")
        if result:
            st.success(result.get("message", "Strategy pool proposal completed"))
            st.write(f"Task ID: `{result.get('task_id', 'n/a')}`")
            st.write(f"Status: `{result.get('status', 'n/a')}`")
            decision = result.get("decision") or {}
            st.write(f"Decision bias: `{decision.get('bias', 'n/a')}`")
            st.write(f"Composite direction: `{decision.get('composite_direction', 'n/a')}`")
        else:
            st.info("Submit a strategy pool proposal to see the returned decision bundle.")
    with right:
        st.subheader("Returned proposals")
        decision = (result or {}).get("decision") or {}
        proposals_df = _safe_df(decision.get("proposals", []))
        if not proposals_df.empty:
            st.dataframe(proposals_df, use_container_width=True, hide_index=True)
        else:
            st.info("No proposal rows yet.")
    _json_box(result, expanded=False)


def render_audit() -> None:
    st.markdown('<div class="page-card"><div class="section-title">Audit</div><div class="section-sub">Read-only queries over append-only records. This page intentionally avoids editable forms that would imply write access.</div></div>', unsafe_allow_html=True)
    tab_decisions, tab_risk, tab_feedback, tab_auth = st.tabs(["Decisions", "Risk", "Feedback", "Auth"])
    with tab_decisions:
        col1, col2 = st.columns(2)
        symbol = col1.text_input("Decision symbol filter", value="")
        limit = col2.number_input("Decision limit", min_value=1, max_value=100, value=10, step=1)
        if st.button("Load decision records", use_container_width=True, key="audit-decisions-load", type="primary"):
            params = {"limit": int(limit)}
            if symbol.strip():
                params["symbol"] = symbol.strip()
            st.session_state.audit_decisions = _get("/api/v1/audit/decisions", params=params) or {}
        result = st.session_state.get("audit_decisions")
        df = _safe_df((result or {}).get("items", []))
        if not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No decision audit rows loaded.")
        _json_box(result, expanded=False, title="decision audit raw response")
    with tab_risk:
        col1, col2 = st.columns(2)
        symbol = col1.text_input("Risk symbol filter", value="", key="risk-symbol")
        limit = col2.number_input("Risk limit", min_value=1, max_value=100, value=10, step=1, key="risk-limit")
        if st.button("Load risk records", use_container_width=True, key="audit-risk-load", type="primary"):
            params = {"limit": int(limit)}
            if symbol.strip():
                params["symbol"] = symbol.strip()
            st.session_state.audit_risk = _get("/api/v1/audit/risk", params=params) or {}
        result = st.session_state.get("audit_risk")
        df = _safe_df((result or {}).get("items", []))
        if not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No risk audit rows loaded.")
        _json_box(result, expanded=False, title="risk audit raw response")
    with tab_feedback:
        col1, col2 = st.columns(2)
        symbol = col1.text_input("Feedback symbol filter", value="", key="feedback-symbol")
        limit = col2.number_input("Feedback limit", min_value=1, max_value=100, value=10, step=1, key="feedback-limit")
        if st.button("Load feedback records", use_container_width=True, key="audit-feedback-load", type="primary"):
            params = {"limit": int(limit)}
            if symbol.strip():
                params["symbol"] = symbol.strip()
            st.session_state.audit_feedback = _get("/api/v1/audit/feedback", params=params) or {}
        result = st.session_state.get("audit_feedback")
        df = _safe_df((result or {}).get("items", []))
        if not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Feedback is allowed to be empty. This view should show an empty-state instead of pretending the backend wrote data.")
        _json_box(result, expanded=False, title="feedback audit raw response")
    with tab_auth:
        col1, col2 = st.columns(2)
        limit = col1.number_input("Auth audit limit", min_value=1, max_value=200, value=20, step=1, key="auth-limit")
        resource = col2.text_input("Resource filter", value="", key="auth-resource")
        if st.button("Load auth audit + users", use_container_width=True, key="auth-load", type="primary"):
            audit_params = {"limit": int(limit)}
            if resource.strip():
                audit_params["resource"] = resource.strip()
            st.session_state.auth_audit = _get("/api/v1/auth/audit", params=audit_params) or {}
            st.session_state.auth_users = _get("/api/v1/auth/users") or {}
        audit_result = st.session_state.get("auth_audit")
        users_result = st.session_state.get("auth_users")
        left, right = st.columns(2)
        with left:
            df = _safe_df((audit_result or {}).get("entries", []))
            if not df.empty:
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No auth audit rows loaded.")
        with right:
            df = _safe_df((users_result or {}).get("users", []))
            if not df.empty:
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No user rows loaded.")
        _json_box(audit_result, expanded=False, title="auth audit raw response")


def render_feedback() -> None:
    st.markdown('<div class="page-card"><div class="section-title">Feedback</div><div class="section-sub">Task-style submit and status polling for <code>/api/v1/audit/feedback/tasks</code>. This is intentionally not shown as a direct write-success flow.</div></div>', unsafe_allow_html=True)
    left, right = st.columns(2)
    with left:
        with st.form("feedback-task-form"):
            feedback_type = st.selectbox("Feedback type", ["all", "loss_amplification", "win_fade", "regime_mismatch", "confidence_mismatch", "low_signal_count"], index=0)
            symbol = st.text_input("Symbol filter", value="AAPL")
            submit = st.form_submit_button("Submit Feedback Scan", use_container_width=True, type="primary")
        if submit:
            payload = {"feedback_type": feedback_type}
            if symbol.strip():
                payload["symbol"] = symbol.strip()
            st.session_state.result_audit_feedback_task = _post("/api/v1/audit/feedback/tasks", payload)
        task_result = st.session_state.result_audit_feedback_task
        if task_result:
            st.success("Feedback task submitted")
            st.write(f"Task ID: `{task_result.get('task_id', 'n/a')}`")
            st.write(f"Status: `{task_result.get('status', 'n/a')}`")
            st.write(task_result.get("message", ""))
        else:
            st.info("Submit a scan task first. Then use the right-side panel to query its status.")
        _json_box(task_result, expanded=False, title="feedback task submit raw response")
    with right:
        default_task_id = ""
        task_submit = st.session_state.result_audit_feedback_task or {}
        if task_submit.get("task_id"):
            default_task_id = task_submit["task_id"]
        task_id = st.text_input("Task ID", value=default_task_id, key="feedback-task-id")
        if st.button("Load task status", use_container_width=True, key="feedback-task-load", type="primary"):
            if task_id.strip():
                st.session_state.result_audit_feedback_status = _get(f"/api/v1/audit/feedback/tasks/{task_id.strip()}")
            else:
                st.warning("Enter a task id first.")
        status_result = st.session_state.result_audit_feedback_status
        if status_result:
            st.success(f"Task status: {status_result.get('status', 'n/a')}")
            st.write(f"Feedback count: `{status_result.get('feedback_count', 'n/a')}`")
            if status_result.get("summary"):
                st.write(status_result["summary"])
            feedback_df = _safe_df(status_result.get("feedbacks", []))
            if not feedback_df.empty:
                st.dataframe(feedback_df, use_container_width=True, hide_index=True)
            else:
                st.info("This task returned no feedback rows.")
        else:
            st.info("No task status loaded yet.")
        _json_box(status_result, expanded=False, title="feedback task status raw response")


def main() -> None:
    _setup_page()
    _init_state()
    _read_page()
    _render_shell()
    page = st.session_state.page
    if page == "dashboard":
        render_dashboard()
    elif page == "pipeline":
        render_pipeline()
    elif page == "arbitration":
        render_arbitration()
    elif page == "strategy_pool":
        render_strategy_pool()
    elif page == "audit":
        render_audit()
    elif page == "feedback":
        render_feedback()
    else:
        st.error(f"Unknown page: {page}")
    with st.expander("Advanced Details", expanded=False):
        st.write("Current page query params")
        st.json(dict(st.query_params))
        st.write("Session state keys")
        st.json(sorted(st.session_state.keys()))
        st.write("Frontend capability boundary")
        st.code("This console only reads from and writes to product API endpoints. It does not import core trading phases directly and does not expose any registry truth write path.")
