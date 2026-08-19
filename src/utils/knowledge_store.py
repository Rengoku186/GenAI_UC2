"""Writes a .knowledge_store file to the project root after each pipeline run.

The file is a structured, human-readable plain-text log of every agent execution
event captured during the run. It is appended (not overwritten) so all runs are
preserved for backtracking.
"""

from __future__ import annotations
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

KNOWLEDGE_STORE_PATH = Path(".knowledge_store")

# Width of each log line in the file
_LINE_WIDTH = 100

_SEPARATOR   = "=" * _LINE_WIDTH
_SUBSEP      = "-" * _LINE_WIDTH

AGENT_STAGE_MAP = {
    "ingestion_chunker":    "Ingestion",
    "chunk_evaluator":      "Evaluation",
    "dependency_mapper":    "Analysis",
    "dependency_evaluator": "Evaluation",
    "documenter":           "Documentation",
    "doc_evaluator":        "Evaluation",
    "doc_refiner":          "Refinement",
    "code_generator":       "Generation",
    "code_evaluator":       "Evaluation",
    "code_refiner":         "Refinement",
    "test_generator":       "Testing",
    "test_executor":        "Testing",
    "Orchestrator":         "Pipeline",
    "Router":               "Pipeline",
    "ReportBuilder":        "Reporting",
}


def _fmt_ts(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S.") + f"{dt.microsecond // 1000:03d} UTC"
    except Exception:
        return iso


def write_knowledge_store(
    entries: list[dict[str, Any]],
    run_id: str,
    source_files: list[str],
    chunk_summary: dict[str, Any],
    output_path: Path = KNOWLEDGE_STORE_PATH,
) -> Path:
    """Appends a full run trace block to the .knowledge_store file.

    Args:
        entries:       Structured log entries from PipelineMemoryHandler.
        run_id:        Unique identifier for this pipeline run.
        source_files:  List of source files processed.
        chunk_summary: Dict with total_chunks, status_summary, avg_confidence.
        output_path:   Path to the .knowledge_store file (default: project root).

    Returns:
        Resolved path to the written file.
    """
    now = datetime.now(timezone.utc)

    lines: list[str] = []

    # ── Run header ────────────────────────────────────────────────────────────
    lines += [
        "",
        _SEPARATOR,
        f"  PIPELINE RUN: {run_id}",
        f"  Timestamp  : {now.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"  Sources    : {', '.join(source_files) or '(none)'}",
        f"  Chunks     : {chunk_summary.get('total_chunks', 0)}  |  "
        f"Avg Confidence: {chunk_summary.get('overall_average_confidence', 0):.1%}",
        _SEPARATOR,
    ]

    # ── Status summary ────────────────────────────────────────────────────────
    ss = chunk_summary.get("status_summary", {})
    lines += [
        "",
        "  STATUS SUMMARY",
        _SUBSEP,
        f"  ✅  Auto-Passed         : {ss.get('auto_passed', 0)}",
        f"  🔄  Refined             : {ss.get('auto_passed_after_refinement', 0)}",
        f"  ⚠️   Needs Human Review  : {ss.get('flagged_for_human_review', 0)}",
        "",
    ]

    # ── Agent execution trace ─────────────────────────────────────────────────
    if entries:
        lines += [
            "  AGENT EXECUTION TRACE",
            _SUBSEP,
        ]

        current_agent = None
        for e in entries:
            agent    = e.get("agent") or e.get("category", "?")
            level    = e.get("level", "INFO")
            ts_str   = _fmt_ts(e.get("ts", ""))
            raw_msg  = e.get("raw_message", e.get("message", ""))
            stage    = AGENT_STAGE_MAP.get(agent, "—")

            # Print a sub-header when the agent changes
            if agent != current_agent:
                current_agent = agent
                lines += [
                    "",
                    f"  [{stage.upper()}] >> {agent}",
                ]

            # Indent and wrap the log line
            prefix   = f"    {ts_str}  [{level:<8}]  "
            wrapped  = textwrap.fill(
                raw_msg,
                width=_LINE_WIDTH,
                initial_indent=prefix,
                subsequent_indent=" " * len(prefix),
            )
            lines.append(wrapped)
    else:
        lines += ["", "  (No execution trace entries captured for this run)", ""]

    lines += ["", _SEPARATOR, ""]

    block = "\n".join(lines)

    # Append to the file (creates it if it doesn't exist)
    with output_path.open("a", encoding="utf-8") as f:
        f.write(block)

    return output_path.resolve()


def read_knowledge_store(path: Path = KNOWLEDGE_STORE_PATH) -> str | None:
    """Reads the full .knowledge_store file content. Returns None if not found."""
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def parse_runs_from_knowledge_store(path: Path = KNOWLEDGE_STORE_PATH) -> list[dict[str, Any]]:
    """Parses individual run blocks from the .knowledge_store file.

    Returns a list of dicts with keys: run_id, timestamp, raw_block.
    Newest run is first.
    """
    if not path.exists():
        return []

    content = path.read_text(encoding="utf-8")
    sep = "=" * _LINE_WIDTH

    # Split on the separator lines that open each run block
    blocks = content.split(sep)
    runs: list[dict[str, Any]] = []

    i = 0
    while i < len(blocks):
        block = blocks[i].strip()
        if block.startswith("PIPELINE RUN:"):
            lines = block.splitlines()
            run_id = lines[0].replace("PIPELINE RUN:", "").strip() if lines else "unknown"
            ts_line = next((l for l in lines if "Timestamp" in l), "")
            ts = ts_line.split(":", 1)[-1].strip() if ts_line else ""
            # Merge this header + next content block (before next separator)
            raw = sep + "\n" + block
            if i + 1 < len(blocks):
                raw += sep + "\n" + blocks[i + 1]
                i += 1
            runs.append({"run_id": run_id, "timestamp": ts, "raw_block": raw})
        i += 1

    return list(reversed(runs))  # newest first
