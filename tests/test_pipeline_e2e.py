"""End-to-end integration test for the legacy code modernization multi-agent pipeline."""

import pytest
from pathlib import Path
from src.orchestrator.graph import run_pipeline
from src.evaluation.report_builder import ReportBuilder


def test_end_to_end_modernization_pipeline(tmp_path):
    sample_files = [
        "data/legacy_source/loan_calculator.cbl",
        "data/legacy_source/customer_validator.vb",
        "data/legacy_source/account_processor.java"
    ]

    final_state = run_pipeline(sample_files)

    # Validate state structure
    assert len(final_state["chunks"]) > 0
    assert len(final_state["dependency_graph"]) > 0
    assert len(final_state["docs"]) > 0
    assert len(final_state["generated_code"]) > 0
    assert len(final_state["tests"]) > 0
    assert len(final_state["eval_history"]) > 0
    assert final_state["stage"] == "completed"

    # Validate report generation
    builder = ReportBuilder(output_dir=tmp_path)
    report = builder.build_summary_report(final_state)
    assert report["total_chunks"] == len(final_state["chunks"])
    assert "status_summary" in report
    assert "ranked_triage_table" in report
