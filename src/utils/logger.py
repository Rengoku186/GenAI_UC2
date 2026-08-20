"""Unified logging configuration for the Legacy Code Modernization Multi-Agent System."""

from __future__ import annotations
import os
import sys
import logging
from pathlib import Path


def setup_logging(
    log_level: str | None = None,
    log_file: str | Path | None = None
) -> None:
    """Configures root and application loggers with formatted console and optional file handlers."""
    level_name = (log_level or os.getenv("LOG_LEVEL", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)

    log_format = "%(asctime)s | %(levelname)-8s | [%(name)s] %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout)
    ]

    if log_file is None:
        from datetime import datetime
        log_file = Path(".logs") / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(log_format, date_format))
        handlers.append(file_handler)

    logging.basicConfig(
        level=level,
        format=log_format,
        datefmt=date_format,
        handlers=handlers,
        force=True
    )


def get_logger(name: str) -> logging.Logger:
    """Returns a named logger instance configured for the modernization pipeline."""
    return logging.getLogger(name)
