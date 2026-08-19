"""Unit tests for LangGraph state machine routers and retry logic."""

import pytest
from src.orchestrator.state import PipelineState, EvalResult, DocSection
from src.orchestrator.router import (
    route_after_chunk_eval,
    route_after_dep_eval,
    route_after_doc_eval,
    route_after_code_eval,
    route_after_test_exec
)


def test_route_after_chunk_eval_success():
    state: PipelineState = {
        "eval_history": [
            EvalResult(target_id="global_chunks", stage="chunk_evaluation", score=0.95, passed=True)
        ],
        "retry_counts": {},
        "chunks": [],
        "source_files": [],
        "dependency_graph": [],
        "docs": {},
        "generated_code": {},
        "tests": {},
        "current_chunk_id": None,
        "stage": "chunk_evaluation",
        "flagged_for_review": [],
        "metadata": {}
    }
    assert route_after_chunk_eval(state) == "dependency_mapper"


def test_route_after_doc_eval_refine_loop():
    state: PipelineState = {
        "eval_history": [
            EvalResult(target_id="CHUNK_1", stage="doc_evaluation", score=0.50, passed=False)
        ],
        "docs": {
            "CHUNK_1": DocSection(chunk_id="CHUNK_1", purpose="test", control_flow="test")
        },
        "retry_counts": {"CHUNK_1:documentation": 0},
        "chunks": [],
        "source_files": [],
        "dependency_graph": [],
        "generated_code": {},
        "tests": {},
        "current_chunk_id": None,
        "stage": "doc_evaluation",
        "flagged_for_review": [],
        "metadata": {}
    }
    assert route_after_doc_eval(state) == "doc_refiner"

    # When retry count hits max cap (3), it should proceed to code_generator
    state["retry_counts"]["CHUNK_1:documentation"] = 3
    assert route_after_doc_eval(state) == "code_generator"
