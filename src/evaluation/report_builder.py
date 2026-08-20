"""Aggregation of pipeline state, evaluation history, and documentation & code exports."""

from __future__ import annotations
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Any
import pandas as pd

from src.orchestrator.state import PipelineState, EvalResult, ChunkMetadata
from src.evaluation.metrics import EvaluationMetricsCalculator
from src.evaluation.full_file_synthesizer import FullFileSynthesizer
from src.utils.logger import get_logger

logger = get_logger("ReportBuilder")


class ReportBuilder:
    """Aggregates evaluation results into JSON and exports complete converted services, test suites, and documentation markdown."""

    def __init__(
        self,
        output_dir: str | Path = "outputs/evaluation_reports",
        code_export_dir: str | Path = "outputs/modernized_code",
        docs_export_dir: str | Path = "outputs/documentation"
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.code_export_dir = Path(code_export_dir)
        self.code_export_dir.mkdir(parents=True, exist_ok=True)
        self.docs_export_dir = Path(docs_export_dir)
        self.docs_export_dir.mkdir(parents=True, exist_ok=True)

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

        # Build full synthesized file conversions & documentation per source file
        source_files = list(set(c.source_file for c in chunks))
        full_files_map: dict[str, Any] = {}

        for sf in source_files:
            file_chunks = [c for c in chunks if c.source_file == sf]
            file_code = {c.chunk_id: generated_code[c.chunk_id] for c in file_chunks if c.chunk_id in generated_code}
            file_docs = {c.chunk_id: docs[c.chunk_id] for c in file_chunks if c.chunk_id in docs}
            synthesized = FullFileSynthesizer.synthesize_file_modernization(sf, file_chunks, file_code, file_docs)
            full_files_map[sf] = synthesized

        # Generate a stable run_id from timestamp
        run_ts = datetime.now(timezone.utc)
        run_id = run_ts.strftime("%Y%m%d_%H%M%S")

        report = {
            "run_id": run_id,
            "timestamp": run_ts.isoformat(),
            "pipeline_stage": state.get("stage", "completed"),
            "total_chunks": len(chunks),
            "status_summary": status_counts,
            "overall_average_confidence": round(avg_confidence, 3),
            "flagged_for_review_ids": [c["chunk_id"] for c in ranked_chunks if c["status"] == "flagged_for_human_review"],
            "ranked_triage_table": ranked_chunks,
            "chunk_details": chunk_details,
            "synthesized_full_files": full_files_map,
            "dependency_graph_edges": [e.model_dump() for e in state.get("dependency_graph", [])],
        }

        return report

    def export_converted_code_and_docs(self, state: PipelineState) -> dict[str, list[str]]:
        """Writes modern whole-file Java services, JUnit 5 test suites, and markdown documentation to outputs directory."""
        java_dir = self.code_export_dir / "java"
        test_java_dir = self.code_export_dir / "tests" / "java"
        docs_dir = self.docs_export_dir

        for d in [java_dir, test_java_dir, docs_dir]:
            d.mkdir(parents=True, exist_ok=True)

        chunks = state.get("chunks", [])
        generated_code = state.get("generated_code", {})
        docs = state.get("docs", {})
        source_files = list(set(c.source_file for c in chunks))

        exported_files: dict[str, list[str]] = {"java": [], "tests": [], "docs": []}

        for sf in source_files:
            file_chunks = [c for c in chunks if c.source_file == sf]
            file_code = {c.chunk_id: generated_code[c.chunk_id] for c in file_chunks if c.chunk_id in generated_code}
            file_docs = {c.chunk_id: docs[c.chunk_id] for c in file_chunks if c.chunk_id in docs}
            
            synth = FullFileSynthesizer.synthesize_file_modernization(sf, file_chunks, file_code, file_docs)
            mod_name = synth.get("module_name", Path(sf).stem)
            java_name = synth.get("java_class_name", mod_name.capitalize() + "Service")

            # 1. Export Whole Java Service File
            if synth.get("java_code"):
                java_file = java_dir / f"{java_name}.java"
                java_file.write_text(synth["java_code"], encoding="utf-8")
                exported_files["java"].append(str(java_file))

            # 2. Export JUnit 5 Suite
            if synth.get("java_tests"):
                test_java_file = test_java_dir / f"{java_name}Test.java"
                test_java_file.write_text(synth["java_tests"], encoding="utf-8")
                exported_files["tests"].append(str(test_java_file))

            # 3. Export Markdown Documentation
            if synth.get("documentation_markdown"):
                doc_file = docs_dir / f"{mod_name}.md"
                doc_file.write_text(synth["documentation_markdown"], encoding="utf-8")
                exported_files["docs"].append(str(doc_file))

        # Write System Architecture Overview
        arch_doc = docs_dir / "SYSTEM_ARCHITECTURE.md"
        arch_content = f"""# Autonomous Legacy Code Modernization System Architecture

Generated: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}

## 1. Processed Legacy Codebase Sources
""" + "\n".join([f"- `{sf}` ({len([c for c in chunks if c.source_file == sf])} semantic chunks)" for sf in source_files]) + """

## 2. Modern Target Deliverables
- **Java 17+/21+ Services:** `outputs/modernized_code/java/`
- **JUnit 5 Test Suites:** `outputs/modernized_code/tests/java/`
- **System Documentation:** `outputs/documentation/`

## 3. Evaluation & Quality Gate
- 13-Node LangGraph Multi-Agent Architecture with self-correcting feedback loops.
- Java-only modernization mode: all legacy sources (Java) converted to modern Java 17+.
"""
        arch_doc.write_text(arch_content, encoding="utf-8")
        exported_files["docs"].append(str(arch_doc))

        logger.info(
            "Exported: %d Java files, %d test suites, %d documentation files to outputs/",
            len(exported_files["java"]), len(exported_files["tests"]), len(exported_files["docs"])
        )
        return exported_files

    def save_report_to_disk(self, state: PipelineState, filename_prefix: str = "modernization_run") -> Path:
        """Saves JSON report and exports converted code and markdown documentation to disk."""
        # 1. Export whole-file code, test suites, and documentation
        self.export_converted_code_and_docs(state)

        # 2. Build and save JSON report
        report = self.build_summary_report(state)
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        report_path = self.output_dir / f"{filename_prefix}_{timestamp_str}.json"
        
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)

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
        return pd.DataFrame(rows)
