"""Agent: Java Compile Checker — synthesizes the full Java file and validates it with javac."""

from __future__ import annotations
from pathlib import Path

from src.agents.base_agent import BaseAgent
from src.orchestrator.state import PipelineState, EvalResult
from src.evaluation.full_file_synthesizer import FullFileSynthesizer
from src.evaluation.java_compiler import JavaCompiler


class JavaCompileCheckerAgent(BaseAgent):
    """
    Synthesizes each source file's generated Java code and compiles it with javac.
    Compile errors are stored as EvalResult entries (stage='compile_check') and
    written into state so the router can send failing files back to CodeRefiner.
    """

    def __init__(self, config_dir: str = "configs"):
        super().__init__("java_compile_checker", config_dir=config_dir)

    def execute(self, state: PipelineState) -> dict:
        chunks = state.get("chunks", [])
        generated_code = state.get("generated_code", {})
        docs = state.get("docs", {})

        source_files = list({c.source_file for c in chunks})
        new_evals: list[EvalResult] = []
        compile_errors: dict[str, list[str]] = {}

        for sf in source_files:
            file_chunks = [c for c in chunks if c.source_file == sf]
            file_code = {c.chunk_id: generated_code[c.chunk_id] for c in file_chunks if c.chunk_id in generated_code}
            file_docs = {c.chunk_id: docs[c.chunk_id] for c in file_chunks if c.chunk_id in docs}

            if not file_code:
                self.logger.warning("No generated code for source file %s — skipping compile check.", sf)
                continue

            synth = FullFileSynthesizer.synthesize_file_modernization(sf, file_chunks, file_code, file_docs)
            java_code = synth.get("java_code", "")
            class_name = synth.get("java_class_name", Path(sf).stem)

            if not java_code.strip():
                self.logger.warning("Synthesized Java code is empty for %s — skipping.", sf)
                continue

            self.logger.info("Running javac on synthesized %s.java (%d lines)...", class_name, len(java_code.splitlines()))
            result = JavaCompiler.compile(java_code, class_name)

            if result.compiled:
                self.logger.info("javac PASSED for %s.java", class_name)
                compile_errors[sf] = []
            else:
                self.logger.warning(
                    "javac FAILED for %s.java — %d error(s): %s",
                    class_name, len(result.errors), "; ".join(result.errors[:3])
                )
                compile_errors[sf] = result.errors

                # Create EvalResult entries per chunk flagging the compile failure
                for chunk in file_chunks:
                    if chunk.chunk_id in generated_code:
                        new_evals.append(EvalResult(
                            target_id=chunk.chunk_id,
                            stage="compile_check",
                            score=0.0,
                            passed=False,
                            issues=[f"Compile error in synthesized {class_name}.java: {e}" for e in result.errors[:5]],
                            suggestions=[
                                "Fix class/record/method declarations so the synthesized file compiles.",
                                "Ensure all referenced types and imports are declared.",
                                "Check for duplicate method signatures or invalid modifiers.",
                            ],
                            needs_human_review=False,
                            version_evaluated=generated_code[chunk.chunk_id].version
                        ))

        self.logger.info(
            "Compile check complete: %d source file(s), %d with errors.",
            len(source_files),
            sum(1 for errs in compile_errors.values() if errs)
        )

        return {
            "compile_errors": compile_errors,
            "eval_history": new_evals,
            "stage": "compile_check",
        }
