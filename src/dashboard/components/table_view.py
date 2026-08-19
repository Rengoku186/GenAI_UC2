"""Sortable triage table ranking chunks by confidence."""

from __future__ import annotations
import streamlit as st
import pandas as pd
from typing import Any


def render_triage_table(report_data: dict[str, Any]) -> str | None:
    """Renders the interactive triage table and returns selected chunk_id for drilldown."""
    rows = report_data.get("ranked_triage_table", [])
    if not rows:
        st.warning("No triage data available in report.")
        return None

    df = pd.DataFrame(rows)

    # Filter controls
    col1, col2 = st.columns([2, 1])
    with col1:
        status_filter = st.multiselect(
            "Filter by Status:",
            options=["flagged_for_human_review", "auto_passed_after_refinement", "auto_passed", "in_progress"],
            default=["flagged_for_human_review", "auto_passed_after_refinement", "auto_passed"]
        )
    with col2:
        lang_filter = st.multiselect(
            "Filter by Language:",
            options=list(df["language"].unique()) if "language" in df else [],
            default=list(df["language"].unique()) if "language" in df else []
        )

    filtered_df = df.copy()
    if status_filter:
        filtered_df = filtered_df[filtered_df["status"].isin(status_filter)]
    if lang_filter:
        filtered_df = filtered_df[filtered_df["language"].isin(lang_filter)]

    st.markdown("### 📋 Chunks Triage Ranking (Lowest Confidence First)")
    st.caption("Human reviewers should prioritize chunks marked `flagged_for_human_review` or with lower confidence scores.")

    st.dataframe(
        filtered_df[[
            "chunk_id", "name", "language", "status", "confidence_score", "issue_count", "source_file", "line_range"
        ]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "chunk_id": st.column_config.TextColumn("Chunk ID", width="medium"),
            "status": st.column_config.TextColumn("Status", width="medium"),
            "confidence_score": st.column_config.ProgressColumn(
                "Confidence",
                format="%.2f",
                min_value=0.0,
                max_value=1.0,
                width="medium"
            ),
            "issue_count": st.column_config.NumberColumn("Issues Logged", width="small")
        }
    )

    # Selection for deep drilldown
    chunk_list = filtered_df["chunk_id"].tolist()
    if not chunk_list:
        return None

    selected = st.selectbox("Select a Chunk to Inspect Details & Diffs:", options=chunk_list, index=0)
    return selected
