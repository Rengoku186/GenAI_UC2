"""Agent 7: Doc Refiner Agent."""

from __future__ import annotations
from pydantic import BaseModel, Field
from src.agents.base_agent import BaseAgent
from src.orchestrator.state import PipelineState, DocSection, ChunkMetadata, EvalResult
from src.prompts.documenter_prompts import (
    DOC_REFINER_SYSTEM_PROMPT,
    DOC_REFINER_USER_PROMPT
)


class DocRefinementSchema(BaseModel):
    purpose: str = Field(description="Refined summary of purpose and business intent")
    inputs: list[str] = Field(default_factory=list, description="Refined inputs consumed")
    outputs: list[str] = Field(default_factory=list, description="Refined outputs or modified fields")
    business_rules: list[str] = Field(default_factory=list, description="Refined and complete list of business rules")
    control_flow: str = Field(description="Refined control flow description")


class DocRefinerAgent(BaseAgent):
    """Consumes Doc Evaluator feedback and rewrites failing documentation sections."""

    def __init__(self, config_dir: str = "configs"):
        super().__init__("doc_refiner", config_dir=config_dir)

    def refine_doc(self, chunk: ChunkMetadata, current_doc: DocSection, latest_eval: EvalResult) -> DocSection:
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
        eval_history = state.get("eval_history", [])
        retry_counts = dict(state.get("retry_counts", {}))

        target_chunk_id = state.get("current_chunk_id")
        if target_chunk_id and target_chunk_id in docs and target_chunk_id in chunks:
            refine_targets = [target_chunk_id]
        else:
            refine_targets = []
            for cid in docs:
                latest_evals = [e for e in eval_history if e.target_id == cid and e.stage == "doc_evaluation"]
                if latest_evals and not latest_evals[-1].passed and not latest_evals[-1].needs_human_review:
                    refine_targets.append(cid)

        self.logger.info("Running documentation refiner on %d chunks", len(refine_targets))
        for cid in refine_targets:
            chunk = chunks[cid]
            current_doc = docs[cid]
            latest_evals = [e for e in eval_history if e.target_id == cid and e.stage == "doc_evaluation"]
            latest_eval = latest_evals[-1] if latest_evals else EvalResult(
                target_id=cid, stage="doc_evaluation", score=0.0, passed=False, issues=["Initial refinement"]
            )

            new_doc = self.refine_doc(chunk, current_doc, latest_eval)
            docs[cid] = new_doc
            
            key = f"{cid}:documentation"
            retry_counts[key] = retry_counts.get(key, 0) + 1
            self.logger.debug("Incremented retry count for %s to %d", key, retry_counts[key])

        return {
            "docs": docs,
            "retry_counts": retry_counts,
            "stage": "doc_refinement"
        }
