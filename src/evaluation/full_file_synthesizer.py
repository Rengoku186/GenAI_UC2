"""Full-file synthesis engine: assembles per-chunk generated Java code into a single
unified Modern Java 17+ service file, JUnit 5 test suite, and Markdown documentation.

All output is built dynamically from the live pipeline state — no hardcoded templates.
"""

from __future__ import annotations
import re
from pathlib import Path
from typing import Any

from src.orchestrator.state import PipelineState, ChunkMetadata, GeneratedCode, DocSection
from src.utils.logger import get_logger
from src.utils.java_merger import JavaMerger
from src.utils.doc_builder import DocBuilder

logger = get_logger("FullFileSynthesizer")


class FullFileSynthesizer:
    """Assembles complete modernized Java services, JUnit 5 test suites, and documentation."""

    @classmethod
    def synthesize_file_modernization(
        cls,
        source_filename: str,
        chunks: list[ChunkMetadata],
        generated_code: dict[str, GeneratedCode],
        docs: dict[str, DocSection]
    ) -> dict[str, Any]:
        """Dynamically synthesizes the unified Java file, JUnit 5 tests, and documentation.

        Args:
            source_filename: Original legacy source file name.
            chunks:          All ChunkMetadata objects for this file (ordered by source line).
            generated_code:  Dict of chunk_id → GeneratedCode from the CodeGeneratorAgent.
            docs:            Dict of chunk_id → DocSection from the DocumenterAgent.

        Returns:
            Dict with keys: source_file, java_class_name, java_code, java_tests,
                            documentation_markdown.
        """
        stem = Path(source_filename).stem
        # Preserve existing PascalCase/camelCase (e.g. AccountProcessor → AccountProcessor).
        # Only apply PascalCase splitting if the stem is all-lowercase or uses separators.
        if re.search(r'[_\-]', stem) or stem == stem.lower():
            class_name = "".join(
                w.capitalize()
                for w in re.split(r"[_\-.\s]+", stem)
                if w
            )
        else:
            # Already PascalCase / camelCase — capitalise first letter only
            class_name = stem[0].upper() + stem[1:]

        # Determine package from first generated chunk (fallback to default)
        package = "com.modern.services"
        for gc in generated_code.values():
            if gc.java_package:
                package = gc.java_package
                break

        # Build class Javadoc from first documented chunk's purpose
        first_doc = next(
            (docs[c.chunk_id] for c in chunks if c.chunk_id in docs),
            None
        )
        class_javadoc = (
            f"Modernized {class_name} — migrated from legacy {Path(source_filename).name}.\n"
            + (first_doc.purpose if first_doc else "")
        )

        logger.info("Synthesizing unified Java class '%s' from %d chunks", class_name, len(chunks))

        java_code = JavaMerger.merge(
            class_name=class_name,
            chunks=chunks,
            generated_code=generated_code,
            package=package,
            class_javadoc=class_javadoc,
        )

        java_tests = cls._build_junit_suite(class_name, chunks, generated_code, package)

        doc_md = DocBuilder.build(
            source_filename=source_filename,
            chunks=chunks,
            docs=docs,
            class_name=class_name,
        )

        logger.info(
            "Synthesis complete for '%s': %d Java lines, %d doc lines",
            class_name, len(java_code.splitlines()), len(doc_md.splitlines())
        )

        return {
            "source_file":            source_filename,
            "java_class_name":        class_name,
            "java_code":              java_code,
            "java_tests":             java_tests,
            "documentation_markdown": doc_md,
        }

    @classmethod
    def _build_junit_suite(
        cls,
        class_name: str,
        chunks: list[ChunkMetadata],
        generated_code: dict[str, GeneratedCode],
        package: str,
    ) -> str:
        """Builds a unified JUnit 5 test class skeleton from chunk metadata.

        When running with a real LLM, the TestGeneratorAgent fills java_test_code on each
        GeneratedCode object. This builder merges those into one @Nested test class.
        In mock/offline mode it generates minimal structural stubs.
        """
        chunk_map = {c.chunk_id: c for c in chunks}
        ordered_ids = sorted(
            generated_code.keys(),
            key=lambda cid: chunk_map[cid].line_start if cid in chunk_map else 9999
        )

        lines: list[str] = [
            f"package {package};",
            "",
            "import org.junit.jupiter.api.Test;",
            "import org.junit.jupiter.api.Nested;",
            "import org.junit.jupiter.api.BeforeEach;",
            "import org.junit.jupiter.api.DisplayName;",
            "import java.math.BigDecimal;",
            "import java.time.LocalDateTime;",
            "import static org.junit.jupiter.api.Assertions.*;",
            "",
            f"/**",
            f" * Unified JUnit 5 test suite for {class_name}.",
            f" * Auto-generated by the Legacy Code Modernization Pipeline.",
            f" */",
            f"@DisplayName(\"{class_name} — JUnit 5 Suite\")",
            f"class {class_name}Test {{",
            "",
            f"    private {class_name} service;",
            "",
            "    @BeforeEach",
            "    void setUp() {",
            f"        service = new {class_name}();",
            "    }",
            "",
        ]

        for cid in ordered_ids:
            gc = generated_code[cid]
            chunk = chunk_map.get(cid)

            # Use real test code if available (from TestGeneratorAgent)
            real_test = getattr(gc, 'java_test_code', '').strip()
            if real_test:
                # Embed raw test class body as a @Nested class
                lines.append(f"    @Nested")
                lines.append(f"    @DisplayName(\"{cid}\")")
                nested_name = "".join(
                    w.capitalize()
                    for w in re.split(r"[_.\-]", cid.replace(Path(gc.java_class_name).stem if gc.java_class_name else '', '', 1).strip('_'))
                    if w
                ) + "Tests"
                lines.append(f"    class {nested_name} {{")
                # Indent the test body
                for tl in real_test.splitlines():
                    lines.append(f"        {tl}")
                lines.append("    }")
                lines.append("")
            else:
                # Minimal stub
                method_name = re.sub(r"[^a-zA-Z0-9]", "_", cid)
                lines.append(f"    @Test")
                lines.append(f"    @DisplayName(\"{cid}\")")
                lines.append(f"    void test_{method_name}() {{")
                lines.append(f"        // TODO: implement test for {chunk.name if chunk else cid}")
                lines.append(f"        assertNotNull(service);")
                lines.append(f"    }}")
                lines.append("")

        lines.append("}")
        return "\n".join(lines) + "\n"
