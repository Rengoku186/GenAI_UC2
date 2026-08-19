"""Centralised logging configuration for the GenAI Legacy Code Pipeline.

Call ``setup_logging()`` once at process startup (in main.py / run_phase1.py).
After that every ``logging.getLogger(__name__)`` in any module — Dependency
Scanner, Splitter, Documenter, Evaluator, Orchestrator — will automatically
write to BOTH:

  * The terminal  (INFO and above, plain-text)
  * A timestamped log file under ``logs/``  (DEBUG and above, plain-text)

Log file naming:
    logs/pipeline_YYYYMMDD_HHMMSS.log

On failure you can inspect the full DEBUG-level trace in that file to see
exactly which chunk, which agent, and which LLM call broke.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_logger(name: str) -> logging.Logger:
    """Return a module logger without configuring global logging.

    Library modules use this helper at import time. Application entry points
    remain responsible for calling :func:`setup_logging` once, which avoids
    adding duplicate handlers during tests, worker startup, or imports.
    """
    return logging.getLogger(name)


def setup_logging(
    log_dir: str = "logs",
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
    run_label: str | None = None,
) -> str:
    """Configure root logger with a console handler and a file handler.

    Args:
        log_dir:       Directory where log files are written. Created if absent.
        console_level: Minimum level shown in the terminal (default INFO).
        file_level:    Minimum level written to the log file (default DEBUG).
        run_label:     Optional suffix appended to the log filename, e.g. the
                       input filename stem. Defaults to a timestamp.

    Returns:
        Absolute path of the log file that was created.
    """
    # ------------------------------------------------------------------ dirs
    os.makedirs(log_dir, exist_ok=True)

    # ----------------------------------------------------------------- naming
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    label = f"_{run_label}" if run_label else ""
    log_filename = f"pipeline_{timestamp}{label}.log"
    log_path = os.path.abspath(os.path.join(log_dir, log_filename))

    # --------------------------------------------------------------- root logger
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)   # capture everything; handlers filter down

    # Remove any handlers that Python or a library added before us
    root.handlers.clear()

    # --------------------------------------------------------- file handler
    file_fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(file_level)
    fh.setFormatter(file_fmt)
    root.addHandler(fh)

    # ------------------------------------------------------ console handler
    console_fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)s - %(message)s",
        datefmt="%H:%M:%S",
    )
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(console_level)
    ch.setFormatter(console_fmt)
    root.addHandler(ch)

    # ------------------------------------------------- suppress noisy libs
    # Third-party libraries that flood DEBUG output with irrelevant internals
    for noisy in (
        "httpx",
        "httpcore",
        "urllib3",
        "openai",
        "anthropic",
        "google.auth",
        "google.api_core",
        "huggingface_hub",
        "transformers",
        "langchain_core",
        "langchain",
        "langgraph",
        "asyncio",
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # ------------------------------------------------- first log line
    root.info("=" * 70)
    root.info("Pipeline logging initialised")
    root.info("  Console : %s+", logging.getLevelName(console_level))
    root.info("  Log file: %s  (DEBUG+)", log_path)
    root.info("=" * 70)

    return log_path
