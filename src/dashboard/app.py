"""Streamlit Web Application: Legacy Code Modernization Dashboard."""

from __future__ import annotations
import sys
import json
from pathlib import Path

# Ensure project root is on sys.path for Streamlit
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st

from src.dashboard.components.metrics_view import render_kpi_cards, render_distribution_charts
from src.dashboard.components.table_view import render_triage_table
from src.dashboard.components.diff_viewer import render_chunk_drilldown, render_full_file_view
from src.dashboard.components.graph_view import render_dependency_graph
from src.dashboard.components.knowledge_store_view import render_knowledge_store
from src.orchestrator.graph import run_pipeline

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Legacy Modernization Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Global Design System ──────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    /* ── Base Reset ── */
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        background-color: #f8fafc !important;
        color: #1e293b !important;
    }

    /* ── App background ── */
    .stApp { background-color: #f8fafc !important; }
    section[data-testid="stSidebar"] {
        background: #ffffff !important;
        border-right: 1px solid #e2e8f0 !important;
    }

    /* ── Sidebar title styling ── */
    .sidebar-logo {
        display: flex; align-items: center; gap: 10px;
        padding: 16px 0 20px 0;
        border-bottom: 1px solid #e2e8f0;
        margin-bottom: 20px;
    }
    .sidebar-logo-icon { font-size: 1.6rem; }
    .sidebar-logo-text { font-size: 1rem; font-weight: 700; color: #0f172a; line-height: 1.3; }
    .sidebar-logo-sub  { font-size: 0.72rem; color: #64748b; font-weight: 400; }

    .sidebar-section-label {
        font-size: 0.7rem; font-weight: 700; color: #94a3b8;
        text-transform: uppercase; letter-spacing: 0.08em;
        margin: 18px 0 6px 0;
    }

    /* ── Page header ── */
    .page-header {
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        border-radius: 14px;
        padding: 28px 32px;
        margin-bottom: 24px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 4px 20px rgba(15,23,42,0.12);
    }
    .page-header-title {
        font-size: 1.65rem; font-weight: 800;
        color: #ffffff; letter-spacing: -0.01em; margin-bottom: 4px;
    }
    .page-header-sub {
        font-size: 0.88rem; color: #94a3b8; font-weight: 400;
    }
    .header-badge {
        background: rgba(99,102,241,0.18);
        border: 1px solid rgba(99,102,241,0.4);
        color: #a5b4fc; border-radius: 20px;
        padding: 6px 14px; font-size: 0.78rem; font-weight: 600;
    }

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background: #f1f5f9;
        padding: 4px;
        border-radius: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 8px 18px;
        font-size: 0.875rem; font-weight: 500;
        border-radius: 7px; color: #475569;
        transition: all 0.2s ease;
    }
    .stTabs [aria-selected="true"] {
        background: #ffffff !important;
        color: #0f172a !important;
        font-weight: 600;
        box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    }

    /* ── Metric / dataframe containers ── */
    [data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 14px 18px;
    }

    /* ── Buttons ── */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #6366f1, #4f46e5) !important;
        border: none !important; border-radius: 8px !important;
        font-weight: 600 !important; color: #fff !important;
        padding: 10px 0 !important;
        box-shadow: 0 2px 8px rgba(99,102,241,0.35) !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button[kind="primary"]:hover {
        box-shadow: 0 4px 14px rgba(99,102,241,0.50) !important;
        transform: translateY(-1px) !important;
    }

    /* ── Section card wrapper ── */
    .section-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 16px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.04);
    }
    .section-title {
        font-size: 0.78rem; font-weight: 700; color: #64748b;
        text-transform: uppercase; letter-spacing: 0.07em;
        margin-bottom: 14px;
    }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────
