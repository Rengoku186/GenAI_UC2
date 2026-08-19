"""Aggregation of pipeline state and evaluation history into structured reports."""

from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any
import pandas as pd

from src.orchestrator.state import PipelineState, EvalResult, ChunkMetadata
from src.evaluation.metrics import EvaluationMetricsCalculator


class ReportBuilder:
    """Aggregates all evaluation results into JSON and DataFrame formats for dashboard & audit logs."""

    def __init__(self, output_dir: str | Path = "outputs/evaluation_reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def build_summary_report(self, state: PipelineState) -> dict[str, Any]:
        """Builds a complete structured summary report from PipelineState."""
        chunks = state.get("chunks", [])
        eval_history = state.get("eval_history", [])
        retry_counts = state.get("retry_counts", {})
        docs = state.get("docs", {})
        generated_code = state.get("generated_code", {})
        tests = state.get("tests", {})

        ranked_chunks = EvaluationMetricsCalculator.rank_chunks_for_triage(
            chunks, eval_history, retry_counts
        )

        status_counts = {
            "auto_passed": sum(1 for c in ranked_chunks if c["status"] == "auto_passed"),
            "auto_passed_after_refinement": sum(1 for c in ranked_chunks if c["status"] == "auto_passed_after_refinement"),
            "flagged_for_human_review": sum(1 for c in ranked_chunks if c["status"] == "flagged_for_human_review"),
            "in_progress": sum(1 for c in ranked_chunks if c["status"] == "in_progress")
        }

        avg_confidence = (
            sum(c["confidence_score"] for c in ranked_chunks) / max(1, len(ranked_chunks))
        ) if ranked_chunks else 0.0

        # Detailed per-chunk trail
        chunk_details: dict[str, Any] = {}
        for c in chunks:
            cid = c.chunk_id
            c_evals = [e.model_dump() for e in eval_history if e.target_id == cid]
            c_doc = docs.get(cid)
            c_code = generated_code.get(cid)
            c_test = tests.get(cid)

            chunk_details[cid] = {
                "metadata": c.model_dump(),
                "status": EvaluationMetricsCalculator.classify_chunk_state(cid, eval_history, retry_counts),
                "confidence_score": EvaluationMetricsCalculator.calculate_chunk_confidence(cid, eval_history),
                "doc": c_doc.model_dump() if c_doc else None,
                "generated_code": c_code.model_dump() if c_code else None,
                "tests": c_test.model_dump() if c_test else None,
                "eval_trail": c_evals,
                "retry_count": sum(v for k, v in retry_counts.items() if k.startswith(f"{cid}:"))
            }

        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pipeline_stage": state.get("stage", "completed"),
            "total_chunks": len(chunks),
            "status_summary": status_counts,
            "overall_average_confidence": round(avg_confidence, 3),
            "flagged_for_review_ids": [c["chunk_id"] for c in ranked_chunks if c["status"] == "flagged_for_human_review"],
            "ranked_triage_table": ranked_chunks,
            "chunk_details": chunk_details,
            "dependency_graph_edges": [e.model_dump() for e in state.get("dependency_graph", [])]
        }

        return report

    def save_report_to_disk(self, state: PipelineState, filename_prefix: str = "modernization_run") -> Path:
        """Saves JSON report to outputs directory."""
        report = self.build_summary_report(state)
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        report_path = self.output_dir / f"{filename_prefix}_{timestamp_str}.json"
        
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)

        # Also write a latest symlink or pointer file
        latest_path = self.output_dir / "latest_report.json"
        with open(latest_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)

        return report_path

    @staticmethod
    def get_triage_dataframe(report: dict[str, Any]) -> pd.DataFrame:
        """Converts ranked triage table from report into a Pandas DataFrame."""
        rows = report.get("ranked_triage_table", [])
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        return df
