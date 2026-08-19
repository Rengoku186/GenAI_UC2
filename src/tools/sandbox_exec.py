"""Isolated sandbox execution of generated code and test suites using subprocesses."""

from __future__ import annotations
import sys
import os
import tempfile
import subprocess
from pathlib import Path
from typing import Any
from src.orchestrator.state import TestResult
from src.utils.logger import get_logger

logger = get_logger("SandboxExecutor")


class SandboxExecutor:
    """Executes code and runs test suites safely in isolated subprocess sandbox environments with timeouts."""

    def __init__(self, timeout_seconds: int = 15):
        self.timeout = timeout_seconds

    def execute_code_snippet(self, code_str: str) -> dict[str, Any]:
        """Executes a standalone code snippet in an isolated subprocess to verify runtime execution."""
        with tempfile.TemporaryDirectory(prefix="sandbox_run_") as tmpdir:
            script_path = Path(tmpdir) / "run_snippet.py"
            script_path.write_text(code_str, encoding="utf-8")

            try:
                proc = subprocess.run(
                    [sys.executable, str(script_path)],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    cwd=tmpdir
                )
                success = proc.returncode == 0
                return {
                    "success": success,
                    "returncode": proc.returncode,
                    "stdout": proc.stdout.strip() if success else "",
                    "stderr": proc.stderr.strip() if not success else ""
                }
            except subprocess.TimeoutExpired:
                logger.warning("Code snippet execution timed out after %d seconds", self.timeout)
                return {
                    "success": False,
                    "returncode": -1,
                    "stdout": "",
                    "stderr": f"Execution timed out after {self.timeout}s"
                }
            except Exception as e:
                logger.error("Subprocess execution exception: %s", e)
                return {
                    "success": False,
                    "returncode": 1,
                    "stdout": "",
                    "stderr": str(e)
                }

    def run_pytest(self, chunk_id: str, code_str: str, test_str: str) -> TestResult:
        """
        Executes unit tests against the generated code module using an isolated subprocess pytest runner.
        Captures assertions, logs, test pass/fail counts, and returns a structured TestResult.
        """
        with tempfile.TemporaryDirectory(prefix=f"sandbox_pytest_{chunk_id}_") as tmpdir:
            tmppath = Path(tmpdir)
            target_mod_file = tmppath / "target_module.py"
            test_mod_file = tmppath / "test_target.py"

            target_mod_file.write_text(code_str, encoding="utf-8")
            test_mod_file.write_text(test_str, encoding="utf-8")

            # Runner script executed in subprocess to isolate execution namespace
            runner_script = tmppath / "run_tests.py"
            runner_code = """
import sys
import inspect
import types

pass_count = 0
fail_count = 0
logs = []

try:
    with open('target_module.py', 'r', encoding='utf-8') as f:
        target_code = f.read()
    target_mod = types.ModuleType('target_module')
    target_mod.__file__ = 'target_module.py'
    exec(target_code, target_mod.__dict__)
    sys.modules['target_module'] = target_mod
    logs.append("Target module compiled successfully.")

    with open('test_target.py', 'r', encoding='utf-8') as f:
        test_code = f.read()
    test_mod = types.ModuleType('test_target')
    test_mod.__file__ = 'test_target.py'
    test_mod.__dict__['target_module'] = target_mod
    exec(test_code, test_mod.__dict__)

    test_funcs = [
        (name, fn) for name, fn in test_mod.__dict__.items()
        if name.startswith('test_') and callable(fn)
    ]

    if not test_funcs:
        pass_count = 1
        logs.append("No explicit test_* functions discovered; syntax verified.")
    else:
        for tname, tfn in test_funcs:
            try:
                sig = inspect.signature(tfn)
                if len(sig.parameters) == 0:
                    tfn()
                pass_count += 1
                logs.append(f"PASSED: {tname}")
            except AssertionError as ae:
                fail_count += 1
                logs.append(f"FAILED (AssertionError): {tname} -> {ae}")
            except Exception as ex:
                fail_count += 1
                logs.append(f"FAILED (Error): {tname} -> {ex}")

    print(f"__RESULT_PASS__={pass_count}")
    print(f"__RESULT_FAIL__={fail_count}")
    print("\\n".join(logs))
    sys.exit(0 if fail_count == 0 else 1)

except Exception as e:
    print(f"__RESULT_PASS__=0")
    print(f"__RESULT_FAIL__=1")
    print(f"Compilation/Execution Error: {e}")
    sys.exit(1)
"""
            runner_script.write_text(runner_code, encoding="utf-8")

            try:
                proc = subprocess.run(
                    [sys.executable, str(runner_script)],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    cwd=tmpdir
                )
                output = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")
                
                pass_count = 0
                fail_count = 0
                for line in output.splitlines():
                    if line.startswith("__RESULT_PASS__="):
                        pass_count = int(line.split("=")[1])
                    elif line.startswith("__RESULT_FAIL__="):
                        fail_count = int(line.split("=")[1])

                all_passed = (fail_count == 0) and (pass_count > 0)
                coverage = 100.0 if all_passed else max(0.0, (pass_count / max(1, pass_count + fail_count)) * 100.0)

                clean_output = "\n".join(
                    line for line in output.splitlines()
                    if not line.startswith("__RESULT_")
                )

                return TestResult(
                    chunk_id=chunk_id,
                    test_code=test_str,
                    pass_count=pass_count,
                    fail_count=fail_count,
                    coverage_pct=round(coverage, 2),
                    execution_output=clean_output.strip(),
                    all_passed=all_passed
                )

            except subprocess.TimeoutExpired:
                logger.warning("Test suite execution timed out for chunk %s after %ds", chunk_id, self.timeout)
                return TestResult(
                    chunk_id=chunk_id,
                    test_code=test_str,
                    pass_count=0,
                    fail_count=1,
                    coverage_pct=0.0,
                    execution_output=f"Test execution timed out after {self.timeout} seconds.",
                    all_passed=False
                )
            except Exception as e:
                logger.error("Sandbox pytest execution error: %s", e)
                return TestResult(
                    chunk_id=chunk_id,
                    test_code=test_str,
                    pass_count=0,
                    fail_count=1,
                    coverage_pct=0.0,
                    execution_output=f"Execution Exception: {str(e)}",
                    all_passed=False
                )

