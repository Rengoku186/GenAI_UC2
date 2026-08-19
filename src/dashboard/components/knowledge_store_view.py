"""Agent Execution Knowledge Store — reads from the .knowledge_store file on disk."""

from __future__ import annotations
from pathlib import Path
from typing import Any

import streamlit as st

from src.utils.knowledge_store import (
    KNOWLEDGE_STORE_PATH,
    read_knowledge_store,
    parse_runs_from_knowledge_store,
)


def render_knowledge_store(report_data: dict[str, Any]) -> None:
    """Renders the knowledge store tab by reading the .knowledge_store file."""

    st.markdown("""
    <style>
    .ks-run-header {
        background: #1e293b;
        color: #f1f5f9;
        border-radius: 10px;
        padding: 14px 20px;
        font-family: 'JetBrains Mono', 'Fira Code', monospace;
        font-size: 0.8rem;
        line-height: 1.6;
        margin-bottom: 12px;
        white-space: pre-wrap;
        word-break: break-word;
        box-shadow: 0 2px 10px rgba(15,23,42,0.15);
    }
    .ks-file-path {
        font-size: 0.72rem; color: #64748b;
        font-family: monospace; margin-bottom: 10px;
    }
    .ks-empty {
        background: #f8fafc; border: 1px dashed #cbd5e1;
        border-radius: 10px; padding: 28px 24px;
        text-align: center; color: #64748b;
    }
    </style>
    """, unsafe_allow_html=True)

    ks_path = KNOWLEDGE_STORE_PATH
    abs_path = ks_path.resolve()

    # ── File path indicator ───────────────────────────────────────────────────
    st.markdown(
        f'<div class="ks-file-path">📄 Knowledge store: <code>{abs_path}</code></div>',
        unsafe_allow_html=True
    )

    # ── Controls row ──────────────────────────────────────────────────────────
    col_a, col_b, col_c = st.columns([2, 1, 1])

    with col_a:
        search_q = st.text_input(
            "Search:", placeholder="Filter by agent name, chunk_id, score…",
            label_visibility="collapsed"
        )
    with col_b:
        show_mode = st.radio(
            "View:", ["By Run", "Full File"], horizontal=True,
            label_visibility="collapsed"
        )
    with col_c:
        if ks_path.exists():
            raw_content = read_knowledge_store(ks_path)
            st.download_button(
                label="⬇ Download .knowledge_store",
                data=raw_content or "",
                file_name=".knowledge_store",
                mime="text/plain",
                use_container_width=True,
            )

    st.markdown("---")

    # ── Empty state ───────────────────────────────────────────────────────────
    if not ks_path.exists():
        st.markdown("""
        <div class="ks-empty">
            <div style="font-size:2rem;margin-bottom:8px;">📭</div>
            <div style="font-weight:600;color:#334155;margin-bottom:4px;">.knowledge_store not found</div>
            <div style="font-size:0.85rem;">
                Run the pipeline via <strong>▶ Run Modernization</strong> in the sidebar.<br>
                A <code>.knowledge_store</code> file will be created automatically in the project root.
            </div>
        </div>
        """, unsafe_allow_html=True)
        return

    raw_content = read_knowledge_store(ks_path) or ""

    # Apply search filter to raw content lines
    if search_q.strip():
        q = search_q.strip().lower()
        filtered_lines = [ln for ln in raw_content.splitlines() if q in ln.lower()]
        display_content = "\n".join(filtered_lines)
        st.caption(f"🔎 Showing **{len(filtered_lines)}** matching lines for `{search_q}`")
    else:
        display_content = raw_content

    # ── View: Full File ───────────────────────────────────────────────────────
    if show_mode == "Full File":
        st.code(display_content, language="text")
        return

    # ── View: By Run ─────────────────────────────────────────────────────────
    runs = parse_runs_from_knowledge_store(ks_path)

    if not runs:
        st.code(display_content or "(empty)", language="text")
        return

    st.caption(f"**{len(runs)}** run(s) recorded in `.knowledge_store`")

    for i, run in enumerate(runs):
        run_id  = run.get("run_id", "unknown")
        ts      = run.get("timestamp", "")
        label   = f"{'🕐' if i > 0 else '🟢'} Run: {run_id}  |  {ts}"

        with st.expander(label, expanded=(i == 0)):
            block = run.get("raw_block", "")

            # Apply search highlight inside expander
            if search_q.strip():
                q = search_q.strip().lower()
                matched = [ln for ln in block.splitlines() if q in ln.lower()]
                if matched:
                    st.caption(f"{len(matched)} matching line(s) in this run:")
                    st.code("\n".join(matched), language="text")
                else:
                    st.caption("No matches in this run.")
            else:
                st.code(block, language="text")
