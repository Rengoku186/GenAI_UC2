"""Full LangGraph state machine orchestrating the legacy code modernization multi-agent system."""

from __future__ import annotations
import sys
from pathlib import Path
from typing import Any
from langgraph.graph import StateGraph, START, END

from src.orchestrator.state import PipelineState
from src.orchestrator.router import (
    route_after_chunk_eval,
    route_after_dep_eval,
    route_after_doc_eval,
    route_after_code_eval,
    route_after_test_exec
)

# Import Agents
from src.agents.ingestion_chunker import IngestionChunkerAgent
from src.agents.dependency_mapper import DependencyMapperAgent
from src.agents.chunk_evaluator import ChunkEvaluatorAgent
from src.agents.dependency_evaluator import DependencyEvaluatorAgent
from src.agents.documenter import DocumenterAgent
from src.agents.doc_evaluator import DocEvaluatorAgent
from src.agents.doc_refiner import DocRefinerAgent
from src.agents.code_generator import CodeGeneratorAgent
from src.agents.code_evaluator import CodeEvaluatorAgent
from src.agents.code_refiner import CodeRefinerAgent
from src.agents.test_generator import TestGeneratorAgent
from src.agents.test_executor import TestExecutorAgent
from src.evaluation.report_builder import ReportBuilder
from src.utils.logger import setup_logging, get_logger
from src.utils.pipeline_log_handler import PipelineMemoryHandler
from src.utils.knowledge_store import write_knowledge_store

logger = get_logger("Orchestrator")


