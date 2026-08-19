"""Conditional edge routing logic for LangGraph state machine with logging."""

from __future__ import annotations
import yaml
from pathlib import Path
from typing import Literal
from src.orchestrator.state import PipelineState, EvalResult
from src.utils.logger import get_logger

logger = get_logger("Router")


_CACHED_RETRY_CAPS: dict[str, int] | None = None

def _load_retry_caps() -> dict[str, int]:
    """Loads retry limits from thresholds config safely and independently of CWD."""
    global _CACHED_RETRY_CAPS
    if _CACHED_RETRY_CAPS is not None:
        return _CACHED_RETRY_CAPS

    candidates = [
        Path("configs/thresholds.yaml"),
        Path(__file__).resolve().parent.parent.parent / "configs" / "thresholds.yaml",
        Path.cwd() / "configs" / "thresholds.yaml",
    ]
    for config_path in candidates:
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    caps = data.get("retry_caps", {})
                    if caps:
                        _CACHED_RETRY_CAPS = caps
                        return _CACHED_RETRY_CAPS
            except Exception as e:
                logger.debug("Failed reading retry caps from %s: %s", config_path, e)
    
    _CACHED_RETRY_CAPS = {"chunking": 2, "dependency_mapping": 2, "documentation": 3, "code_generation": 3, "test_generation": 3}
    return _CACHED_RETRY_CAPS


def route_after_chunk_eval(state: PipelineState) -> Literal["dependency_mapper", "ingestion_chunker"]:
    """Routes after chunk evaluation: retry chunking if failed and under retry cap, else proceed."""
    eval_history = state.get("eval_history", [])
    chunk_evals = [e for e in eval_history if e.stage == "chunk_evaluation"]
    if not chunk_evals:
        logger.info("[Router] No chunk evaluations found; routing to dependency_mapper")
        return "dependency_mapper"

    latest = chunk_evals[-1]
    if latest.passed:
        logger.info("[Router] Chunk evaluation passed (Score: %.2f); routing to dependency_mapper", latest.score)
        return "dependency_mapper"

    retry_counts = state.get("retry_counts", {})
    cap = _load_retry_caps().get("chunking", 2)
    attempts = retry_counts.get("global:chunking", 0)

    if attempts < cap:
        logger.warning("[Router] Chunk evaluation failed (Attempt %d/%d); looping back to ingestion_chunker", attempts + 1, cap)
        return "ingestion_chunker"
    
    logger.warning("[Router] Chunk evaluation retry cap reached (%d/%d); proceeding to dependency_mapper", attempts, cap)
    return "dependency_mapper"


def route_after_dep_eval(state: PipelineState) -> Literal["documenter", "dependency_mapper"]:
    """Routes after dependency evaluation: retry mapping if failed and under retry cap, else proceed."""
    eval_history = state.get("eval_history", [])
    dep_evals = [e for e in eval_history if e.stage == "dependency_evaluation"]
    if not dep_evals:
        logger.info("[Router] No dependency evaluations found; routing to documenter")
        return "documenter"

    latest = dep_evals[-1]
    if latest.passed:
        logger.info("[Router] Dependency evaluation passed (Score: %.2f); routing to documenter", latest.score)
        return "documenter"

    retry_counts = state.get("retry_counts", {})
    cap = _load_retry_caps().get("dependency_mapping", 2)
    attempts = retry_counts.get("global:dependency_mapping", 0)

    if attempts < cap:
        logger.warning("[Router] Dependency evaluation failed (Attempt %d/%d); looping back to dependency_mapper", attempts + 1, cap)
        return "dependency_mapper"
    
    logger.warning("[Router] Dependency evaluation retry cap reached (%d/%d); proceeding to documenter", attempts, cap)
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
                    logger.warning("[Router] Doc evaluation failed for chunk %s (Attempt %d/%d); routing to doc_refiner", cid, attempts + 1, cap)
                    return "doc_refiner"

    logger.info("[Router] Documentation evaluation complete; proceeding to code_generator")
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
                    logger.warning("[Router] Code evaluation failed for chunk %s (Attempt %d/%d); routing to code_refiner", cid, attempts + 1, cap)
                    return "code_refiner"

    logger.info("[Router] Code evaluation complete; proceeding to test_generator")
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
                    logger.warning("[Router] Test execution failed for chunk %s (Attempt %d/%d); routing back to code_refiner", cid, attempts + 1, cap)
                    return "code_refiner"

    logger.info("[Router] Test execution phase complete; proceeding to report_builder")
    return "report_builder"
