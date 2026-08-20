"""Unit tests for LangGraph state machine routers and retry logic."""

import pytest
from src.orchestrator.state import PipelineState, EvalResult, DocSection
from src.orchestrator.router import (
    route_after_chunk_eval,
    route_after_dep_eval,
    route_after_code_eval,
    route_after_test_exec,
    route_after_compile_check,
)


def _base_state(**overrides) -> dict:
    """Helper: returns a minimal valid PipelineState with optional overrides."""
    base = {
        "eval_history": [],
        "retry_counts": {},
        "chunks": [],
        "source_files": [],
        "dependency_graph": [],
        "docs": {},
        "generated_code": {},
        "tests": {},
        "current_chunk_id": None,
        "stage": "test",
        "flagged_for_review": [],
        "metadata": {},
        "compile_errors": {},
    }
    base.update(overrides)
    return base


def test_route_after_chunk_eval_success():
    state = _base_state(
        eval_history=[
            EvalResult(target_id="global_chunks", stage="chunk_evaluation", score=0.95, passed=True)
        ]
    )
    assert route_after_chunk_eval(state) == "dependency_mapper"


def test_route_after_chunk_eval_retry():
    state = _base_state(
        eval_history=[
            EvalResult(target_id="global_chunks", stage="chunk_evaluation", score=0.30, passed=False)
        ],
        retry_counts={"global:chunking": 0}
    )
    assert route_after_chunk_eval(state) == "ingestion_chunker"


def test_route_after_compile_check_clean():
    state = _base_state(compile_errors={})
    assert route_after_compile_check(state) == "report_builder"


def test_route_after_compile_check_errors():
    state = _base_state(
        compile_errors={"AccountProcessor.java": ["error: ';' expected"]},
        retry_counts={"global:compile_check": 0}
    )
    assert route_after_compile_check(state) == "code_refiner"


def test_route_after_test_exec_routes_to_compile_checker():
    state = _base_state(
        tests={"CHUNK_1": object()},
        eval_history=[
            EvalResult(target_id="CHUNK_1", stage="test_execution", score=0.95, passed=True)
        ],
    )
    assert route_after_test_exec(state) == "java_compile_checker"