def build_modernization_graph(config_dir: str = "configs") -> Any:
    """Builds and compiles the full LangGraph StateGraph for code modernization."""
    setup_logging()
    logger.info("Initializing LangGraph Modernization Graph with config_dir='%s'", config_dir)

    # Initialize all agent instances
    chunker = IngestionChunkerAgent(config_dir=config_dir)
    dep_mapper = DependencyMapperAgent(config_dir=config_dir)
    chunk_eval = ChunkEvaluatorAgent(config_dir=config_dir)
    dep_eval = DependencyEvaluatorAgent(config_dir=config_dir)
    documenter = DocumenterAgent(config_dir=config_dir)
    doc_eval = DocEvaluatorAgent(config_dir=config_dir)
    doc_refiner = DocRefinerAgent(config_dir=config_dir)
    code_gen = CodeGeneratorAgent(config_dir=config_dir)
    code_eval = CodeEvaluatorAgent(config_dir=config_dir)
    code_refiner = CodeRefinerAgent(config_dir=config_dir)
    test_gen = TestGeneratorAgent(config_dir=config_dir)
    test_exec = TestExecutorAgent(config_dir=config_dir)
    report_builder = ReportBuilder()

    # Define Node Wrappers
    def node_ingestion_chunker(state: PipelineState) -> dict:
        logger.info("[Pipeline] Executing Node: IngestionChunker")
        return chunker.execute(state)

    def node_chunk_evaluator(state: PipelineState) -> dict:
        logger.info("[Pipeline] Executing Node: ChunkEvaluator")
        return chunk_eval.execute(state)

    def node_dependency_mapper(state: PipelineState) -> dict:
        logger.info("[Pipeline] Executing Node: DependencyMapper")
        return dep_mapper.execute(state)

    def node_dependency_evaluator(state: PipelineState) -> dict:
        logger.info("[Pipeline] Executing Node: DependencyEvaluator")
        return dep_eval.execute(state)

    def node_documenter(state: PipelineState) -> dict:
        logger.info("[Pipeline] Executing Node: Documenter")
        return documenter.execute(state)

    def node_doc_evaluator(state: PipelineState) -> dict:
        logger.info("[Pipeline] Executing Node: DocEvaluator")
        return doc_eval.execute(state)

    def node_doc_refiner(state: PipelineState) -> dict:
        logger.info("[Pipeline] Executing Node: DocRefiner")
        return doc_refiner.execute(state)

    def node_code_generator(state: PipelineState) -> dict:
        logger.info("[Pipeline] Executing Node: CodeGenerator (Python & Java)")
        return code_gen.execute(state)

    def node_code_evaluator(state: PipelineState) -> dict:
        logger.info("[Pipeline] Executing Node: CodeEvaluator")
        return code_eval.execute(state)

    def node_code_refiner(state: PipelineState) -> dict:
        logger.info("[Pipeline] Executing Node: CodeRefiner")
        return code_refiner.execute(state)

    def node_test_generator(state: PipelineState) -> dict:
        logger.info("[Pipeline] Executing Node: TestGenerator (pytest & JUnit 5)")
        return test_gen.execute(state)

    def node_test_executor(state: PipelineState) -> dict:
        logger.info("[Pipeline] Executing Node: TestExecutor")
        return test_exec.execute(state)

    def node_report_builder(state: PipelineState) -> dict:
        logger.info("[Pipeline] Executing Node: ReportBuilder")
        saved_path = report_builder.save_report_to_disk(state)
        logger.info("[Pipeline] Evaluation report successfully written to: %s", saved_path)
        return {
            "stage": "completed",
            "metadata": {"report_path": str(saved_path)}
        }

    # Initialize StateGraph
    workflow = StateGraph(PipelineState)

    # Add all Agent Nodes
    workflow.add_node("ingestion_chunker", node_ingestion_chunker)
    workflow.add_node("chunk_evaluator", node_chunk_evaluator)
    workflow.add_node("dependency_mapper", node_dependency_mapper)
    workflow.add_node("dependency_evaluator", node_dependency_evaluator)
    workflow.add_node("documenter", node_documenter)
    workflow.add_node("doc_evaluator", node_doc_evaluator)
    workflow.add_node("doc_refiner", node_doc_refiner)
    workflow.add_node("code_generator", node_code_generator)
    workflow.add_node("code_evaluator", node_code_evaluator)
    workflow.add_node("code_refiner", node_code_refiner)
    workflow.add_node("test_generator", node_test_generator)
    workflow.add_node("test_executor", node_test_executor)
    workflow.add_node("report_builder", node_report_builder)

    # Edge Wiring
    workflow.add_edge(START, "ingestion_chunker")
    workflow.add_edge("ingestion_chunker", "chunk_evaluator")

    # Conditional Branch after Chunk Evaluator
    workflow.add_conditional_edges(
        "chunk_evaluator",
        route_after_chunk_eval,
        {
            "dependency_mapper": "dependency_mapper",
            "ingestion_chunker": "ingestion_chunker"
        }
    )

    workflow.add_edge("dependency_mapper", "dependency_evaluator")

    # Conditional Branch after Dependency Evaluator
    workflow.add_conditional_edges(
        "dependency_evaluator",
        route_after_dep_eval,
        {
            "documenter": "documenter",
            "dependency_mapper": "dependency_mapper"
        }
    )

    workflow.add_edge("documenter", "doc_evaluator")

    # Conditional Refinement Loop for Documentation
    workflow.add_conditional_edges(
        "doc_evaluator",
        route_after_doc_eval,
        {
            "doc_refiner": "doc_refiner",
            "code_generator": "code_generator"
        }
    )
    workflow.add_edge("doc_refiner", "doc_evaluator")

    # Code Gen -> Code Eval Loop
    workflow.add_edge("code_generator", "code_evaluator")
    workflow.add_conditional_edges(
        "code_evaluator",
        route_after_code_eval,
        {
            "code_refiner": "code_refiner",
            "test_generator": "test_generator"
        }
    )
    workflow.add_edge("code_refiner", "code_evaluator")

    # Test Gen -> Test Exec -> Refiner / Report Builder Loop
    workflow.add_edge("test_generator", "test_executor")
    workflow.add_conditional_edges(
        "test_executor",
        route_after_test_exec,
        {
            "code_refiner": "code_refiner",
            "report_builder": "report_builder"
        }
    )

    workflow.add_edge("report_builder", END)

    app = workflow.compile()
    return app


