"""Minimal, clean triage table component with subtle color pills."""

from __future__ import annotations
import streamlit as st
import pandas as pd
from typing import Any


def render_triage_table(report_data: dict[str, Any]) -> str | None:
    """Renders a clean, compact triage table and returns selected chunk_id."""
    rows = report_data.get("ranked_triage_table", [])
    if not rows:
        st.info("No triage records found.")
        return None

    # Map raw status to clean badge labels
    status_map = {
        "auto_passed": "Passed",
        "auto_passed_after_refinement": "Refined",
        "flagged_for_human_review": "Review"
    }

    display_rows = []
    for r in rows:
        raw_status = r.get("status", "unknown")
        display_rows.append({
            "Chunk": r.get("name", r.get("chunk_id")),
            "Chunk ID": r.get("chunk_id"),
            "Language": r.get("language", "").upper(),
            "Status": status_map.get(raw_status, raw_status),
            "Confidence": round(float(r.get("confidence_score", 0.0)), 2),
            "Source File": r.get("source_file"),
            "Lines": r.get("line_range")
        })

    df = pd.DataFrame(display_rows)

    # Minimal filter bar
    c1, c2 = st.columns([1, 1])
    with c1:
        status_filter = st.multiselect(
            "Filter Status:",
            options=["Passed", "Refined", "Review"],
            default=["Review", "Refined", "Passed"],
            label_visibility="collapsed"
        )
    with c2:
        lang_filter = st.multiselect(
            "Filter Language:",
            options=list(df["Language"].unique()),
            default=list(df["Language"].unique()),
            label_visibility="collapsed"
        )

    filtered_df = df.copy()
    if status_filter:
        filtered_df = filtered_df[filtered_df["Status"].isin(status_filter)]
    if lang_filter:
        filtered_df = filtered_df[filtered_df["Language"].isin(lang_filter)]

    # Render clean interactive dataframe
    st.dataframe(
        filtered_df[["Chunk", "Language", "Status", "Confidence", "Source File", "Lines"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Chunk": st.column_config.TextColumn("Chunk / Routine", width="medium"),
            "Language": st.column_config.TextColumn("Lang", width="small"),
            "Status": st.column_config.TextColumn("Status", width="small"),
            "Confidence": st.column_config.ProgressColumn(
                "Confidence",
                format="%.2f",
                min_value=0.0,
                max_value=1.0,
                width="small"
            ),
            "Source File": st.column_config.TextColumn("Source", width="medium"),
            "Lines": st.column_config.TextColumn("Lines", width="small")
        }
    )

    chunk_ids = filtered_df["Chunk ID"].tolist()
    chunk_labels = {r["Chunk ID"]: f"{r['Chunk']} ({r['Language']} - {r['Status']})" for r in display_rows}

    if not chunk_ids:
        return None

    selected = st.selectbox(
        "Select chunk to view code diff & business rules:",
        options=chunk_ids,
        format_func=lambda cid: chunk_labels.get(cid, cid),
        label_visibility="visible"
    )
    return selected
