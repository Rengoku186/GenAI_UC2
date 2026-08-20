"""AST analysis and language detection tools for legacy code."""

from __future__ import annotations
import os
from pathlib import Path
from typing import Literal


class ASTTools:
    """Utility methods for source file inspection, language detection, and token statistics."""

    @staticmethod
    def detect_language(file_path: str | Path) -> Literal["java", "unknown"]:
        """Naive heuristic to guess language from file extension or content snippet."""
        path = Path(file_path)
        ext = path.suffix.lower()

        if ext == ".java":
            return "java"

        if path.exists():
            try:
                content = path.read_text(encoding="utf-8")[:1000].lower()
                if "class " in content and "public " in content:
                    return "java"
            except Exception:
                pass

        return "unknown"

    @staticmethod
    def get_file_stats(content: str) -> dict[str, int]:
        """Calculates line counts, comment lines, and blank lines."""
        lines = content.splitlines()
        total_lines = len(lines)
        blank_lines = sum(1 for l in lines if not l.strip())
        comment_lines = sum(
            1 for l in lines 
            if l.strip().startswith(("*", "/", "'", "//", "/*", "--", "#"))
        )
        code_lines = total_lines - blank_lines - comment_lines
        return {
            "total_lines": total_lines,
            "code_lines": max(0, code_lines),
            "blank_lines": blank_lines,
            "comment_lines": comment_lines
        }