def run_pipeline(source_files: list[str], config_dir: str = "configs") -> PipelineState:
    """Convenience runner to execute the modernization graph synchronously on given source files."""
    setup_logging()

    # Install the in-memory log handler and reset any prior run's entries
    mem_handler = PipelineMemoryHandler.install()
    mem_handler.reset()

    logger.info("Starting Modernization Pipeline for %d source files: %s", len(source_files), source_files)
    app = build_modernization_graph(config_dir=config_dir)

    initial_state: PipelineState = {
        "source_files": source_files,
        "chunks": [],
        "dependency_graph": [],
        "docs": {},
        "generated_code": {},
        "tests": {},
        "eval_history": [],
        "retry_counts": {},
        "current_chunk_id": None,
        "stage": "starting",
        "flagged_for_review": [],
        "metadata": {}
    }

    final_state = app.invoke(initial_state)
    logger.info("Pipeline run finished. Total chunks: %d, stage: %s", len(final_state.get("chunks", [])), final_state.get("stage"))

    # Flush captured logs and write them to the .knowledge_store file on disk
    execution_log = mem_handler.flush_entries()
    report_meta   = final_state.get("metadata", {})
    run_id        = report_meta.get("report_path", "").replace("\\", "/").split("/")[-1].replace(".json", "") or "run_unknown"

    ks_path = write_knowledge_store(
        entries=execution_log,
        run_id=run_id,
        source_files=source_files,
        chunk_summary={
            "total_chunks":               len(final_state.get("chunks", [])),
            "status_summary":             {},   # populated fully by ReportBuilder; this is a quick summary
            "overall_average_confidence": 0.0,
        },
    )
    logger.info("Execution trace written to: %s", ks_path)

    return final_state


def main():
    """CLI Entrypoint for running the legacy code modernizer."""
    setup_logging()
    from rich.console import Console
    from rich.table import Table

    console = Console()
    console.print("[bold green]=== Legacy Code Modernization Agentic System ===[/bold green]\n")

    if len(sys.argv) > 1:
        source_paths = sys.argv[1:]
    else:
        sample_dir = Path("data/legacy_source")
        source_paths = [
            str(p) for p in sample_dir.glob("*.*")
            if p.suffix.lower() in [".cbl", ".vb", ".java"]
        ]

    console.print(f"[bold]Target Source Files:[/bold] {source_paths}\n")

    with console.status("[bold blue]Executing Autonomous Multi-Agent Modernization Pipeline...[/bold blue]"):
        final_state = run_pipeline(source_paths)

    console.print("[bold green][OK] Modernization Pipeline Run Completed Successfully![/bold green]\n")

    # Print summary table
    table = Table(title="Modernization Chunks Triage Summary")
    table.add_column("Chunk ID", style="cyan")
    table.add_column("Lang", style="magenta")
    table.add_column("Status", style="bold")
    table.add_column("Confidence", justify="right")
    table.add_column("Source Range")

    report_path = final_state.get("metadata", {}).get("report_path", "outputs/evaluation_reports/latest_report.json")
    from src.evaluation.metrics import EvaluationMetricsCalculator
    ranked = EvaluationMetricsCalculator.rank_chunks_for_triage(
        final_state.get("chunks", []),
        final_state.get("eval_history", []),
        final_state.get("retry_counts", {})
    )

    for row in ranked:
        status_style = "green" if row["status"] == "auto_passed" else ("yellow" if row["status"] == "auto_passed_after_refinement" else "red")
        table.add_row(
            row["chunk_id"],
            row["language"],
            f"[{status_style}]{row['status']}[/{status_style}]",
            f"{row['confidence_score']:.2f}",
            row["line_range"]
        )

    console.print(table)
    console.print(f"\n[bold]Full Report Saved To:[/bold] {report_path}")
    console.print("[dim]Launch dashboard with: [bold]streamlit run src/dashboard/app.py[/bold][/dim]\n")


if __name__ == "__main__":
    main()
