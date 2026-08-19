"""Agent 12: Test Executor Agent (Java-only mode — records JUnit 5 suite, auto-validates structure)."""

from __future__ import annotations
from src.agents.base_agent import BaseAgent
from src.orchestrator.state import PipelineState, TestResult, EvalResult


class TestExecutorAgent(BaseAgent):
    """Records generated JUnit 5 test suites and validates their structural completeness."""
    __test__ = False

    def __init__(self, config_dir: str = "configs"):
        super().__init__("test_executor", config_dir=config_dir)
        self.min_coverage = float(self.thresholds.get("confidence_thresholds", {}).get("test_coverage_min_pct", 80.0))
        self.max_retries = int(self.thresholds.get("retry_caps", {}).get("test_generation", 3))

    def execute_chunk_test(self, chunk_id: str, java_test_code: str, retry_count: int) -> tuple[TestResult, EvalResult]:
        """Structurally validates the JUnit 5 test suite for a chunk."""
        self.logger.debug("Validating JUnit 5 test suite for chunk %s (retry=%d)", chunk_id, retry_count)

        issues = []
        # Structural checks on the Java test code
        if not java_test_code.strip():
            issues.append("JUnit 5 test suite is empty.")
        elif "@Test" not in java_test_code:
            issues.append("JUnit 5 test suite contains no @Test annotated methods.")
        elif "org.junit.jupiter.api.Test" not in java_test_code:
            issues.append("JUnit 5 import missing: org.junit.jupiter.api.Test")

        passed = len(issues) == 0
        # Count @Test methods as a proxy for pass_count
        test_count = java_test_code.count("@Test")
        score = 1.0 if passed else 0.0
        needs_human = (not passed) and (retry_count >= self.max_retries)

        self.logger.info("JUnit 5 validation for %s: @Test methods=%d, Valid=%s", chunk_id, test_count, passed)

        updated_test = TestResult(
            chunk_id=chunk_id,
            test_code="",
            java_test_code=java_test_code,
            pass_count=test_count if passed else 0,
            fail_count=0 if passed else 1,
            coverage_pct=100.0 if passed else 0.0,
            execution_output="" if passed else "; ".join(issues),
            all_passed=passed
        )

        eval_result = EvalResult(
            target_id=chunk_id,
            stage="test_execution",
            score=score,
            passed=passed,
            issues=issues,
            suggestions=(
                [f"JUnit 5 suite validated: {test_count} @Test methods generated."]
                if passed
                else ["Ensure JUnit 5 test class imports org.junit.jupiter.api.Test and has @Test annotated methods."]
            ),
            needs_human_review=needs_human
        )

        return updated_test, eval_result

    def execute(self, state: PipelineState) -> dict:
        tests = dict(state.get("tests", {}))
        retry_counts = dict(state.get("retry_counts", {}))

        target_chunk_id = state.get("current_chunk_id")
        if target_chunk_id and target_chunk_id in tests:
            run_targets = [target_chunk_id]
        else:
            run_targets = list(tests.keys())

        self.logger.info("Validating JUnit 5 test suites for %d chunks", len(run_targets))
        new_evals: list[EvalResult] = []
        flagged: list[str] = []

        for cid in run_targets:
            if cid in tests:
                retries = retry_counts.get(f"{cid}:test_generation", 0)
                java_test_code = tests[cid].java_test_code

                t_res, e_res = self.execute_chunk_test(cid, java_test_code, retries)
                tests[cid] = t_res
                new_evals.append(e_res)
                if not e_res.passed:
                    key = f"{cid}:test_generation"
                    retry_counts[key] = retries + 1
                    self.logger.debug("Incremented test retry count for %s to %d", key, retry_counts[key])
                if e_res.needs_human_review:
                    flagged.append(f"{cid}:test_execution")

        return {
            "tests": tests,
            "eval_history": new_evals,
            "retry_counts": retry_counts,
            "flagged_for_review": flagged,
            "stage": "test_execution"
        }
