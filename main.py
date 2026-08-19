"""Main entrypoint for the Legacy Code Modernization Agentic System.

Provides a unified, beginner-friendly CLI to run the modernization pipeline,
launch the Streamlit triage dashboard, or run test suites.

Usage:
    python main.py                              # Run pipeline on default legacy source files
    python main.py path/to/legacy/File.java     # Run pipeline on specific file(s)
    python main.py --dashboard                  # Launch the Streamlit observability dashboard
    python main.py --test                       # Run the test suite
"""

import sys
import os
import argparse
from pathlib import Path

# Ensure workspace root is in sys.path so 'src' imports work seamlessly from any CWD
WORKSPACE_ROOT = Path(__file__).resolve().parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))


def launch_dashboard():
    """Launches the Streamlit dashboard as a subprocess."""
    import subprocess
    app_path = WORKSPACE_ROOT / "src" / "dashboard" / "app.py"
    print(f"\n🚀 Launching Streamlit Observability Dashboard: {app_path}\n")
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path)])


def run_tests():
    """Runs pytest test suite."""
    import pytest
    print("\n🧪 Running Pytest Test Suite...\n")
    sys.exit(pytest.main(["-v", str(WORKSPACE_ROOT / "tests")]))


def run_modernization(source_files: list[str] | None = None):
    """Runs the LangGraph Modernization Pipeline."""
    from src.orchestrator.graph import run_pipeline, setup_logging
    from src.evaluation.metrics import EvaluationMetricsCalculator
    from rich.console import Console
    from rich.table import Table

    setup_logging()
    console = Console()
    console.print("\n[bold green]⚡ === Legacy Code Modernization Agentic System === ⚡[/bold green]\n")

    if not source_files:
        sample_dir = WORKSPACE_ROOT / "data" / "legacy_source"
        source_paths = [
            str(p) for p in sample_dir.glob("*.*")
            if p.suffix.lower() in [".cbl", ".vb", ".java"]
        ]
    else:
        source_paths = [str(Path(f).resolve()) for f in source_files]

    if not source_paths:
        console.print("[bold red]❌ Error: No legacy source files found to modernize![/bold red]")
        sys.exit(1)

    console.print(f"[bold cyan]Target Source Files ({len(source_paths)}):[/bold cyan]")
    for p in source_paths:
        console.print(f"  • {p}")
    console.print("")

    with console.status("[bold blue]Executing Autonomous Multi-Agent Modernization Pipeline...[/bold blue]"):
        final_state = run_pipeline(source_paths)

    console.print("\n[bold green]✅ Modernization Pipeline Run Completed Successfully![/bold green]\n")

    # Display Triage Summary Table
    table = Table(title="Modernization Chunks Triage Summary")
    table.add_column("Chunk ID", style="cyan")
    table.add_column("Lang", style="magenta")
    table.add_column("Status", style="bold")
    table.add_column("Confidence", justify="right")
    table.add_column("Source Range")

    report_path = final_state.get("metadata", {}).get("report_path", "outputs/evaluation_reports/latest_report.json")
    ranked = EvaluationMetricsCalculator.rank_chunks_for_triage(
        final_state.get("chunks", []),
        final_state.get("eval_history", []),
        final_state.get("retry_counts", {})
    )

    for row in ranked:
        status = row["status"]
        if status == "auto_passed":
            status_style = "green"
            badge = "🟢 Auto-Passed"
        elif status == "auto_passed_after_refinement":
            status_style = "yellow"
            badge = "🟡 Auto-Passed (Refined)"
        else:
            status_style = "red"
            badge = "🔴 Flagged for Review"

        table.add_row(
            row["chunk_id"],
            row["language"],
            f"[{status_style}]{badge}[/{status_style}]",
            f"{row['confidence_score']:.2f}",
            row["line_range"]
        )

    console.print(table)
    console.print(f"\n[bold]📊 Full Evaluation Report Saved To:[/bold] {report_path}")
    console.print("[bold blue]💡 Launch dashboard anytime with:[/bold blue] [bold yellow]python main.py --dashboard[/bold yellow]\n")


def main():
    parser = argparse.ArgumentParser(
        description="Legacy Code Modernization Agentic System - CLI Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                                   # Run modernization on all sample legacy files
  python main.py data/legacy_source/AccountProcessor.java  # Modernize a specific file
  python main.py --dashboard                       # Launch Streamlit web dashboard
  python main.py --test                            # Run unit & E2E tests
        """
    )
    parser.add_argument("files", nargs="*", help="Legacy source code files to modernize (COBOL, VB, Java)")
    parser.add_argument("--dashboard", action="store_true", help="Launch the Streamlit triage dashboard")
    parser.add_argument("--test", action="store_true", help="Run the test suite")

    args = parser.parse_args()

    if args.dashboard:
        launch_dashboard()
    elif args.test:
        run_tests()
    else:
        run_modernization(args.files if args.files else None)


if __name__ == "__main__":
    main()
