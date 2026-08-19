"""Evaluation metrics calculation and triage ranking."""

from __future__ import annotations
from typing import Any
from src.orchestrator.state import PipelineState, EvalResult, ChunkMetadata


class EvaluationMetricsCalculator:
    """Calculates granular stage quality metrics, triage rankings, and three-state chunk classifications."""

    @staticmethod
    def classify_chunk_state(
        chunk_id: str,
        eval_history: list[EvalResult],
        retry_counts: dict[str, int]
    ) -> str:
        """
        Classifies a chunk into one of three explicit states:
        1. 'auto_passed': Passed all evaluated stages on version 1 without refinement.
        2. 'auto_passed_after_refinement': Passed after 1 or more refinement iterations.
        3. 'flagged_for_human_review': Failed to meet confidence threshold or flagged for review.
        """
        chunk_evals = [e for e in eval_history if e.target_id == chunk_id]
        if not chunk_evals:
            return "in_progress"

        # If any eval explicitly flagged for human review or failed in its latest run
        stage_latest: dict[str, EvalResult] = {}
        for e in chunk_evals:
            stage_latest[e.stage] = e

        has_active_failure = any(not e.passed for e in stage_latest.values())
        has_human_flag = any(e.needs_human_review for e in chunk_evals)

        if has_human_flag or has_active_failure:
            return "flagged_for_human_review"

        # Check if retries occurred for any stage of this chunk
        has_retries = any(
            count > 0 for k, count in retry_counts.items() 
            if k.startswith(f"{chunk_id}:")
        ) or any(e.version_evaluated > 1 for e in chunk_evals)

        if has_retries:
            return "auto_passed_after_refinement"
        
        return "auto_passed"

    @staticmethod
    def calculate_chunk_confidence(
        chunk_id: str,
        eval_history: list[EvalResult]
    ) -> float:
        """Computes weighted composite confidence score (0.0 to 1.0) for a chunk based on its latest evals."""
        chunk_evals = [e for e in eval_history if e.target_id == chunk_id]
        if not chunk_evals:
            return 0.0

        stage_weights = {
            "doc_evaluation": 0.25,
            "code_evaluation": 0.35,
            "test_execution": 0.40
        }

        stage_latest_scores: dict[str, float] = {}
        for e in chunk_evals:
            stage_latest_scores[e.stage] = e.score

        total_weight = 0.0
        weighted_sum = 0.0
        for stage, score in stage_latest_scores.items():
            w = stage_weights.get(stage, 0.2)
            weighted_sum += score * w
            total_weight += w

        return round(weighted_sum / max(0.001, total_weight), 3)

    @classmethod
    def rank_chunks_for_triage(
        cls,
        chunks: list[ChunkMetadata],
        eval_history: list[EvalResult],
        retry_counts: dict[str, int]
    ) -> list[dict[str, Any]]:
        """Ranks all chunks by lowest confidence score first to guide human review triage."""
        ranked: list[dict[str, Any]] = []

        for chunk in chunks:
            cid = chunk.chunk_id
            status = cls.classify_chunk_state(cid, eval_history, retry_counts)
            confidence = cls.calculate_chunk_confidence(cid, eval_history)
            
            chunk_evals = [e for e in eval_history if e.target_id == cid]
            total_issues = sum(len(e.issues) for e in chunk_evals)
            
            ranked.append({
                "chunk_id": cid,
                "name": chunk.name,
                "language": chunk.language,
                "status": status,
                "confidence_score": confidence,
                "issue_count": total_issues,
                "source_file": chunk.source_file,
                "line_range": f"{chunk.line_start}-{chunk.line_end}"
            })

        # Sort lowest confidence first, then flagged status
        status_priority = {
            "flagged_for_human_review": 0,
            "auto_passed_after_refinement": 1,
            "auto_passed": 2,
            "in_progress": 3
        }
        
        ranked.sort(key=lambda x: (status_priority.get(x["status"], 4), x["confidence_score"]))
        return ranked
