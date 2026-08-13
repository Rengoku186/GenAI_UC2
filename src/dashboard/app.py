import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # adds project root

import streamlit as st
import pandas as pd
from src.knowledge_store.store import KnowledgeStore

st.set_page_config(page_title="Legacy Conversion — Review Dashboard", layout="wide")

@st.cache_resource
def load_store():
    return KnowledgeStore()

store = load_store()

st.title("Phase 1 — Review Dashboard")
st.caption("Flags issues for human SMEs")

docs = store.docs
evals = store.get_all_evals()
flagged = store.get_flagged_items()

col1, col2, col3 = st.columns(3)
col1.metric("Chunks documented", len(docs))
col2.metric("Chunks evaluated", len(evals))
col3.metric("Flagged for review", len(flagged))

st.divider()

tab_overview, tab_flagged, tab_browse = st.tabs(["Overview", "Flagged items", "Browse all chunks"])

with tab_overview:
    if evals:
        rows = []
        for chunk_id, e in evals.items():
            rows.append({
                "chunk_id": chunk_id,
                "score": e.get("overall_score", 0.0),
                "needs_refinement": e.get("needs_refinement", False),
                "issue_count": len(e.get("issues", [])),
            })
        df = pd.DataFrame(rows).sort_values("score")
        st.bar_chart(df.set_index("chunk_id")["score"])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No evaluations yet. Run the Phase 1 pipeline first.")

with tab_flagged:
    if not flagged:
        st.success("Nothing flagged — all chunks passed evaluation.")
    else:
        for item in flagged:
            cid = item.get("chunk_id", "")
            score = item.get("overall_score", 0.0)
            with st.expander(f"🚩 {cid} — score {score:.0f}"):
                issues = item.get("issues", [])
                if issues:
                    for issue in issues:
                        st.markdown(f"- {issue}")
                else:
                    st.write(item.get("reason", "No specific issues recorded."))

                doc = docs.get(cid)
                if doc:
                    st.markdown("**Generated documentation:**")
                    st.markdown(f"*Summary:* {doc.get('summary', '(empty)')}")
                    st.markdown(f"*Business logic:* {doc.get('business_logic', '(empty)')}")
                    if doc.get("inputs"):
                        st.markdown(f"*Inputs:* {', '.join(doc['inputs'])}")
                    if doc.get("outputs"):
                        st.markdown(f"*Outputs:* {', '.join(doc['outputs'])}")

with tab_browse:
    search = st.text_input("Filter by chunk id")
    for chunk_id, doc in docs.items():
        if search and search.lower() not in chunk_id.lower():
            continue
        eval_data = evals.get(chunk_id, {})
        score = eval_data.get("overall_score")
        score_label = f"{score:.0f}" if score is not None else "not evaluated"
        with st.expander(f"{chunk_id}  (score: {score_label})"):
            st.markdown(f"**Summary:** {doc.get('summary', '')}")
            st.markdown(f"**Business logic:** {doc.get('business_logic', '')}")
            if doc.get("inputs"):
                st.markdown(f"**Inputs:** {', '.join(doc['inputs'])}")
            if doc.get("outputs"):
                st.markdown(f"**Outputs:** {', '.join(doc['outputs'])}")
            if doc.get("dependencies_used"):
                st.markdown(f"**Dependencies used:** {', '.join(doc['dependencies_used'])}")
            if eval_data.get("issues"):
                st.markdown("**Issues:**")
                for issue in eval_data["issues"]:
                    st.markdown(f"- {issue}")