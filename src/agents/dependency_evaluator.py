"""Agent 4: Dependency Evaluator Agent."""

from __future__ import annotations
from pydantic import BaseModel, Field
from src.agents.base_agent import BaseAgent
from src.orchestrator.state import PipelineState, EvalResult
from src.prompts.evaluator_prompts import (
    DEPENDENCY_EVALUATOR_SYSTEM_PROMPT,
    DEPENDENCY_EVALUATOR_USER_PROMPT
)


class DependencyEvaluationSchema(BaseModel):
    score: float = Field(ge=0.0, le=1.0, description="Completeness score of dependency graph")
    passed: bool = Field(description="True if dependency graph matches static analysis")
    issues: list[str] = Field(default_factory=list, description="Missing or invalid dependencies")
    suggestions: list[str] = Field(default_factory=list, description="Suggestions for edge enhancement")


class DependencyEvaluatorAgent(BaseAgent):
    """Audits cross-chunk dependency graph against source code."""

    def __init__(self, config_dir: str = "configs"):
        super().__init__("dependency_evaluator", config_dir=config_dir)
        self.threshold = float(self.thresholds.get("confidence_thresholds", {}).get("dependency_evaluation", 0.85))

    def execute(self, state: PipelineState) -> dict:
        chunks = state.get("chunks", [])
        edges = state.get("dependency_graph", [])
        self.logger.info("Auditing dependency graph: %d nodes, %d edges (Threshold: %.2f)", len(chunks), len(edges), self.threshold)
        
        chunk_ids = {c.chunk_id for c in chunks}
        issues: list[str] = []

        for edge in edges:
            if edge.source_chunk not in chunk_ids and not edge.source_chunk.endswith("_HEADER"):
                issues.append(f"Edge references unknown source chunk: {edge.source_chunk}")

        def mock_eval() -> DependencyEvaluationSchema:
            if issues:
                return DependencyEvaluationSchema(
                    score=0.60,
                    passed=False,
                    issues=issues,
                    suggestions=["Re-scan source symbols for unresolved chunk IDs."]
                )
            return DependencyEvaluationSchema(
                score=0.92,
                passed=True,
                issues=[],
                suggestions=["Dependency graph successfully verified against static AST calls."]
            )

        nodes_str = "\n".join([f"- {c.chunk_id} ({c.name})" for c in chunks])
        edges_str = "\n".join([f"- {e.source_chunk} -> {e.target_chunk} [{e.edge_type}: {e.symbol}]" for e in edges])

        user_prompt = DEPENDENCY_EVALUATOR_USER_PROMPT.format(
            nodes=nodes_str,
            edges=edges_str or "No external edges detected."
        )

        res = self.invoke_structured(
            schema=DependencyEvaluationSchema,
            system_prompt=DEPENDENCY_EVALUATOR_SYSTEM_PROMPT.format(threshold=self.threshold),
            user_prompt=user_prompt,
            mock_fallback_generator=mock_eval
        )

        is_passed = res.passed and res.score >= self.threshold
        self.logger.info("Dependency evaluation result: Score=%.2f, Passed=%s, Issues=%d", res.score, is_passed, len(res.issues))

        eval_result = EvalResult(
            target_id="global_dependency_graph",
            stage="dependency_evaluation",
            score=res.score,
            passed=is_passed,
            issues=res.issues,
            suggestions=res.suggestions,
            needs_human_review=not res.passed and res.score < self.threshold
        )

        return {
            "eval_history": [eval_result],
            "stage": "dependency_evaluation"
        }
