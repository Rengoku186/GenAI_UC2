"""Streamlit Web Application: Legacy Code Modernization Dashboard."""

from __future__ import annotations
import json
from pathlib import Path
import streamlit as st

from src.dashboard.components.metrics_view import render_kpi_cards, render_distribution_charts
from src.dashboard.components.table_view import render_triage_table
from src.dashboard.components.diff_viewer import render_chunk_drilldown
from src.dashboard.components.graph_view import render_dependency_graph
from src.orchestrator.graph import run_pipeline

# Configure Streamlit Page
st.set_page_config(
    page_title="Legacy Code Modernization Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for polished aesthetics
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1e293b;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #64748b;
        margin-bottom: 1.5rem;
    }
    .stMetric {
        background-color: #f8fafc;
        padding: 12px 16px;
        border-radius: 8px;
        border: 1px solid #e2e8f0;
    }
</style>
""", unsafe_allow_html=True)


def load_latest_or_selected_report(reports_dir: str = "outputs/evaluation_reports") -> dict | None:
    """Loads evaluation report JSON from disk."""
    rpath = Path(reports_dir)
    if not rpath.exists():
        return None

    report_files = sorted(list(rpath.glob("*.json")), key=lambda p: p.stat().st_mtime, reverse=True)
    if not report_files:
        return None

    # Sidebar selection
    st.sidebar.markdown("### 📁 Select Evaluation Run")
    selected_file = st.sidebar.selectbox(
        "Report Run:",
        options=report_files,
        format_func=lambda p: p.name
    )

    try:
        with open(selected_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        st.sidebar.error(f"Error loading report: {e}")
        return None


def main():
    st.markdown('<div class="main-title">⚡ Autonomous Legacy Modernization Dashboard</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Multi-Agent Pipeline Orchestration & Triage Observability (COBOL / VB / Java → Python)</div>', unsafe_allow_html=True)

    # Sidebar: Pipeline execution controls
    st.sidebar.markdown("### 🚀 Execute Pipeline")
    sample_dir = Path("data/legacy_source")
    available_sources = list(sample_dir.glob("*.*")) if sample_dir.exists() else []

    selected_sources = st.sidebar.multiselect(
        "Select Source Files:",
        options=[str(p) for p in available_sources],
        default=[str(p) for p in available_sources]
    )

    if st.sidebar.button("Run Full Modernization Pipeline", type="primary"):
        if not selected_sources:
            st.sidebar.warning("Please select at least one legacy source file.")
        else:
            with st.spinner("Executing multi-agent LangGraph workflow..."):
                final_state = run_pipeline(selected_sources)
                st.sidebar.success("Pipeline Run Completed!")
                st.rerun()

    report_data = load_latest_or_selected_report()

    if not report_data:
        st.info("No evaluation reports found. Click 'Run Full Modernization Pipeline' in the sidebar or execute `python -m src.orchestrator.graph` to generate a run.")
        return

    # Section 1: KPI Overview & Charts
    render_kpi_cards(report_data)
    st.markdown("---")
    render_distribution_charts(report_data)
    st.markdown("---")

    # Section 2: Main Content Tabs (Triage Table, Graph Topology)
    tab_triage, tab_graph = st.tabs(["📊 Chunks Triage & Diffs", "🕸 Dependency Graph Topology"])

    with tab_triage:
        selected_chunk = render_triage_table(report_data)
        if selected_chunk:
            st.markdown("---")
            render_chunk_drilldown(selected_chunk, report_data)

    with tab_graph:
        render_dependency_graph(report_data)


if __name__ == "__main__":
    main()
