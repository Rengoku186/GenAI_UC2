"""Isolated sandbox execution of generated Python code and pytest suites."""

from __future__ import annotations
import os
import sys
import tempfile
import subprocess
import re
from pathlib import Path
from typing import Any
from src.orchestrator.state import TestResult


class SandboxExecutor:
    """Executes Python code and runs test suites safely in temporary isolated directories."""

    def __init__(self, timeout_seconds: int = 10):
        self.timeout = timeout_seconds

    def execute_code_snippet(self, code_str: str) -> dict[str, Any]:
        """Executes a standalone Python code snippet to check for runtime execution errors."""
        with tempfile.TemporaryDirectory(prefix="sandbox_run_") as tmpdir:
            file_path = Path(tmpdir) / "module.py"
            file_path.write_text(code_str, encoding="utf-8")

            try:
                proc = subprocess.run(
                    [sys.executable, str(file_path)],
                    cwd=tmpdir,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout
                )
                return {
                    "success": proc.returncode == 0,
                    "returncode": proc.returncode,
                    "stdout": proc.stdout,
                    "stderr": proc.stderr
                }
            except subprocess.TimeoutExpired:
                return {
                    "success": False,
                    "returncode": -1,
                    "stdout": "",
                    "stderr": f"Execution timed out after {self.timeout} seconds."
                }
            except Exception as e:
                return {
                    "success": False,
                    "returncode": -1,
                    "stdout": "",
                    "stderr": f"Execution failed: {str(e)}"
                }

    def run_pytest(self, chunk_id: str, code_str: str, test_str: str) -> TestResult:
        """Executes pytest against the generated code and unit tests, extracting pass/fail counts."""
        with tempfile.TemporaryDirectory(prefix=f"sandbox_test_{chunk_id}_") as tmpdir:
            tmppath = Path(tmpdir)
            code_file = tmppath / "target_module.py"
            code_file.write_text(code_str, encoding="utf-8")

            # Create an empty pytest.ini inside tmpdir to isolate configuration
            ini_file = tmppath / "pytest.ini"
            ini_file.write_text("[pytest]\n", encoding="utf-8")

            # Ensure auto import if missing
            sanitized_test = test_str
            if "from target_module import" not in sanitized_test and "import target_module" not in sanitized_test:
                sanitized_test = "from target_module import *\n\n" + sanitized_test

            test_file = tmppath / "test_target.py"
            test_file.write_text(sanitized_test, encoding="utf-8")

            # Explicitly disable external hooks/plugins that could stall network
            cmd = [
                sys.executable,
                "-m", "pytest",
                "--rootdir", str(tmppath),
                "-c", str(ini_file),
                "-p", "no:cacheprovider",
                "-p", "no:langsmith",
                "-p", "no:json-report",
                "-q",
                str(test_file)
            ]

            try:
                env = os.environ.copy()
                env["PYTHONPATH"] = str(tmppath) + os.pathsep + env.get("PYTHONPATH", "")
                env["LANGSMITH_TRACING"] = "false"
                env["LANGCHAIN_TRACING_V2"] = "false"
                
                proc = subprocess.run(
                    cmd,
                    cwd=tmppath,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    env=env
                )

                output = proc.stdout + "\n" + proc.stderr
                pass_count, fail_count = self._parse_pytest_counts(output)

                if proc.returncode == 0 and pass_count == 0:
                    pass_count = 1

                all_passed = (proc.returncode == 0) and (fail_count == 0) and (pass_count > 0)
                coverage = 100.0 if all_passed else (max(0.0, (pass_count / max(1, pass_count + fail_count)) * 100.0))

                return TestResult(
                    chunk_id=chunk_id,
                    test_code=test_str,
                    pass_count=pass_count,
                    fail_count=fail_count,
                    coverage_pct=round(coverage, 2),
                    execution_output=output.strip(),
                    all_passed=all_passed
                )

            except subprocess.TimeoutExpired:
                return TestResult(
                    chunk_id=chunk_id,
                    test_code=test_str,
                    pass_count=0,
                    fail_count=1,
                    coverage_pct=0.0,
                    execution_output=f"Pytest execution timed out after {self.timeout} seconds.",
                    all_passed=False
                )
            except Exception as e:
                return TestResult(
                    chunk_id=chunk_id,
                    test_code=test_str,
                    pass_count=0,
                    fail_count=1,
                    coverage_pct=0.0,
                    execution_output=f"Failed to execute pytest: {str(e)}",
                    all_passed=False
                )

    def _parse_pytest_counts(self, output: str) -> tuple[int, int]:
        """Parses pytest output for pass and fail numbers."""
        pass_count = 0
        fail_count = 0

        pass_match = re.search(r"(\d+)\s+passed", output)
        if pass_match:
            pass_count = int(pass_match.group(1))

        fail_match = re.search(r"(\d+)\s+failed", output)
        if fail_match:
            fail_count = int(fail_match.group(1))

        err_match = re.search(r"(\d+)\s+error", output)
        if err_match:
            fail_count += int(err_match.group(1))

        return pass_count, fail_count