def load_latest_or_selected_report(reports_dir: str = "outputs/evaluation_reports") -> dict | None:
    """Loads evaluation report JSON from disk."""
    rpath = Path(reports_dir)
    if not rpath.exists():
        return None

    report_files = sorted(list(rpath.glob("*.json")), key=lambda p: p.stat().st_mtime, reverse=True)
    if not report_files:
        return None

    selected_file = st.sidebar.selectbox(
        "Select Run:",
        options=report_files,
        format_func=lambda p: p.name,
        label_visibility="collapsed"
    )

    try:
        with open(selected_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        st.sidebar.error(f"Error loading report: {e}")
        return None


# ── Main App ──────────────────────────────────────────────────────────────────
def main():
    # ── Sidebar ──────────────────────────────────────────────────────────────
    st.sidebar.markdown("""
    <div class="sidebar-logo">
        <div class="sidebar-logo-icon">⚡</div>
        <div>
            <div class="sidebar-logo-text">Modernizer</div>
            <div class="sidebar-logo-sub">Legacy Code → Modern Services</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.sidebar.markdown('<div class="sidebar-section-label">🚀 Run Pipeline</div>', unsafe_allow_html=True)

    sample_dir = Path("data/legacy_source")
    available_sources = list(sample_dir.glob("*.*")) if sample_dir.exists() else []

    selected_sources = st.sidebar.multiselect(
        "Source files:",
        options=[str(p) for p in available_sources],
        default=[str(p) for p in available_sources],
        label_visibility="collapsed"
    )

    if st.sidebar.button("▶  Run Modernization", type="primary", use_container_width=True):
        if not selected_sources:
            st.sidebar.warning("Select at least one source file.")
        else:
            with st.spinner("Processing legacy code…"):
                run_pipeline(selected_sources)
            st.sidebar.success("✅ Run complete! Check outputs/modernized_code")
            st.rerun()

    st.sidebar.markdown('<div class="sidebar-section-label">📁 Evaluation Run</div>', unsafe_allow_html=True)
    report_data = load_latest_or_selected_report()

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        '<div style="font-size:0.72rem;color:#94a3b8;text-align:center;">GenAI · UC2 · Modernization</div>',
        unsafe_allow_html=True
    )

    # ── Header ───────────────────────────────────────────────────────────────
    run_label = ""
    if report_data:
        run_id = report_data.get("run_id", "")
        run_label = run_id[-8:] if run_id else "Latest"

    st.markdown(f"""
    <div class="page-header">
        <div>
            <div class="page-header-title">⚡ Autonomous Legacy Code Modernization</div>
            <div class="page-header-sub">COBOL · VB · Java  →  Modern Java 17+/21+ Microservices + JUnit 5 Test Suites</div>
        </div>
        <div class="header-badge">Run: {run_label or "—"}</div>
    </div>
    """, unsafe_allow_html=True)

    if not report_data:
        st.info("📭 No evaluation runs recorded yet. Click **▶ Run Modernization** in the sidebar to process legacy codebases.")
        return

    # ── KPI Cards ────────────────────────────────────────────────────────────
    render_kpi_cards(report_data)

    # ── Main Tabs ─────────────────────────────────────────────────────────────
    tab_full, tab_chunks, tab_graph, tab_ks = st.tabs([
        "📦  Whole Converted Services & Tests",
        "📋  Chunks Triage & Drilldown",
        "🕸  Dependency Graph",
        "📚  Agent Execution Log"
    ])

    with tab_full:
        render_full_file_view(report_data)

    with tab_chunks:
        selected_chunk = render_triage_table(report_data)
        if selected_chunk:
            render_chunk_drilldown(selected_chunk, report_data)

    with tab_graph:
        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown('<div class="section-title">Cross-Chunk Dependency Map</div>', unsafe_allow_html=True)
            render_dependency_graph(report_data)
        with c2:
            st.markdown('<div class="section-title">Status Distribution</div>', unsafe_allow_html=True)
            render_distribution_charts(report_data)

    with tab_ks:
        render_knowledge_store(report_data)


if __name__ == "__main__":
    main()
