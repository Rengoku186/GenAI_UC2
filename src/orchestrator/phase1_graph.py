from typing import Dict, Any, List
from langgraph.graph import StateGraph, START, END
from src.state import PipelineState
from src.schemas import Chunk, ChunkDoc, EvalResult
from src.tools.dependency_scanner import scan_project
from src.tools.cycle_detector import prepare_processing_graph
from src.agents.splitter import create_chunk_from_node_data, split_chunk_if_oversized
from src.agents.documenter import document_chunk
from src.agents.evaluator import evaluate_chunk_doc, PASS_THRESHOLD
from src.knowledge_store.store import KnowledgeStore

store = KnowledgeStore()

def scanner_node(state: PipelineState) -> Dict[str, Any]:
    file_paths = state.get("file_paths", [])
    raw_graph = scan_project(file_paths)
    condensed_dag, processing_order = prepare_processing_graph(raw_graph)

    chunks_list = []
    for node_id in condensed_dag.nodes:
        node_data = condensed_dag.nodes[node_id]
        real_id = str(node_data.get("id", node_id))
        chunk = create_chunk_from_node_data(real_id, node_data)
        split_chunks = split_chunk_if_oversized(chunk)
        for sc in split_chunks:
            chunks_list.append(sc.model_dump())

    order = processing_order if processing_order else [c["id"] for c in chunks_list]
    curr = order[0] if order else None

    return {
        "chunks": chunks_list,
        "processing_order": order,
        "current_chunk": curr,
        "docs": state.get("docs", {}),
        "eval_scores": state.get("eval_scores", {}),
        "eval_issues": state.get("eval_issues", {}),
        "refine_count": state.get("refine_count", {}),
        "flagged_items": state.get("flagged_items", [])
    }

def documenter_node(state: PipelineState) -> Dict[str, Any]:
    cid = state.get("current_chunk")
    if not cid:
        return {}

    chunks = state.get("chunks", [])
    chunk_data = next((c for c in chunks if c["id"] == cid), None)
    if not chunk_data:
        return {}

    chunk = Chunk.model_validate(chunk_data)

    docs = dict(state.get("docs", {}))
    dep_docs = []
    for dep_id in chunk.depends_on:
        if dep_id in docs:
            dep_docs.append(ChunkDoc.model_validate(docs[dep_id]))

    doc = document_chunk(chunk, dep_docs)
    docs[cid] = doc.model_dump()
    store.save_doc(doc)
    return {"docs": docs}

def evaluator_node(state: PipelineState) -> Dict[str, Any]:
    cid = state.get("current_chunk")
    if not cid:
        return {}

    chunks = state.get("chunks", [])
    chunk_data = next((c for c in chunks if c["id"] == cid), None)
    docs = state.get("docs", {})
    doc_data = docs.get(cid)

    if not chunk_data or not doc_data:
        return {}

    chunk = Chunk.model_validate(chunk_data)
    doc = ChunkDoc.model_validate(doc_data)

    eval_res = evaluate_chunk_doc(chunk, doc)
    store.save_eval(eval_res)

    eval_scores = dict(state.get("eval_scores", {}))
    eval_scores[cid] = eval_res.overall_score

    eval_issues = dict(state.get("eval_issues", {}))
    eval_issues[cid] = eval_res.issues

    return {"eval_scores": eval_scores, "eval_issues": eval_issues}

def route_after_eval(state: PipelineState) -> str:
    cid = state.get("current_chunk")
    if not cid:
        return "next_chunk_router"

    scores = state.get("eval_scores", {})
    score = scores.get(cid, 0.0)
    refines = state.get("refine_count", {})
    refine_cnt = refines.get(cid, 0)

    if score >= PASS_THRESHOLD:
        return "next_chunk_router"
    if refine_cnt >= 3:
        return "flag_for_human"

    return "refine"

def refine_node(state: PipelineState) -> Dict[str, Any]:
    cid = state.get("current_chunk")
    refines = dict(state.get("refine_count", {}))
    if cid:
        refines[cid] = refines.get(cid, 0) + 1

    doc_updates = documenter_node(state)
    doc_updates["refine_count"] = refines
    return doc_updates

def flag_for_human_node(state: PipelineState) -> Dict[str, Any]:
    cid = state.get("current_chunk")
    if not cid:
        return {}

    scores = state.get("eval_scores", {})
    score = scores.get(cid, 0.0)
    issues = state.get("eval_issues", {}).get(cid, ["Max refinement retries reached (score < 80)"])

    store.flag_for_review(chunk_id=cid, score=score, issues=issues)
    flagged = list(state.get("flagged_items", []))
    flagged.append({
        "chunk_id": cid,
        "overall_score": score,
        "issues": issues,
        "reason": "Max refinement retries reached"
    })
    return {"flagged_items": flagged}

def next_chunk_router_node(state: PipelineState) -> Dict[str, Any]:
    order = state.get("processing_order", [])
    cid = state.get("current_chunk")
    next_cid = None
    if cid and cid in order:
        idx = order.index(cid)
        if idx + 1 < len(order):
            next_cid = order[idx + 1]
    return {"current_chunk": next_cid}

def check_more_chunks(state: PipelineState) -> str:
    if state.get("current_chunk") is not None:
        return "documenter"
    return END

def build_phase1_graph():
    builder = StateGraph(PipelineState)
    builder.add_node("scanner", scanner_node)
    builder.add_node("documenter", documenter_node)
    builder.add_node("evaluator", evaluator_node)
    builder.add_node("refine", refine_node)
    builder.add_node("flag_for_human", flag_for_human_node)
    builder.add_node("next_chunk_router", next_chunk_router_node)

    builder.add_edge(START, "scanner")
    builder.add_edge("scanner", "documenter")
    builder.add_edge("documenter", "evaluator")

    builder.add_conditional_edges(
        "evaluator",
        route_after_eval,
        {
            "refine": "refine",
            "flag_for_human": "flag_for_human",
            "next_chunk_router": "next_chunk_router"
        }
    )

    builder.add_edge("refine", "evaluator")
    builder.add_edge("flag_for_human", "next_chunk_router")

    builder.add_conditional_edges(
        "next_chunk_router",
        check_more_chunks,
        {
            "documenter": "documenter",
            END: END
        }
    )

    return builder.compile()