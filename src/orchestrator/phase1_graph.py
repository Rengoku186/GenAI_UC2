"""Phase 1 LangGraph Orchestrator: Legacy Code Understanding Pipeline.

Orchestrates the full Phase 1 workflow:
  Scanner -> Documenter -> Evaluator -> (Refine / Flag) -> Next Chunk -> [END]

Handles dependency-ordered chunk processing with iterative refinement loops,
configurable retry budgets, structured logging, and graceful error isolation
so that a single chunk failure never crashes the entire pipeline.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from langgraph.graph import StateGraph, START, END

from src.agents.documenter import document_chunk, should_document_chunk
from src.agents.evaluator import evaluate_chunk_doc, PASS_THRESHOLD
from src.agents.splitter import create_chunk_from_node_data, split_chunk_if_oversized
from src.knowledge_store.store import KnowledgeStore
from src.schemas import Chunk, ChunkDoc, EvalResult
from src.state import PipelineState
from src.tools.cycle_detector import prepare_processing_graph
from src.tools.dependency_scanner import scan_project

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

MAX_REFINEMENT_RETRIES = 3

# ============================================================================
# Knowledge Store (singleton for pipeline lifetime)
# ============================================================================

_store: Optional[KnowledgeStore] = None


def _get_store() -> KnowledgeStore:
    """Lazy-initialised singleton KnowledgeStore."""
    global _store
    if _store is None:
        _store = KnowledgeStore()
    return _store


def reset_store(storage_dir: str = ".knowledge_store") -> None:
    """Reset the store singleton (useful for testing or fresh runs)."""
    global _store
    _store = KnowledgeStore(storage_dir=storage_dir)


# ============================================================================
# Node: Scanner
# ============================================================================

def scanner_node(state: PipelineState) -> Dict[str, Any]:
    """Scan source files, build dependency graph, split into processable chunks.

    Performs:
      1. Multi-language dependency scanning across all input files.
      2. Cycle condensation via Tarjan SCC to produce a DAG.
      3. Topological ordering for dependency-respecting processing.
      4. Oversized chunk splitting for LLM context window compliance.
    """
    file_paths = state.get("file_paths", [])
    if not file_paths:
        logger.warning("scanner_node: no file_paths provided in state")
        return {
            "chunks": [],
            "processing_order": [],
            "current_chunk": None,
        }

    logger.info("Scanner: analysing %d file(s)", len(file_paths))
    t0 = time.perf_counter()

    raw_graph = scan_project(file_paths)
    condensed_dag, processing_order = prepare_processing_graph(raw_graph)

    chunks_list: List[Dict[str, Any]] = []
    chunk_ids_seen: set = set()

    for node_id in condensed_dag.nodes:
        node_data = condensed_dag.nodes[node_id]
        real_id = str(node_data.get("id", node_id))
        try:
            chunk = create_chunk_from_node_data(real_id, node_data)
            split_chunks = split_chunk_if_oversized(chunk)
            for sc in split_chunks:
                if sc.id not in chunk_ids_seen:
                    chunks_list.append(sc.model_dump())
                    chunk_ids_seen.add(sc.id)
        except Exception:
            logger.exception("Scanner: failed to create chunk for node '%s'", real_id)

    # Build processing order from condensed DAG order, falling back to chunk list order
    if processing_order:
        # Ensure all split chunk IDs are in the order list
        order_set = set(processing_order)
        final_order = [cid for cid in processing_order if cid in chunk_ids_seen]
        for cid in chunk_ids_seen:
            if cid not in order_set:
                final_order.append(cid)
    else:
        final_order = [c["id"] for c in chunks_list]

    current = final_order[0] if final_order else None

    elapsed = time.perf_counter() - t0
    logger.info(
        "Scanner: produced %d chunk(s) in %.2fs, processing order has %d entries",
        len(chunks_list), elapsed, len(final_order),
    )

    return {
        "chunks": chunks_list,
        "processing_order": final_order,
        "current_chunk": current,
        "docs": state.get("docs", {}),
        "eval_scores": state.get("eval_scores", {}),
        "eval_issues": state.get("eval_issues", {}),
        "refine_count": state.get("refine_count", {}),
        "flagged_items": state.get("flagged_items", []),
    }


# ============================================================================
# Node: Documenter
# ============================================================================

def documenter_node(state: PipelineState) -> Dict[str, Any]:
    """Generate semantic documentation for the current chunk.

    Triages trivial boilerplate chunks (fast-path) and supports evaluator
    critique injection for iterative refinement passes.
    """
    cid = state.get("current_chunk")
    if not cid:
        return {}

    chunks = state.get("chunks", [])
    chunk_data = next((c for c in chunks if c["id"] == cid), None)
    if not chunk_data:
        logger.warning("documenter_node: chunk '%s' not found in state", cid)
        return {}

    chunk = Chunk.model_validate(chunk_data)
    docs = dict(state.get("docs", {}))
    store = _get_store()

    # Gather upstream dependency docs for context
    dep_docs: List[ChunkDoc] = []
    for dep_id in chunk.depends_on:
        if dep_id in docs:
            try:
                dep_docs.append(ChunkDoc.model_validate(docs[dep_id]))
            except Exception:
                logger.debug("documenter_node: skipping invalid dep doc for '%s'", dep_id)

    # Triage: skip trivial boilerplate to save LLM tokens
    if not should_document_chunk(chunk):
        logger.debug("documenter_node: skipping boilerplate chunk '%s'", cid)
        doc = ChunkDoc(
            chunk_id=cid,
            summary=f"Structural routine: {chunk.name}",
            inputs=[],
            outputs=[],
            business_logic="Standard structural or control exit routine.",
            dependencies_used=[],
        )
    else:
        # Check if this is a refinement pass (evaluator critique available)
        eval_issues = state.get("eval_issues", {}).get(cid)
        prev_doc_data = docs.get(cid)
        prev_doc = ChunkDoc.model_validate(prev_doc_data) if prev_doc_data else None

        try:
            doc = document_chunk(
                chunk=chunk,
                dep_docs=dep_docs,
                eval_issues=eval_issues,
                previous_doc=prev_doc,
            )
        except Exception:
            logger.exception("documenter_node: LLM call failed for chunk '%s'", cid)
            doc = ChunkDoc(
                chunk_id=cid,
                summary="",
                inputs=[],
                outputs=[],
                business_logic="[DOCUMENTATION FAILED: unexpected error during generation]",
                dependencies_used=[],
            )

    docs[cid] = doc.model_dump()
    store.save_doc(doc)
    return {"docs": docs}


# ============================================================================
# Node: Evaluator
# ============================================================================

def evaluator_node(state: PipelineState) -> Dict[str, Any]:
    """Evaluate documentation quality using 4-parameter rubric.

    Records scores and categorised issues for routing decisions.
    """
    cid = state.get("current_chunk")
    if not cid:
        return {}

    chunks = state.get("chunks", [])
    chunk_data = next((c for c in chunks if c["id"] == cid), None)
    docs = state.get("docs", {})
    doc_data = docs.get(cid)

    if not chunk_data or not doc_data:
        logger.warning("evaluator_node: missing chunk or doc for '%s'", cid)
        return {}

    chunk = Chunk.model_validate(chunk_data)
    doc = ChunkDoc.model_validate(doc_data)
    store = _get_store()

    try:
        eval_res = evaluate_chunk_doc(chunk, doc)
    except Exception:
        logger.exception("evaluator_node: evaluation failed for chunk '%s'", cid)
        eval_res = EvalResult(
            chunk_id=cid,
            overall_score=0.0,
            issues=["[EVAL_FAILED] Unexpected error during evaluation"],
            needs_refinement=True,
        )

    store.save_eval(eval_res)

    eval_scores = dict(state.get("eval_scores", {}))
    eval_scores[cid] = eval_res.overall_score

    eval_issues = dict(state.get("eval_issues", {}))
    eval_issues[cid] = eval_res.issues

    logger.info(
        "Evaluator: chunk '%s' scored %.1f (%d issue(s))",
        cid, eval_res.overall_score, len(eval_res.issues),
    )

    return {"eval_scores": eval_scores, "eval_issues": eval_issues}


# ============================================================================
# Routing: Post-Evaluation Decision
# ============================================================================

def route_after_eval(state: PipelineState) -> str:
    """Route chunk after evaluation: pass -> next, fail -> refine or flag.

    Decision logic:
      - Score >= PASS_THRESHOLD  -> advance to next chunk
      - Refinement retries exhausted -> flag for human review
      - Otherwise -> refine (re-document with evaluator critique)
    """
    cid = state.get("current_chunk")
    if not cid:
        return "next_chunk_router"

    scores = state.get("eval_scores", {})
    score = scores.get(cid, 0.0)
    refines = state.get("refine_count", {})
    refine_cnt = refines.get(cid, 0)

    if score >= PASS_THRESHOLD:
        logger.debug("route_after_eval: chunk '%s' PASSED (score=%.1f)", cid, score)
        return "next_chunk_router"

    if refine_cnt >= MAX_REFINEMENT_RETRIES:
        logger.info(
            "route_after_eval: chunk '%s' exhausted %d retries (score=%.1f) -> flagging",
            cid, MAX_REFINEMENT_RETRIES, score,
        )
        return "flag_for_human"

    logger.info(
        "route_after_eval: chunk '%s' needs refinement (score=%.1f, attempt=%d/%d)",
        cid, score, refine_cnt + 1, MAX_REFINEMENT_RETRIES,
    )
    return "refine"


# ============================================================================
# Node: Refine (Re-document with evaluator critique)
# ============================================================================

def refine_node(state: PipelineState) -> Dict[str, Any]:
    """Increment refinement counter and re-invoke documenter with critique context."""
    cid = state.get("current_chunk")
    refines = dict(state.get("refine_count", {}))
    if cid:
        refines[cid] = refines.get(cid, 0) + 1

    doc_updates = documenter_node(state)
    doc_updates["refine_count"] = refines
    return doc_updates


# ============================================================================
# Node: Flag for Human Review
# ============================================================================

def flag_for_human_node(state: PipelineState) -> Dict[str, Any]:
    """Flag a chunk for human review after exhausting refinement retries."""
    cid = state.get("current_chunk")
    if not cid:
        return {}

    store = _get_store()
    scores = state.get("eval_scores", {})
    score = scores.get(cid, 0.0)
    issues = state.get("eval_issues", {}).get(cid, ["Max refinement retries reached"])

    store.flag_for_review(chunk_id=cid, score=score, issues=issues)

    flagged = list(state.get("flagged_items", []))
    flagged.append({
        "chunk_id": cid,
        "overall_score": score,
        "issues": issues,
        "reason": "Max refinement retries reached",
    })

    logger.warning(
        "flag_for_human: chunk '%s' flagged (score=%.1f, %d issue(s))",
        cid, score, len(issues),
    )

    return {"flagged_items": flagged}


# ============================================================================
# Node: Next Chunk Router
# ============================================================================

def next_chunk_router_node(state: PipelineState) -> Dict[str, Any]:
    """Advance to the next chunk in the processing order."""
    order = state.get("processing_order", [])
    cid = state.get("current_chunk")
    next_cid = None

    if cid and cid in order:
        idx = order.index(cid)
        if idx + 1 < len(order):
            next_cid = order[idx + 1]

    if next_cid:
        logger.debug("next_chunk_router: advancing to '%s'", next_cid)
    else:
        logger.info("next_chunk_router: all chunks processed")

    return {"current_chunk": next_cid}


def check_more_chunks(state: PipelineState) -> str:
    """Conditional edge: loop back to documenter if chunks remain, else END."""
    if state.get("current_chunk") is not None:
        return "documenter"
    return END


# ============================================================================
# Graph Builder
# ============================================================================

def build_phase1_graph():
    """Build and compile the Phase 1 LangGraph state machine.

    Graph topology:
        START -> scanner -> documenter -> evaluator
                                            |
                              +---------+---+---+-----------+
                              |         |               |
                           refine   next_chunk_router  flag_for_human
                              |         |               |
                              +-> evaluator    +--------+
                                        |
                                  documenter (loop) / END
    """
    builder = StateGraph(PipelineState)

    # Register nodes
    builder.add_node("scanner", scanner_node)
    builder.add_node("documenter", documenter_node)
    builder.add_node("evaluator", evaluator_node)
    builder.add_node("refine", refine_node)
    builder.add_node("flag_for_human", flag_for_human_node)
    builder.add_node("next_chunk_router", next_chunk_router_node)

    # Linear edges
    builder.add_edge(START, "scanner")
    builder.add_edge("scanner", "documenter")
    builder.add_edge("documenter", "evaluator")

    # Post-evaluation conditional routing
    builder.add_conditional_edges(
        "evaluator",
        route_after_eval,
        {
            "refine": "refine",
            "flag_for_human": "flag_for_human",
            "next_chunk_router": "next_chunk_router",
        },
    )

    # Refinement loop: refine -> re-evaluate
    builder.add_edge("refine", "evaluator")

    # After flagging, advance to next chunk
    builder.add_edge("flag_for_human", "next_chunk_router")

    # Chunk iteration loop
    builder.add_conditional_edges(
        "next_chunk_router",
        check_more_chunks,
        {
            "documenter": "documenter",
            END: END,
        },
    )

    return builder.compile()