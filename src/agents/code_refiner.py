"""Agent 10: Code Refiner Agent (Java-only mode)."""

from __future__ import annotations
from pydantic import BaseModel, Field
from src.agents.base_agent import BaseAgent
from src.orchestrator.state import PipelineState, GeneratedCode, ChunkMetadata, DocSection, EvalResult, TestResult
from src.prompts.codegen_prompts import (
    CODE_REFINER_SYSTEM_PROMPT,
    CODE_REFINER_USER_PROMPT
)


class CodeRefinementSchema(BaseModel):
    module_name: str = Field(description="Java module/file stem name")
    target_java_code: str = Field(description="Corrected, complete Java 17+ service code")
    java_class_name: str = Field(default="", description="Java class name")


class CodeRefinerAgent(BaseAgent):
    """Consumes Code Evaluator feedback or test execution failures and rewrites failing Java code."""

    def __init__(self, config_dir: str = "configs"):
        super().__init__("code_refiner", config_dir=config_dir)

    def refine_code(
        self,
        chunk: ChunkMetadata,
        doc: DocSection,
        current_code: GeneratedCode,
        latest_eval: EvalResult | None = None,
        test_result: TestResult | None = None
    ) -> GeneratedCode:
        """Rewrites Java code based on evaluator feedback or test failure output."""
        self.logger.info("Refining Java code for chunk %s (v%d -> v%d)", chunk.chunk_id, current_code.version, current_code.version + 1)

        def mock_refine() -> CodeRefinementSchema:
            # Ensure package declaration is present
            java_code = current_code.target_java_code
            if java_code and "package com.modern.services;" not in java_code:
                java_code = "package com.modern.services;\n\n" + java_code
            return CodeRefinementSchema(
                module_name=chunk.name.lower(),
                target_java_code=java_code,
                java_class_name=current_code.java_class_name
            )

        feedback_str = ""
        if latest_eval:
            feedback_str = f"Score: {latest_eval.score}\nIssues: " + ", ".join(latest_eval.issues)

        test_out_str = test_result.execution_output if test_result else "No test failure logs"

        user_prompt = CODE_REFINER_USER_PROMPT.format(
            chunk_id=chunk.chunk_id,
            feedback=feedback_str,
            test_output=test_out_str,
            version=current_code.version,
            current_java_code=current_code.target_java_code,
            language=chunk.language,
            raw_code=chunk.raw_code,
            business_rules="\n".join([f"- {r}" for r in doc.business_rules])
        )

        res = self.invoke_structured(
            schema=CodeRefinementSchema,
            system_prompt=CODE_REFINER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            mock_fallback_generator=mock_refine
        )

        return GeneratedCode(
            chunk_id=chunk.chunk_id,
            target_java_code=res.target_java_code or current_code.target_java_code,
            java_class_name=res.java_class_name or current_code.java_class_name,
            java_package=current_code.java_package,
            version=current_code.version + 1
        )

    def execute(self, state: PipelineState) -> dict:
        chunks = {c.chunk_id: c for c in state.get("chunks", [])}
        docs = state.get("docs", {})
        generated = dict(state.get("generated_code", {}))
        eval_history = state.get("eval_history", [])
        tests = state.get("tests", {})
        retry_counts = dict(state.get("retry_counts", {}))

        target_chunk_id = state.get("current_chunk_id")
        if target_chunk_id and target_chunk_id in generated and target_chunk_id in chunks:
            refine_targets = [target_chunk_id]
        else:
            refine_targets = []
            for cid in generated:
                code_evals = [e for e in eval_history if e.target_id == cid and e.stage == "code_evaluation"]
                test_evals = [e for e in eval_history if e.target_id == cid and e.stage == "test_execution"]
                
                needs_refine = False
                if code_evals and not code_evals[-1].passed and not code_evals[-1].needs_human_review:
                    needs_refine = True
                if test_evals and not test_evals[-1].passed and not test_evals[-1].needs_human_review:
                    needs_refine = True

                if needs_refine:
                    refine_targets.append(cid)

        self.logger.info("Refining code across %d chunks", len(refine_targets))
        for cid in refine_targets:
            chunk = chunks[cid]
            doc = docs.get(cid, DocSection(chunk_id=cid, purpose="Default", control_flow="Sequential"))
            curr_code = generated[cid]
            latest_evals = [e for e in eval_history if e.target_id == cid and e.stage == "code_evaluation"]
            latest_eval = latest_evals[-1] if latest_evals else None
            t_res = tests.get(cid)

            new_code = self.refine_code(chunk, doc, curr_code, latest_eval, t_res)
            generated[cid] = new_code

            key = f"{cid}:code_generation"
            retry_counts[key] = retry_counts.get(key, 0) + 1
            self.logger.debug("Incremented retry count for %s to %d", key, retry_counts[key])

        return {
            "generated_code": generated,
            "retry_counts": retry_counts,
            "stage": "code_refinement"
        }
