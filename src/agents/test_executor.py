"""Agent 12: Test Executor Agent."""

from __future__ import annotations
from src.agents.base_agent import BaseAgent
from src.orchestrator.state import PipelineState, TestResult, EvalResult
from src.tools.sandbox_exec import SandboxExecutor


class TestExecutorAgent(BaseAgent):
    """Executes generated pytest suites in an isolated sandbox and captures coverage/pass/fail results."""
    __test__ = False

    def __init__(self, config_dir: str = "configs"):
        super().__init__("test_executor", config_dir=config_dir)
        self.min_coverage = float(self.thresholds.get("confidence_thresholds", {}).get("test_coverage_min_pct", 80.0))
        self.max_retries = int(self.thresholds.get("retry_caps", {}).get("test_generation", 3))
        self.sandbox = SandboxExecutor(timeout_seconds=15)

    def execute_chunk_test(self, chunk_id: str, code_str: str, test_str: str, retry_count: int) -> tuple[TestResult, EvalResult]:
        """Runs pytest on the chunk in the sandbox."""
        test_result = self.sandbox.run_pytest(chunk_id, code_str, test_str)
        
        passed = test_result.all_passed and test_result.coverage_pct >= self.min_coverage
        score = 1.0 if passed else (0.5 if test_result.pass_count > 0 else 0.0)
        
        issues = []
        if not test_result.all_passed:
            issues.append(f"Pytest failures detected: {test_result.fail_count} failed tests.")
        if test_result.coverage_pct < self.min_coverage:
            issues.append(f"Test coverage {test_result.coverage_pct}% is below minimum required {self.min_coverage}%.")

        needs_human = (not passed) and (retry_count >= self.max_retries)

        eval_result = EvalResult(
            target_id=chunk_id,
            stage="test_execution",
            score=score,
            passed=passed,
            issues=issues,
            suggestions=["Refine Python code logic or test assertions to achieve 100% pass rate."] if not passed else ["All unit tests passed."],
            needs_human_review=needs_human
        )

        return test_result, eval_result

    def execute(self, state: PipelineState) -> dict:
        generated = state.get("generated_code", {})
        tests = dict(state.get("tests", {}))
        retry_counts = state.get("retry_counts", {})

        target_chunk_id = state.get("current_chunk_id")
        if target_chunk_id and target_chunk_id in tests and target_chunk_id in generated:
            run_targets = [target_chunk_id]
        else:
            run_targets = list(tests.keys())

        new_evals: list[EvalResult] = []
        flagged: list[str] = []

        for cid in run_targets:
            if cid in generated and cid in tests:
                retries = retry_counts.get(f"{cid}:test_generation", 0)
                code_str = generated[cid].target_code
                test_str = tests[cid].test_code

                t_res, e_res = self.execute_chunk_test(cid, code_str, test_str, retries)
                tests[cid] = t_res
                new_evals.append(e_res)
                if e_res.needs_human_review:
                    flagged.append(f"{cid}:test_execution")

        return {
            "tests": tests,
            "eval_history": new_evals,
            "flagged_for_review": flagged,
            "stage": "test_execution"
        }
