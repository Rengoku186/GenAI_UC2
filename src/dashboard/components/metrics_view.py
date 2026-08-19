"""KPI and Metrics visualizer component for Streamlit dashboard."""

from __future__ import annotations
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from typing import Any


def render_kpi_cards(report_data: dict[str, Any]):
    """Renders top-level summary metrics cards."""
    status_summary = report_data.get("status_summary", {})
    total_chunks = report_data.get("total_chunks", 0)
    avg_confidence = report_data.get("overall_average_confidence", 0.0)
    flagged_count = status_summary.get("flagged_for_human_review", 0)
    auto_passed = status_summary.get("auto_passed", 0)
    refined_passed = status_summary.get("auto_passed_after_refinement", 0)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Total Chunks Migrated",
            value=total_chunks,
            help="Total number of discrete code chunks processed"
        )
    with col2:
        st.metric(
            label="Auto-Passed (Direct)",
            value=auto_passed,
            delta=f"{(auto_passed / max(1, total_chunks) * 100):.1f}%",
            delta_color="normal"
        )
    with col3:
        st.metric(
            label="Auto-Passed (Refined)",
            value=refined_passed,
            delta=f"{(refined_passed / max(1, total_chunks) * 100):.1f}%",
            delta_color="off"
        )
    with col4:
        st.metric(
            label="Flagged for Review",
            value=flagged_count,
            delta=f"-{flagged_count}" if flagged_count > 0 else "0",
            delta_color="inverse"
        )


def render_distribution_charts(report_data: dict[str, Any]):
    """Renders visual status breakdown and confidence distribution."""
    status_summary = report_data.get("status_summary", {})
    
    col1, col2 = st.columns(2)

    with col1:
        labels = ["Auto-Passed", "Auto-Passed after Refinement", "Flagged for Review", "In Progress"]
        values = [
            status_summary.get("auto_passed", 0),
            status_summary.get("auto_passed_after_refinement", 0),
            status_summary.get("flagged_for_human_review", 0),
            status_summary.get("in_progress", 0)
        ]
        colors = ["#22c55e", "#eab308", "#ef4444", "#94a3b8"]

        fig_pie = go.Figure(
            data=[
                go.Pie(
                    labels=labels,
                    values=values,
                    hole=0.45,
                    marker=dict(colors=colors),
                    textinfo="label+percent"
                )
            ]
        )
        fig_pie.update_layout(
            title_text="Migration Quality Breakdown",
            margin=dict(t=40, b=10, l=10, r=10),
            height=300
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        rows = report_data.get("ranked_triage_table", [])
        if rows:
            df_scores = [r["confidence_score"] for r in rows]
            fig_hist = px.histogram(
                df_scores,
                nbins=10,
                title="Confidence Score Distribution (0.0 - 1.0)",
                labels={"value": "Confidence Score", "count": "Chunks"},
                color_discrete_sequence=["#3b82f6"]
            )
            fig_hist.update_layout(
                margin=dict(t=40, b=10, l=10, r=10),
                height=300,
                xaxis_title="Confidence Score",
                yaxis_title="Chunk Count"
            )
            st.plotly_chart(fig_hist, use_container_width=True)
        else:
            st.info("No chunk confidence data available.")
