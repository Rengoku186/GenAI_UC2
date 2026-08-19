"""AST analysis and language detection tools for legacy code."""

from __future__ import annotations
import os
from pathlib import Path
from typing import Literal


class ASTTools:
    """Utility methods for source file inspection, language detection, and token statistics."""

    @staticmethod
    def detect_language(file_path: str | Path) -> Literal["cobol", "vb", "java", "unknown"]:
        """Infers legacy language from file extension or content keywords."""
        path = Path(file_path)
        ext = path.suffix.lower()

        if ext in [".cbl", ".cob", ".cobol", ".cpy"]:
            return "cobol"
        elif ext in [".vb", ".vbs", ".bas", ".cls", ".frm"]:
            return "vb"
        elif ext in [".java", ".jav"]:
            return "java"

        # Content fallback
        if path.exists():
            try:
                sample = path.read_text(encoding="utf-8", errors="ignore")[:2000].upper()
                if "IDENTIFICATION DIVISION" in sample or "PROCEDURE DIVISION" in sample:
                    return "cobol"
                elif "NAMESPACE" in sample or "PUBLIC CLASS" in sample and "END CLASS" in sample:
                    return "vb"
                elif "PACKAGE " in sample or ("PUBLIC CLASS " in sample and "{" in sample):
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
