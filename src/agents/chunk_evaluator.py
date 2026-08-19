"""Agent 3: Chunk Evaluator Agent."""

from __future__ import annotations
from pydantic import BaseModel, Field
from src.agents.base_agent import BaseAgent
from src.orchestrator.state import PipelineState, EvalResult
from src.prompts.evaluator_prompts import (
    CHUNK_EVALUATOR_SYSTEM_PROMPT,
    CHUNK_EVALUATOR_USER_PROMPT
)


class ChunkEvaluationSchema(BaseModel):
    """Schema for chunk evaluation structured output."""
    score: float = Field(ge=0.0, le=1.0, description="Quality score between 0.0 and 1.0")
    passed: bool = Field(description="True if chunking satisfies boundary integrity")
    issues: list[str] = Field(default_factory=list, description="Issues found")
    suggestions: list[str] = Field(default_factory=list, description="Recommendations")


class ChunkEvaluatorAgent(BaseAgent):
    """Evaluates whether the legacy file split preserved semantic boundaries and no logic was orphaned."""

    def __init__(self, config_dir: str = "configs"):
        super().__init__("chunk_evaluator", config_dir=config_dir)
        self.threshold = float(self.thresholds.get("confidence_thresholds", {}).get("chunk_evaluation", 0.85))

    def execute(self, state: PipelineState) -> dict:
        chunks = state.get("chunks", [])
        issues: list[str] = []
        self.logger.info("Evaluating chunk boundary integrity for %d chunks (Threshold: %.2f)", len(chunks), self.threshold)
        
        if not chunks:
            issues.append("No chunks were extracted from source files.")
        
        for c in chunks:
            if not c.raw_code.strip():
                issues.append(f"Chunk '{c.chunk_id}' has empty raw code.")
            if c.line_start < 1 or c.line_end < c.line_start:
                issues.append(f"Chunk '{c.chunk_id}' has invalid line range ({c.line_start}-{c.line_end}).")

        def mock_eval() -> ChunkEvaluationSchema:
            if issues:
                return ChunkEvaluationSchema(
                    score=0.40,
                    passed=False,
                    issues=issues,
                    suggestions=["Review parser regex boundaries."]
                )
            return ChunkEvaluationSchema(
                score=0.95,
                passed=True,
                issues=[],
                suggestions=["Chunking semantic boundaries preserved."]
            )

        summary_text = "\n".join([f"- {c.chunk_id} ({c.language}, lines {c.line_start}-{c.line_end}, type={c.chunk_type})" for c in chunks])
        user_prompt = CHUNK_EVALUATOR_USER_PROMPT.format(
            source_file=", ".join(set(c.source_file for c in chunks)),
            total_lines=sum(c.line_end - c.line_start + 1 for c in chunks),
            chunk_count=len(chunks),
            chunk_summaries=summary_text
        )

        res = self.invoke_structured(
            schema=ChunkEvaluationSchema,
            system_prompt=CHUNK_EVALUATOR_SYSTEM_PROMPT.format(threshold=self.threshold),
            user_prompt=user_prompt,
            mock_fallback_generator=mock_eval
        )

        is_passed = res.passed and res.score >= self.threshold
        self.logger.info("Chunk evaluation result: Score=%.2f, Passed=%s, Issues=%d", res.score, is_passed, len(res.issues))

        eval_result = EvalResult(
            target_id="global_chunks",
            stage="chunk_evaluation",
            score=res.score,
            passed=is_passed,
            issues=res.issues,
            suggestions=res.suggestions,
            needs_human_review=not res.passed and res.score < self.threshold
        )

        return {
            "eval_history": [eval_result],
            "stage": "chunk_evaluation"
        }
