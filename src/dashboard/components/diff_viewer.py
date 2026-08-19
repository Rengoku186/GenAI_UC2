"""Chunk & full-file code modernization viewer with test suites and documentation."""

from __future__ import annotations
import streamlit as st
from typing import Any


def render_full_file_view(report_data: dict[str, Any]):
    """Renders the complete synthesized file modernization, test suite, and documentation."""
    synthesized = report_data.get("synthesized_full_files", {})
    if not synthesized:
        st.info("No full-file modernizations available.")
        return

    source_files = list(synthesized.keys())
    selected_sf = st.selectbox(
        "Select Source File to View Full Modernized Codebase:",
        options=source_files,
        key="full_file_select"
    )

    if not selected_sf:
        return

    file_data = synthesized[selected_sf]
    mod_name = file_data.get("module_name", "service")
    java_name = file_data.get("java_class_name", "Service")

    # Tabs for Whole Converted Service, Documentation, & Test Suites
    tab_doc, tab_full_py, tab_full_java, tab_full_tests = st.tabs([
        "📄 Complete Documentation",
        f"🐍 Whole Python Service (`{mod_name}.py`)",
        f"☕ Whole Java Service (`{java_name}.java`)",
        "🧪 End-to-End Test Suites"
    ])

    with tab_doc:
        doc_md = file_data.get("documentation_markdown")
        if doc_md:
            st.markdown(doc_md)
        else:
            st.info("No documentation generated for this module.")

    with tab_full_py:
        st.caption(f"Complete standalone modernized Python service converted from `{selected_sf}`")
        st.code(file_data.get("python_code", "# No python code"), language="python")

    with tab_full_java:
        st.caption(f"Complete standalone modernized Java service converted from `{selected_sf}`")
        st.code(file_data.get("java_code", "// No java code"), language="java")

    with tab_full_tests:
        test_sub1, test_sub2 = st.tabs([f"🐍 Pytest Suite (`test_{mod_name}.py`)", f"☕ JUnit 5 Suite (`{java_name}Test.java`)"])
        with test_sub1:
            st.caption("End-to-end Python test suite verifying all business rules, calculations, and boundary conditions")
            st.code(file_data.get("python_tests", "# No tests"), language="python")
        with test_sub2:
            st.caption("End-to-end Java JUnit 5 test suite verifying service parity")
            st.code(file_data.get("java_tests", "// No tests"), language="java")


def render_chunk_drilldown(chunk_id: str, report_data: dict[str, Any]):
    """Renders focused code modernization view for selected chunk."""
    chunk_details = report_data.get("chunk_details", {}).get(chunk_id)
    if not chunk_details:
        st.warning("No details available for selected chunk.")
        return

    meta = chunk_details.get("metadata", {})
    status = chunk_details.get("status", "unknown")
    confidence = chunk_details.get("confidence_score", 0.0)
    retries = chunk_details.get("retry_count", 0)
    doc = chunk_details.get("doc", {})
    code = chunk_details.get("generated_code", {})
    tests = chunk_details.get("tests", {})

    status_bg = "#ecfdf5" if status == "auto_passed" else ("#fffbeb" if status == "auto_passed_after_refinement" else "#fff1f2")
    status_border = "#10b981" if status == "auto_passed" else ("#f59e0b" if status == "auto_passed_after_refinement" else "#f43f5e")
    status_text = "#065f46" if status == "auto_passed" else ("#92400e" if status == "auto_passed_after_refinement" else "#9f1239")
    status_label = "Auto-Passed" if status == "auto_passed" else ("Auto-Passed (Refined)" if status == "auto_passed_after_refinement" else "Human Review Needed")

    st.markdown(f"""
    <div style="display: flex; justify-content: space-between; align-items: center; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px 16px; margin-top: 10px; margin-bottom: 12px;">
        <div>
            <span style="font-size: 1.1rem; font-weight: 700; color: #0f172a;">{meta.get('name', chunk_id)}</span>
            <span style="font-size: 0.85rem; color: #64748b; margin-left: 8px;">({meta.get('source_file')}:{meta.get('line_start')}-{meta.get('line_end')})</span>
        </div>
        <div>
            <span style="background: {status_bg}; border: 1px solid {status_border}; color: {status_text}; padding: 3px 10px; border-radius: 12px; font-size: 0.8rem; font-weight: 600; margin-right: 8px;">
                {status_label}
            </span>
            <span style="font-size: 0.85rem; font-weight: 600; color: #475569;">Confidence: {confidence:.2f}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab_code, tab_rules, tab_tests = st.tabs([
        "Modernized Code",
        "Business Rules",
        "Test Verification"
    ])

    with tab_code:
        target_lang = st.radio("Target Modern Architecture:", ["Python 3.11+", "Java 17+"], horizontal=True, label_visibility="collapsed")

        c1, c2 = st.columns(2)
        with c1:
            st.caption(f"Original Legacy Source ({meta.get('language', '').upper()})")
            st.code(meta.get("raw_code", "# No legacy source available"), language=meta.get("language", "text"))

        with c2:
            if target_lang == "Python 3.11+":
                st.caption(f"Modern Python Service (`{code.get('module_name', 'service')}.py` - v{code.get('version', 1)})")
                st.code(code.get("target_code", "# No python code generated"), language="python")
            else:
                st.caption(f"Modern Java Service (`{code.get('java_class_name', 'Service')}.java`)")
                st.code(code.get("target_java_code", "// No java code generated"), language="java")

    with tab_rules:
        if doc:
            st.markdown(f"**Purpose:** {doc.get('purpose', 'N/A')}")
            rules = doc.get("business_rules", [])
            if rules:
                st.markdown("**Extracted Business Logic Rules:**")
                for r in rules:
                    st.markdown(f"- {r}")
            if doc.get("control_flow"):
                st.caption(f"**Control Flow:** {doc.get('control_flow')}")
        else:
            st.info("No documentation extracted.")

    with tab_tests:
        if tests:
            t_col1, t_col2 = st.columns([1, 3])
            with t_col1:
                st.metric("Test Coverage", f"{tests.get('coverage_pct', 0.0):.0f}%")
                st.write(f"Passed: **{tests.get('pass_count', 0)}** | Failed: **{tests.get('fail_count', 0)}**")
            
            with t_col2:
                test_view = st.radio("Test Suite:", ["Pytest (Python)", "JUnit 5 (Java)"], horizontal=True, label_visibility="collapsed")
                if test_view == "Pytest (Python)":
                    st.code(tests.get("test_code", "# No tests generated"), language="python")
                else:
                    st.code(tests.get("java_test_code", "// No JUnit tests generated"), language="java")
        else:
            st.info("No unit test suite generated.")
