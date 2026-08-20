"""Java compilation utility — runs javac on synthesized Java files and parses errors."""

from __future__ import annotations
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from src.utils.logger import get_logger

logger = get_logger("JavaCompiler")


@dataclass
class CompileResult:
    """Result of a javac compilation attempt."""
    compiled: bool
    errors: list[str] = field(default_factory=list)
    raw_output: str = ""


class JavaCompiler:
    """Compiles Java source using the system javac executable."""

    @staticmethod
    def is_available() -> bool:
        """Returns True if javac is on the system PATH."""
        return shutil.which("javac") is not None

    @classmethod
    def compile(cls, java_code: str, class_name: str) -> CompileResult:
        """
        Writes java_code to a temp file named <class_name>.java and compiles it.

        Args:
            java_code:   Full Java source text to compile.
            class_name:  The public class name (used to name the .java file).

        Returns:
            CompileResult with compiled=True and empty errors on success, or
            compiled=False with parsed error messages on failure.
        """
        if not cls.is_available():
            logger.warning("javac not found on PATH — skipping compilation check.")
            return CompileResult(compiled=True, errors=[], raw_output="javac not available")

        with tempfile.TemporaryDirectory(prefix="javac_check_") as tmpdir:
            src_file = Path(tmpdir) / f"{class_name}.java"
            src_file.write_text(java_code, encoding="utf-8")

            try:
                proc = subprocess.run(
                    ["javac", "-nowarn", str(src_file)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=tmpdir,
                )
                raw = (proc.stdout + proc.stderr).strip()
                logger.debug("javac exit code=%d for %s.java", proc.returncode, class_name)

                if proc.returncode == 0:
                    logger.info("javac: %s.java compiled successfully.", class_name)
                    return CompileResult(compiled=True, errors=[], raw_output=raw)

                errors = cls._parse_errors(raw, class_name)
                logger.warning(
                    "javac: %s.java has %d compile error(s).", class_name, len(errors)
                )
                return CompileResult(compiled=False, errors=errors, raw_output=raw)

            except subprocess.TimeoutExpired:
                logger.error("javac timed out for %s.java", class_name)
                return CompileResult(compiled=False, errors=["Compilation timed out after 30s."], raw_output="timeout")
            except Exception as exc:
                logger.error("javac invocation failed: %s", exc)
                return CompileResult(compiled=False, errors=[str(exc)], raw_output=str(exc))

    @staticmethod
    def _parse_errors(raw_output: str, class_name: str) -> list[str]:
        """Strips temp-dir paths from javac error lines for clean reporting."""
        errors: list[str] = []
        for line in raw_output.splitlines():
            line = line.strip()
            if not line:
                continue
            # Normalize absolute temp path to just <ClassName>.java
            line = re.sub(r".*[\\/]" + re.escape(class_name) + r"\.java", f"{class_name}.java", line)
            if line:
                errors.append(line)
        return errors
