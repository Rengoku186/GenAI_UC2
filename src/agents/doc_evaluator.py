"""Agent 6: Doc Evaluator and Refiner Agent."""

from __future__ import annotations
from pydantic import BaseModel, Field
from src.agents.base_agent import BaseAgent
from src.orchestrator.state import PipelineState, EvalResult, DocSection, ChunkMetadata
from src.prompts.evaluator_prompts import (
    DOC_EVALUATOR_SYSTEM_PROMPT,
    DOC_EVALUATOR_USER_PROMPT
)
from src.prompts.documenter_prompts import (
    DOC_REFINER_SYSTEM_PROMPT,
    DOC_REFINER_USER_PROMPT
)


class DocEvaluationSchema(BaseModel):
    score: float = Field(ge=0.0, le=1.0, description="Quality & fidelity score between 0.0 and 1.0")
    passed: bool = Field(description="Whether documentation meets threshold")
    issues: list[str] = Field(default_factory=list, description="Omissions, inaccuracies or hallucinations")
    suggestions: list[str] = Field(default_factory=list, description="Actionable recommendations")


class DocRefinementSchema(BaseModel):
    purpose: str = Field(description="Refined summary of purpose and business intent")
    inputs: list[str] = Field(default_factory=list, description="Refined inputs consumed")
    outputs: list[str] = Field(default_factory=list, description="Refined outputs or modified fields")
    business_rules: list[str] = Field(default_factory=list, description="Refined and complete list of business rules")
    control_flow: str = Field(description="Refined control flow description")


class DocEvaluatorAgent(BaseAgent):
    """Evaluates and refines documentation for completeness and accuracy."""

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

    def _refine_doc(self, chunk: ChunkMetadata, current_doc: DocSection, latest_eval: EvalResult, dep_ctx: str) -> DocSection:
        """Refines documentation using evaluation issues and suggestions."""
        self.logger.info("Refining documentation for chunk %s (v%d -> v%d)", chunk.chunk_id, current_doc.version, current_doc.version + 1)
        
        def mock_refine() -> DocRefinementSchema:
            refined_rules = list(current_doc.business_rules)
            for iss in latest_eval.issues:
                refined_rules.append(f"Refined rule addressing: {iss}")
            return DocRefinementSchema(
                purpose=f"{current_doc.purpose} (Refined v{current_doc.version + 1})",
                inputs=current_doc.inputs or ["Standard input parameters"],
                outputs=current_doc.outputs or ["Standard outputs / return values"],
                business_rules=refined_rules or ["Accurate business logic from source"],
                control_flow=current_doc.control_flow
            )

        user_prompt = DOC_REFINER_USER_PROMPT.format(
            chunk_id=chunk.chunk_id,
            chunk_type=chunk.chunk_type,
            source_file=chunk.source_file,
            line_start=chunk.line_start,
            line_end=chunk.line_end,
            dependency_context=dep_ctx,
            score=latest_eval.score,
            issues="\n".join([f"- {i}" for i in latest_eval.issues]) or "None",
            suggestions="\n".join([f"- {s}" for s in latest_eval.suggestions]) or "None",
            language=chunk.language,
            raw_code=chunk.raw_code,
            version=current_doc.version,
            current_purpose=current_doc.purpose,
            current_inputs=", ".join(current_doc.inputs),
            current_outputs=", ".join(current_doc.outputs),
            current_business_rules="\n".join([f"- {r}" for r in current_doc.business_rules]),
            current_control_flow=current_doc.control_flow
        )

        res = self.invoke_structured(
            schema=DocRefinementSchema,
            system_prompt=DOC_REFINER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            mock_fallback_generator=mock_refine
        )

        return DocSection(
            chunk_id=chunk.chunk_id,
            purpose=res.purpose,
            inputs=res.inputs,
            outputs=res.outputs,
            business_rules=res.business_rules,
            control_flow=res.control_flow,
            version=current_doc.version + 1
        )

    def execute(self, state: PipelineState) -> dict:
        chunks = {c.chunk_id: c for c in state.get("chunks", [])}
        docs = dict(state.get("docs", {}))
        retry_counts = dict(state.get("retry_counts", {}))
        eval_history = list(state.get("eval_history", []))
        
        target_chunk_id = state.get("current_chunk_id")
        if target_chunk_id and target_chunk_id in docs and target_chunk_id in chunks:
            eval_targets = [target_chunk_id]
        else:
            eval_targets = list(docs.keys())

        self.logger.info("Evaluating documentation across %d chunks", len(eval_targets))
        new_evals: list[EvalResult] = []
        flagged: list[str] = []

        edges = state.get("dependency_graph", [])

        for cid in eval_targets:
            if cid in chunks and cid in docs:
                retries = retry_counts.get(f"{cid}:documentation", 0)
                chunk = chunks[cid]
                chunk_edges = [e for e in edges if e.source_chunk == chunk.chunk_id or e.target_chunk == chunk.chunk_id]
                dep_ctx = "\n".join([f"- {e.edge_type}: {e.source_chunk} -> {e.target_chunk} ({e.description})" for e in chunk_edges]) or "None"
                
                while True:
                    # 1. Evaluate
                    eval_res = self.evaluate_chunk_doc(chunks[cid], docs[cid], retries)
                    new_evals.append(eval_res)
                    eval_history.append(eval_res)
                    
                    if eval_res.passed:
                        break
                    
                    # 2. Check retry cap
                    if retries >= self.max_retries:
                        self.logger.warning("Doc evaluation retry cap reached for %s", cid)
                        flagged.append(f"{cid}:doc_evaluation")
                        break
                    
                    # 3. Refine
                    docs[cid] = self._refine_doc(chunks[cid], docs[cid], eval_res, dep_ctx)
                    retries += 1
                    retry_counts[f"{cid}:documentation"] = retries
                    self.logger.debug("Incremented retry count for %s to %d", f"{cid}:documentation", retries)

        return {
            "docs": docs,
            "retry_counts": retry_counts,
            "eval_history": new_evals,  # Note: graph.py reducer will extend the global list
            "flagged_for_review": flagged,
            "stage": "doc_evaluation"
        }
