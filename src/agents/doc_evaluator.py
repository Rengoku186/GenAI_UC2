"""Agent 6: Doc Evaluator Agent."""

from __future__ import annotations
from pydantic import BaseModel, Field
from src.agents.base_agent import BaseAgent
from src.orchestrator.state import PipelineState, EvalResult, DocSection, ChunkMetadata
from src.prompts.evaluator_prompts import (
    DOC_EVALUATOR_SYSTEM_PROMPT,
    DOC_EVALUATOR_USER_PROMPT
)


class DocEvaluationSchema(BaseModel):
    score: float = Field(ge=0.0, le=1.0, description="Quality & fidelity score between 0.0 and 1.0")
    passed: bool = Field(description="Whether documentation meets threshold")
    issues: list[str] = Field(default_factory=list, description="Omissions, inaccuracies or hallucinations")
    suggestions: list[str] = Field(default_factory=list, description="Actionable recommendations")


class DocEvaluatorAgent(BaseAgent):
    """Evaluates documentation completeness, hallucination vs source, and business rule coverage."""

    def __init__(self, config_dir: str = "configs"):
        super().__init__("doc_evaluator", config_dir=config_dir)
        self.threshold = float(self.thresholds.get("confidence_thresholds", {}).get("doc_evaluation", 0.80))
        self.max_retries = int(self.thresholds.get("retry_caps", {}).get("documentation", 3))

    def evaluate_chunk_doc(self, chunk: ChunkMetadata, doc: DocSection, retry_count: int) -> EvalResult:
        """Evaluates documentation for a single chunk."""
        self.logger.debug("Evaluating doc for chunk %s (v%d, retry=%d)", chunk.chunk_id, doc.version, retry_count)
        
        def mock_eval() -> DocEvaluationSchema:
            issues = []
            if not doc.business_rules:
                issues.append("Business rules list is empty.")
            if not doc.inputs:
                issues.append("Inputs list is empty.")
            if not doc.outputs:
                issues.append("Outputs list is empty.")

            score = 0.92 if not issues else 0.65
            return DocEvaluationSchema(
                score=score,
                passed=score >= self.threshold,
                issues=issues,
                suggestions=["Doc covers all inputs, outputs, and formulas faithfully."] if not issues else ["Add missing business rules."]
            )

        user_prompt = DOC_EVALUATOR_USER_PROMPT.format(
            chunk_id=chunk.chunk_id,
            language=chunk.language,
            raw_code=chunk.raw_code,
            version=doc.version,
            purpose=doc.purpose,
            inputs=", ".join(doc.inputs),
            outputs=", ".join(doc.outputs),
            business_rules="\n".join([f"- {r}" for r in doc.business_rules]),
            control_flow=doc.control_flow
        )

        res = self.invoke_structured(
            schema=DocEvaluationSchema,
            system_prompt=DOC_EVALUATOR_SYSTEM_PROMPT.format(threshold=self.threshold),
            user_prompt=user_prompt,
            mock_fallback_generator=mock_eval
        )

        is_passed = res.passed and res.score >= self.threshold
        needs_human = (not is_passed) and (retry_count >= self.max_retries)
        self.logger.info("Doc evaluation for %s: Score=%.2f, Passed=%s, NeedsReview=%s", chunk.chunk_id, res.score, is_passed, needs_human)

        return EvalResult(
            target_id=chunk.chunk_id,
            stage="doc_evaluation",
            score=res.score,
            passed=is_passed,
            issues=res.issues,
            suggestions=res.suggestions,
            needs_human_review=needs_human,
            version_evaluated=doc.version
        )

    def execute(self, state: PipelineState) -> dict:
        chunks = {c.chunk_id: c for c in state.get("chunks", [])}
        docs = state.get("docs", {})
        retry_counts = state.get("retry_counts", {})
        
        target_chunk_id = state.get("current_chunk_id")
        if target_chunk_id and target_chunk_id in docs and target_chunk_id in chunks:
            eval_targets = [target_chunk_id]
        else:
            eval_targets = list(docs.keys())

        self.logger.info("Evaluating documentation across %d chunks", len(eval_targets))
        new_evals: list[EvalResult] = []
        flagged: list[str] = []

        for cid in eval_targets:
            if cid in chunks and cid in docs:
                retries = retry_counts.get(f"{cid}:documentation", 0)
                eval_res = self.evaluate_chunk_doc(chunks[cid], docs[cid], retries)
                new_evals.append(eval_res)
                if eval_res.needs_human_review:
                    flagged.append(f"{cid}:doc_evaluation")

        return {
            "eval_history": new_evals,
            "flagged_for_review": flagged,
            "stage": "doc_evaluation"
        }
