"""Chunk detail and code/doc diff viewer for Streamlit dashboard."""

from __future__ import annotations
import streamlit as st
from typing import Any


def render_chunk_drilldown(chunk_id: str, report_data: dict[str, Any]):
    """Renders deep drilldown view for a selected chunk."""
    chunk_details = report_data.get("chunk_details", {}).get(chunk_id)
    if not chunk_details:
        st.error(f"Details not found for chunk ID: {chunk_id}")
        return

    meta = chunk_details.get("metadata", {})
    status = chunk_details.get("status", "unknown")
    confidence = chunk_details.get("confidence_score", 0.0)
    retries = chunk_details.get("retry_count", 0)
    doc = chunk_details.get("doc")
    code = chunk_details.get("generated_code")
    tests = chunk_details.get("tests")
    eval_trail = chunk_details.get("eval_trail", [])

    # Status Banner
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.markdown(f"#### 🔍 Chunk: `{chunk_id}` ({meta.get('name')})")
        st.caption(f"Source: `{meta.get('source_file')}` | Lines: `{meta.get('line_start')}-{meta.get('line_end')}` | Lang: `{meta.get('language')}`")
    with col2:
        if status == "auto_passed":
            st.success("✔ State: AUTO-PASSED")
        elif status == "auto_passed_after_refinement":
            st.warning("🔄 State: AUTO-PASSED (REFINED)")
        else:
            st.error("🚩 State: HUMAN REVIEW NEEDED")
    with col3:
        st.metric("Confidence Score", f"{confidence:.2f}", delta=f"Retries: {retries}")

    # Tabs for different perspectives
    tab_code, tab_doc, tab_test, tab_eval = st.tabs([
        "💻 Code Comparison",
        "📄 Business Rules & Docs",
        "🧪 Unit Tests & Sandbox Run",
        "📜 Full Evaluation Trail"
    ])

    with tab_code:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**Original Legacy Code ({meta.get('language', '').upper()})**")
            st.code(meta.get("raw_code", "# No raw code"), language=meta.get("language", "text"))
        with c2:
            st.markdown(f"**Modern Python Service (v{code.get('version', 1) if code else 1})**")
            if code and code.get("target_code"):
                st.code(code.get("target_code"), language="python")
            else:
                st.info("No generated Python code yet.")

    with tab_doc:
        if doc:
            st.markdown(f"**Purpose & Business Intent (v{doc.get('version', 1)}):**")
            st.write(doc.get("purpose", ""))

            st.markdown("**Documented Business Rules:**")
            for r in doc.get("business_rules", []):
                st.markdown(f"- {r}")

            st.markdown("**Control Flow:**")
            st.info(doc.get("control_flow", ""))

            c_in, c_out = st.columns(2)
            with c_in:
                st.markdown("**Inputs:**")
                st.json(doc.get("inputs", []))
            with c_out:
                st.markdown("**Outputs:**")
                st.json(doc.get("outputs", []))
        else:
            st.info("No documentation generated yet.")

    with tab_test:
        if tests:
            t_col1, t_col2 = st.columns(2)
            with t_col1:
                st.metric("Passed Tests", tests.get("pass_count", 0))
            with t_col2:
                st.metric("Failed Tests", tests.get("fail_count", 0))

            st.markdown("**Pytest Unit Test Suite:**")
            st.code(tests.get("test_code", "# No tests"), language="python")

            if tests.get("execution_output"):
                st.markdown("**Sandbox Execution Output:**")
                st.text_area("Console logs", tests.get("execution_output"), height=150)
        else:
            st.info("No unit tests generated yet.")

    with tab_eval:
        st.markdown("**Evaluation History Trail (Append-Only Log):**")
        if eval_trail:
            for idx, ev in enumerate(eval_trail, 1):
                with st.expander(
                    f"Step {idx}: {ev.get('stage')} | Score: {ev.get('score')} | Passed: {ev.get('passed')}",
                    expanded=(not ev.get("passed"))
                ):
                    st.write(f"**Version Evaluated:** v{ev.get('version_evaluated', 1)}")
                    st.write(f"**Needs Human Review:** `{ev.get('needs_human_review', False)}`")
                    if ev.get("issues"):
                        st.error("**Identified Issues:**\n" + "\n".join([f"- {i}" for i in ev.get("issues", [])]))
                    if ev.get("suggestions"):
                        st.info("**Actionable Suggestions:**\n" + "\n".join([f"- {s}" for s in ev.get("suggestions", [])]))
        else:
            st.info("No evaluation trail recorded.")
