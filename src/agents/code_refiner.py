"""Agent 10: Code Refiner Agent."""

from __future__ import annotations
from pydantic import BaseModel, Field
from src.agents.base_agent import BaseAgent
from src.orchestrator.state import PipelineState, GeneratedCode, ChunkMetadata, DocSection, EvalResult, TestResult
from src.prompts.codegen_prompts import (
    CODE_REFINER_SYSTEM_PROMPT,
    CODE_REFINER_USER_PROMPT
)


class CodeRefinementSchema(BaseModel):
    module_name: str = Field(description="Python module name")
    imports: list[str] = Field(default_factory=list, description="Required Python imports")
    target_code: str = Field(description="Corrected, complete, runnable Python code")


class CodeRefinerAgent(BaseAgent):
    """Consumes Code Evaluator feedback or test execution failures and rewrites failing Python code."""

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
        """Rewrites Python code based on evaluator feedback or test failure output."""
        def mock_refine() -> CodeRefinementSchema:
            # Clean up target code if there was any syntax issue
            clean_code = current_code.target_code
            if "import " not in clean_code:
                clean_code = "from decimal import Decimal\n\n" + clean_code
            return CodeRefinementSchema(
                module_name=current_code.module_name or chunk.name.lower(),
                imports=current_code.imports,
                target_code=clean_code
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
            current_code=current_code.target_code,
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
            target_code=res.target_code,
            module_name=res.module_name,
            imports=res.imports,
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
                # Check if latest code_eval failed or test execution failed
                code_evals = [e for e in eval_history if e.target_id == cid and e.stage == "code_evaluation"]
                test_evals = [e for e in eval_history if e.target_id == cid and e.stage == "test_execution"]
                
                needs_refine = False
                if code_evals and not code_evals[-1].passed and not code_evals[-1].needs_human_review:
                    needs_refine = True
                if test_evals and not test_evals[-1].passed and not test_evals[-1].needs_human_review:
                    needs_refine = True

                if needs_refine:
                    refine_targets.append(cid)

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

        return {
            "generated_code": generated,
            "retry_counts": retry_counts,
            "stage": "code_refinement"
        }
