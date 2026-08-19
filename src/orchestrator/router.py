"""Conditional edge routing logic for LangGraph state machine."""

from __future__ import annotations
import yaml
from pathlib import Path
from typing import Literal
from src.orchestrator.state import PipelineState, EvalResult


def _load_retry_caps() -> dict[str, int]:
    """Loads retry limits from thresholds config."""
    config_path = Path("configs/thresholds.yaml")
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                return data.get("retry_caps", {})
        except Exception:
            pass
    return {"chunking": 2, "dependency_mapping": 2, "documentation": 3, "code_generation": 3, "test_generation": 3}


def route_after_chunk_eval(state: PipelineState) -> Literal["dependency_mapper", "ingestion_chunker"]:
    """Routes after chunk evaluation: retry chunking if failed and under retry cap, else proceed."""
    eval_history = state.get("eval_history", [])
    chunk_evals = [e for e in eval_history if e.stage == "chunk_evaluation"]
    if not chunk_evals:
        return "dependency_mapper"

    latest = chunk_evals[-1]
    if latest.passed:
        return "dependency_mapper"

    # Check retry cap
    retry_counts = state.get("retry_counts", {})
    cap = _load_retry_caps().get("chunking", 2)
    attempts = retry_counts.get("global:chunking", 0)

    if attempts < cap:
        return "ingestion_chunker"
    
    return "dependency_mapper"


def route_after_dep_eval(state: PipelineState) -> Literal["documenter", "dependency_mapper"]:
    """Routes after dependency evaluation: retry mapping if failed and under retry cap, else proceed."""
    eval_history = state.get("eval_history", [])
    dep_evals = [e for e in eval_history if e.stage == "dependency_evaluation"]
    if not dep_evals:
        return "documenter"

    latest = dep_evals[-1]
    if latest.passed:
        return "documenter"

    retry_counts = state.get("retry_counts", {})
    cap = _load_retry_caps().get("dependency_mapping", 2)
    attempts = retry_counts.get("global:dependency_mapping", 0)

    if attempts < cap:
        return "dependency_mapper"
    
    return "documenter"


def route_after_doc_eval(state: PipelineState) -> Literal["doc_refiner", "code_generator"]:
    """Routes to doc_refiner if any chunk doc failed and is under retry cap, else proceeds to code_generator."""
    eval_history = state.get("eval_history", [])
    docs = state.get("docs", {})
    retry_counts = state.get("retry_counts", {})
    cap = _load_retry_caps().get("documentation", 3)

    for cid in docs:
        c_evals = [e for e in eval_history if e.target_id == cid and e.stage == "doc_evaluation"]
        if c_evals:
            latest = c_evals[-1]
            if not latest.passed:
                attempts = retry_counts.get(f"{cid}:documentation", 0)
                if attempts < cap:
                    return "doc_refiner"

    return "code_generator"


def route_after_code_eval(state: PipelineState) -> Literal["code_refiner", "test_generator"]:
    """Routes to code_refiner if any chunk code failed and is under retry cap, else proceeds to test_generator."""
    eval_history = state.get("eval_history", [])
    generated = state.get("generated_code", {})
    retry_counts = state.get("retry_counts", {})
    cap = _load_retry_caps().get("code_generation", 3)

    for cid in generated:
        c_evals = [e for e in eval_history if e.target_id == cid and e.stage == "code_evaluation"]
        if c_evals:
            latest = c_evals[-1]
            if not latest.passed:
                attempts = retry_counts.get(f"{cid}:code_generation", 0)
                if attempts < cap:
                    return "code_refiner"

    return "test_generator"


def route_after_test_exec(state: PipelineState) -> Literal["code_refiner", "report_builder"]:
    """Routes to code_refiner if unit tests failed and chunk is under retry cap, else proceeds to report_builder."""
    eval_history = state.get("eval_history", [])
    tests = state.get("tests", {})
    retry_counts = state.get("retry_counts", {})
    cap = _load_retry_caps().get("test_generation", 3)

    for cid in tests:
        t_evals = [e for e in eval_history if e.target_id == cid and e.stage == "test_execution"]
        if t_evals:
            latest = t_evals[-1]
            if not latest.passed:
                attempts = retry_counts.get(f"{cid}:test_generation", 0)
                if attempts < cap:
                    return "code_refiner"

    return "report_builder"
