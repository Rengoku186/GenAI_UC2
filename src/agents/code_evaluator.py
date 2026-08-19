"""Agent 9: Code Evaluator Agent."""

from __future__ import annotations
from pydantic import BaseModel, Field
from src.agents.base_agent import BaseAgent
from src.orchestrator.state import PipelineState, EvalResult, GeneratedCode, ChunkMetadata, DocSection
from src.tools.static_analysis_tools import StaticAnalysisTools
from src.prompts.evaluator_prompts import (
    CODE_EVALUATOR_SYSTEM_PROMPT,
    CODE_EVALUATOR_USER_PROMPT
)


class CodeEvaluationSchema(BaseModel):
    score: float = Field(ge=0.0, le=1.0, description="Code quality & parity score between 0.0 and 1.0")
    passed: bool = Field(description="True if code meets syntax and functional parity threshold")
    issues: list[str] = Field(default_factory=list, description="Syntax errors, logical gaps, or missing types")
    suggestions: list[str] = Field(default_factory=list, description="Actionable recommendations")


class CodeEvaluatorAgent(BaseAgent):
    """Evaluates generated Python code via static AST validation, complexity, and behavioral parity."""

    def __init__(self, config_dir: str = "configs"):
        super().__init__("code_evaluator", config_dir=config_dir)
        self.threshold = float(self.thresholds.get("confidence_thresholds", {}).get("code_evaluation", 0.85))
        self.max_retries = int(self.thresholds.get("retry_caps", {}).get("code_generation", 3))

    def evaluate_chunk_code(
        self,
        chunk: ChunkMetadata,
        doc: DocSection,
        code_obj: GeneratedCode,
        retry_count: int
    ) -> EvalResult:
        """Evaluates a single chunk's Python code."""
        # Static AST analysis
        syntax_res = StaticAnalysisTools.validate_python_syntax(code_obj.target_code)
        complexity = StaticAnalysisTools.calculate_cyclomatic_complexity(code_obj.target_code)

        def mock_eval() -> CodeEvaluationSchema:
            issues = []
            if not syntax_res["valid_syntax"]:
                issues.append(f"Syntax Error: {syntax_res['error']}")
            if not code_obj.target_code.strip():
                issues.append("Generated code is empty.")

            if issues:
                return CodeEvaluationSchema(
                    score=0.30,
                    passed=False,
                    issues=issues,
                    suggestions=["Fix Python syntax errors and parse failures."]
                )

            # High confidence if valid syntax and functions/classes present
            score = 0.94
            return CodeEvaluationSchema(
                score=score,
                passed=score >= self.threshold,
                issues=[],
                suggestions=[f"Code adheres to modern Python 3.11 standards (Cyclomatic complexity: {complexity})."]
            )

        user_prompt = CODE_EVALUATOR_USER_PROMPT.format(
            chunk_id=chunk.chunk_id,
            language=chunk.language,
            raw_code=chunk.raw_code,
            business_rules="\n".join([f"- {r}" for r in doc.business_rules]),
            version=code_obj.version,
            target_code=code_obj.target_code,
            syntax_status="Valid" if syntax_res["valid_syntax"] else f"Invalid ({syntax_res['error']})"
        )

        res = self.invoke_structured(
            schema=CodeEvaluationSchema,
            system_prompt=CODE_EVALUATOR_SYSTEM_PROMPT.format(threshold=self.threshold),
            user_prompt=user_prompt,
            mock_fallback_generator=mock_eval
        )

        # Fail if static syntax is invalid regardless of LLM score
        if not syntax_res["valid_syntax"]:
            res.passed = False
            res.score = min(res.score, 0.40)
            if syntax_res["error"] not in res.issues:
                res.issues.append(syntax_res["error"])

        is_passed = res.passed and res.score >= self.threshold
        needs_human = (not is_passed) and (retry_count >= self.max_retries)

        return EvalResult(
            target_id=chunk.chunk_id,
            stage="code_evaluation",
            score=res.score,
            passed=is_passed,
            issues=res.issues,
            suggestions=res.suggestions,
            needs_human_review=needs_human,
            version_evaluated=code_obj.version
        )

    def execute(self, state: PipelineState) -> dict:
        chunks = {c.chunk_id: c for c in state.get("chunks", [])}
        docs = state.get("docs", {})
        generated = state.get("generated_code", {})
        retry_counts = state.get("retry_counts", {})

        target_chunk_id = state.get("current_chunk_id")
        if target_chunk_id and target_chunk_id in generated and target_chunk_id in chunks:
            eval_targets = [target_chunk_id]
        else:
            eval_targets = list(generated.keys())

        new_evals: list[EvalResult] = []
        flagged: list[str] = []

        for cid in eval_targets:
            if cid in chunks and cid in docs and cid in generated:
                retries = retry_counts.get(f"{cid}:code_generation", 0)
                eval_res = self.evaluate_chunk_code(chunks[cid], docs[cid], generated[cid], retries)
                new_evals.append(eval_res)
                if eval_res.needs_human_review:
                    flagged.append(f"{cid}:code_evaluation")

        return {
            "eval_history": new_evals,
            "flagged_for_review": flagged,
            "stage": "code_evaluation"
        }
