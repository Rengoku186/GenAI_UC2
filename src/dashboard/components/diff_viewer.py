"""Chunk & full-file code modernization viewer — Modern Java 17+ output only."""

from __future__ import annotations
import streamlit as st
from typing import Any


def render_full_file_view(report_data: dict[str, Any]):
    """Renders the complete synthesized Java file, JUnit 5 test suite, and documentation."""
    synthesized = report_data.get("synthesized_full_files", {})
    if not synthesized:
        st.info("No full-file modernizations available. Run the pipeline first.")
        return

    source_files = list(synthesized.keys())
    selected_sf = st.selectbox(
        "Select Source File:",
        options=source_files,
        key="full_file_select"
    )

    if not selected_sf:
        return

    file_data = synthesized[selected_sf]
    java_name = file_data.get("java_class_name", "Service")

    tab_java, tab_tests, tab_doc = st.tabs([
        f"☕  Java Service  ({java_name}.java)",
        f"🧪  JUnit 5 Tests  ({java_name}Test.java)",
        "📄  Documentation",
    ])

    with tab_java:
        st.caption(f"Modernized Java 17+ service — converted from `{selected_sf}`")
        java_code = file_data.get("java_code", "")
        if java_code:
            st.code(java_code, language="java")
        else:
            st.info("No Java code synthesized for this file.")

    with tab_tests:
        st.caption(f"Auto-generated JUnit 5 test suite for `{java_name}`")
        java_tests = file_data.get("java_tests", "")
        if java_tests:
            st.code(java_tests, language="java")
        else:
            st.info("No test suite generated.")

    with tab_doc:
        doc_md = file_data.get("documentation_markdown")
        if doc_md:
            st.markdown(doc_md)
        else:
            st.info("No documentation generated for this module.")


def render_chunk_drilldown(chunk_id: str, report_data: dict[str, Any]):
    """Renders a focused code modernization view for a selected chunk."""
    chunk_details = report_data.get("chunk_details", {}).get(chunk_id)
    if not chunk_details:
        st.warning("No details available for the selected chunk.")
        return

    meta   = chunk_details.get("metadata", {})
    status = chunk_details.get("status", "unknown")
    confidence = chunk_details.get("confidence_score", 0.0)
    doc    = chunk_details.get("doc", {})
    code   = chunk_details.get("generated_code", {})
    tests  = chunk_details.get("tests", {})

    # ── Status banner ─────────────────────────────────────────────────────────
    status_cfg = {
        "auto_passed":                  ("#ecfdf5", "#10b981", "#065f46", "✅ Auto-Passed"),
        "auto_passed_after_refinement": ("#fffbeb", "#f59e0b", "#92400e", "🔄 Auto-Passed (Refined)"),
    }
    bg, border, txt, label = status_cfg.get(
        status, ("#fff1f2", "#f43f5e", "#9f1239", "⚠️ Human Review Needed")
    )

    st.markdown(f"""
    <div style="display:flex;justify-content:space-between;align-items:center;
                background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;
                padding:10px 16px;margin-top:10px;margin-bottom:12px;">
        <div>
            <span style="font-size:1.1rem;font-weight:700;color:#0f172a;">{meta.get('name', chunk_id)}</span>
            <span style="font-size:0.85rem;color:#64748b;margin-left:8px;">
                ({meta.get('source_file')}:{meta.get('line_start')}–{meta.get('line_end')})
            </span>
        </div>
        <div>
            <span style="background:{bg};border:1px solid {border};color:{txt};
                         padding:3px 10px;border-radius:12px;font-size:0.8rem;font-weight:600;margin-right:8px;">
                {label}
            </span>
            <span style="font-size:0.85rem;font-weight:600;color:#475569;">
                Confidence: {confidence:.2f}
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab_code, tab_rules, tab_tests = st.tabs([
        "☕  Modernized Java",
        "📋  Business Rules",
        "🧪  Test Verification",
    ])

    with tab_code:
        c1, c2 = st.columns(2)
        with c1:
            lang = meta.get("language", "java").lower()
            st.caption(f"Legacy Source ({lang.upper()}) — lines {meta.get('line_start')}–{meta.get('line_end')}")
            st.code(meta.get("raw_code", "// No legacy source"), language=lang)
        with c2:
            java_class = code.get("java_class_name") or "Service"
            version    = code.get("version", 1)
            st.caption(f"Modern Java 17+ — {java_class}.java (v{version})")
            st.code(code.get("target_java_code", "// No Java code generated"), language="java")

    with tab_rules:
        if doc:
            st.markdown(f"**Purpose:** {doc.get('purpose', 'N/A')}")
            rules = doc.get("business_rules", [])
            if rules:
                st.markdown("**Extracted Business Rules:**")
                for r in rules:
                    st.markdown(f"- {r}")
            cf = doc.get("control_flow")
            if cf:
                st.caption(f"**Control Flow:** {cf}")
        else:
            st.info("No documentation extracted for this chunk.")

    with tab_tests:
        if tests:
            t_col1, t_col2 = st.columns([1, 3])
            with t_col1:
                st.metric("Coverage", f"{tests.get('coverage_pct', 0.0):.0f}%")
                st.write(f"Passed: **{tests.get('pass_count', 0)}** | Failed: **{tests.get('fail_count', 0)}**")
            with t_col2:
                st.caption("JUnit 5 Test Suite")
                st.code(tests.get("java_test_code", "// No JUnit tests generated"), language="java")
        else:
            st.info("No test suite generated for this chunk.")
