"""In-memory structured log handler that captures pipeline execution events for the knowledge store."""

from __future__ import annotations
import logging
import threading
from datetime import datetime, timezone
from typing import Any


class PipelineMemoryHandler(logging.Handler):
    """Thread-safe in-memory log handler that collects structured log records.
    
    One singleton instance is shared across the pipeline run. The ReportBuilder
    reads the captured entries and writes them into the JSON report so they can
    be replayed in the dashboard knowledge store tab.
    """

    _instance: "PipelineMemoryHandler | None" = None
    _lock: threading.Lock = threading.Lock()

    # Loggers that belong to the pipeline (matched by prefix)
    PIPELINE_PREFIXES = ("Agent.", "Orchestrator", "Router", "ReportBuilder")

    def __new__(cls) -> "PipelineMemoryHandler":
        with cls._lock:
            if cls._instance is None:
                inst = super().__new__(cls)
                inst._entries: list[dict[str, Any]] = []
                inst._entry_lock = threading.Lock()
                super(PipelineMemoryHandler, inst).__init__(level=logging.DEBUG)
                cls._instance = inst
            return cls._instance

    # ── Public API ────────────────────────────────────────────────────────────

    def emit(self, record: logging.LogRecord) -> None:
        """Called by the logging system for every log record."""
        # Only capture pipeline-related loggers
        if not any(record.name.startswith(p) for p in self.PIPELINE_PREFIXES):
            return

        # Parse agent name from logger name, e.g. "Agent.ingestion_chunker" → "ingestion_chunker"
        parts = record.name.split(".", 1)
        category = parts[0]               # "Agent", "Orchestrator", "Router", …
        agent = parts[1] if len(parts) > 1 else record.name

        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "category": category,
            "agent": agent,
            "message": self.format(record),
            "raw_message": record.getMessage(),
        }
        with self._entry_lock:
            self._entries.append(entry)

    def flush_entries(self) -> list[dict[str, Any]]:
        """Returns all captured entries and clears the buffer."""
        with self._entry_lock:
            entries = list(self._entries)
            self._entries.clear()
        return entries

    def get_entries(self) -> list[dict[str, Any]]:
        """Returns all captured entries without clearing."""
        with self._entry_lock:
            return list(self._entries)

    def reset(self) -> None:
        """Clears all captured log entries (call before each pipeline run)."""
        with self._entry_lock:
            self._entries.clear()

    # ── Install / uninstall ───────────────────────────────────────────────────

    @classmethod
    def install(cls) -> "PipelineMemoryHandler":
        """Attaches this handler to the root logger (idempotent)."""
        handler = cls()
        root = logging.getLogger()
        if handler not in root.handlers:
            handler.setFormatter(logging.Formatter(
                "%(asctime)s | %(levelname)-8s | [%(name)s] %(message)s",
                "%Y-%m-%d %H:%M:%S"
            ))
            root.addHandler(handler)
        return handler
