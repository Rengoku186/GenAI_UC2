"""Documenter Agent for Legacy Code Modernization.

Analyzes parsed code chunks across COBOL, Visual Basic, and Java, generating
factual semantic documentation, input/output variable dictionaries, and synthesizing
a comprehensive master Markdown specification according to enterprise standards.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from src.schemas import Chunk, ChunkDoc
from src.utils.llm import get_llm

logger = logging.getLogger(__name__)

# ============================================================================
# Language Labels & Prompt Templates
# ============================================================================

LANGUAGE_LABELS: Dict[str, str] = {
    "cobol": "COBOL",
    "vb": "Visual Basic (VB6 / VBA / VBScript)",
    "java": "Java",
    "mixed": "Multiple languages (Composite Cycle Group)",
    "unknown": "an unspecified legacy language",
}

DOC_SYSTEM_PROMPT = """You are a senior legacy systems analyst documenting old \
{language} code ahead of an enterprise modernization effort. You read legacy code carefully \
and produce precise, factual documentation. You never invent behavior that isn't \
evidenced in the code. If something is unclear or ambiguous, say so plainly \
instead of guessing.

You must extract:
1. "summary": 2-4 sentence plain-English summary of what this code does.
2. "inputs": list of input variables, parameters, files, or database/working-storage fields read.
3. "outputs": list of output variables, return values, files, or fields modified.
4. "calculations_and_joins": specific mathematical formulas, data calculations, table joins, SQL operations, or critical validation rules implemented.
5. "business_logic": detailed explanation of the business rules/logic written for a business analyst.
6. "dependencies_used": list of qualified ids of dependencies actually relied upon.

You must respond with ONLY a single valid JSON object, no markdown fences, no \
prose before or after it, matching exactly this shape:
{{
  "summary": "<2-4 sentence plain-English summary>",
  "inputs": ["<input variable 1>", "<input variable 2>", ...],
  "outputs": ["<output variable 1>", "<output variable 2>", ...],
  "calculations_and_joins": "<specific formulas, joins, calculations, or validations>",
  "business_logic": "<detailed business rules and logic>",
  "dependencies_used": ["<qualified id of each dependency used>"]
}}
"""

DOC_USER_TEMPLATE = """CHUNK METADATA
id: {chunk_id}
file_path: {file_path}
scope: {scope}
name: {name}
language: {language_label}
is_cycle_group: {is_cycle_group}
lines: {start_line}-{end_line}

{dependency_context}

CODE:
```{language_label}
{code}
```

Document this chunk according to the required JSON schema. Base "inputs" and \
"outputs" on the concrete variables/fields the code actually reads or writes. \
Detail all calculations, joins, and business rules explicitly."""

DOC_REFINE_TEMPLATE = """You previously generated documentation for this chunk, but QA evaluation flagged the following issues:
{eval_critique}

PREVIOUS DOCUMENTATION:
Summary: {prev_summary}
Inputs: {prev_inputs}
Outputs: {prev_outputs}
Calculations/Joins: {prev_calculations}
Business Logic: {prev_business_logic}

Please carefully correct the documentation to address every issue flagged above while staying 100% faithful to the ACTUAL SOURCE CODE:
```{language_label}
{code}
```

Respond with ONLY the corrected JSON object."""

NO_DEPENDENCY_CONTEXT = "This chunk has no already-documented dependencies."


# ============================================================================
# Chunk Significance Filter (Memory & Token Optimization)
# ============================================================================

BOILERPLATE_PATTERNS = [
    re.compile(r"^\s*(?:EXIT|GOBACK|STOP\s+RUN)\.?\s*$", re.IGNORECASE),
    re.compile(r"^\s*(?:EXIT\s+PARAGRAPH|EXIT\s+SECTION)\.?\s*$", re.IGNORECASE),
]


def should_document_chunk(chunk: Chunk) -> bool:
    """Determine whether a chunk contains meaningful logic or is trivial boilerplate.

    Filters out pure exit paragraphs, empty bodies, and non-functional stubs to save
    memory, LLM token budget, and prevent micro-JSON clutter.

    Args:
        chunk: The code chunk to evaluate.

    Returns:
        True if the chunk contains significant business logic, False if boilerplate.
    """
    if not chunk.code or not chunk.code.strip():
        return False

    lines = [l.strip() for l in chunk.code.splitlines() if l.strip() and not l.strip().startswith("*") and not l.strip().startswith("//") and not l.strip().startswith("'")]

    if not lines:
        return False

    # Check for pure 1-2 line exit/goback/pass-through boilerplate
    if len(lines) <= 2:
        for p in BOILERPLATE_PATTERNS:
            if any(p.match(l) for l in lines):
                # If all non-comment lines are exit/stop keywords
                if all(p.match(l) or l.endswith(".") and len(l) <= 15 for l in lines):
                    logger.debug("Skipping boilerplate chunk: %s", chunk.id)
                    return False

    return True


# ============================================================================
# Helper Functions
# ============================================================================

def _build_dependency_context(chunk: Chunk, dep_docs: List[ChunkDoc], max_deps: int = 10) -> str:
    """Build concise dependency context for prompt injection."""
    if not dep_docs:
        return NO_DEPENDENCY_CONTEXT

    # Filter to dependencies directly relevant to this chunk
    relevant = [d for d in dep_docs if d.chunk_id in chunk.depends_on]
    if not relevant:
        relevant = dep_docs[:max_deps]
    else:
        relevant = relevant[:max_deps]

    parts = ["DEPENDENCIES ALREADY DOCUMENTED (for context only):"]
    for dep in relevant:
        outputs_str = ", ".join(dep.outputs) if dep.outputs else "none recorded"
        parts.append(f"- {dep.chunk_id}: {dep.summary} (outputs: {outputs_str})")
    return "\n".join(parts)


def _extract_json(raw_text: str) -> dict:
    """Extract and parse a JSON object from raw LLM text with repair heuristics."""
    text = raw_text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract valid JSON from LLM response: {raw_text[:200]}")


def _to_chunk_doc(chunk_id: str, data: dict) -> ChunkDoc:
    """Construct a validated ChunkDoc from parsed dictionary data."""
    # Combine business logic with calculations/joins if present
    business_logic = str(data.get("business_logic", "")).strip()
    calc_joins = str(data.get("calculations_and_joins", "")).strip()

    if calc_joins and calc_joins not in business_logic:
        if business_logic:
            business_logic = f"{business_logic}\n\nKey Operations / Calculations:\n{calc_joins}"
        else:
            business_logic = calc_joins

    return ChunkDoc(
        chunk_id=chunk_id,
        summary=str(data.get("summary", "")).strip(),
        inputs=[str(x) for x in data.get("inputs", []) if str(x).strip()],
        outputs=[str(x) for x in data.get("outputs", []) if str(x).strip()],
        business_logic=business_logic,
        dependencies_used=[str(x) for x in data.get("dependencies_used", [])],
    )


# ============================================================================
# Main Chunk Documentation Agent
# ============================================================================

def document_chunk(
    chunk: Chunk,
    dep_docs: List[ChunkDoc],
    eval_issues: Optional[List[str]] = None,
    previous_doc: Optional[ChunkDoc] = None,
    max_retries: int = 2,
) -> ChunkDoc:
    """Generate structured documentation for a single code chunk.

    Supports evaluator critique feedback loops for iterative refinement.

    Args:
        chunk: The code chunk to document.
        dep_docs: Documentation of upstream dependencies.
        eval_issues: Optional critique issues flagged by QA Evaluator during refinement.
        previous_doc: Optional previous documentation object being refined.
        max_retries: Number of retry attempts on malformed output.

    Returns:
        Validated ChunkDoc object.
    """
    if not chunk.code or not chunk.code.strip():
        raise ValueError(
            f"document_chunk: chunk {chunk.id!r} has empty/missing 'code' - "
            f"refusing to generate documentation from nothing."
        )

    llm = get_llm(temperature=0.0)
    language_label = LANGUAGE_LABELS.get(chunk.language, chunk.language)
    system_prompt = DOC_SYSTEM_PROMPT.format(language=language_label)

    # Build initial or refinement prompt
    if eval_issues and previous_doc:
        critique_text = "\n".join(f"- {issue}" for issue in eval_issues)
        user_prompt = DOC_REFINE_TEMPLATE.format(
            eval_critique=critique_text,
            prev_summary=previous_doc.summary,
            prev_inputs=", ".join(previous_doc.inputs) if previous_doc.inputs else "(none)",
            prev_outputs=", ".join(previous_doc.outputs) if previous_doc.outputs else "(none)",
            prev_calculations="(see business logic)",
            prev_business_logic=previous_doc.business_logic,
            language_label=language_label,
            code=chunk.code,
        )
    else:
        user_prompt = DOC_USER_TEMPLATE.format(
            chunk_id=chunk.id,
            file_path=chunk.file_path,
            scope=chunk.scope or "(none)",
            name=chunk.name,
            language_label=language_label,
            is_cycle_group=chunk.is_cycle_group,
            start_line=chunk.start_line,
            end_line=chunk.end_line,
            dependency_context=_build_dependency_context(chunk, dep_docs),
            code=chunk.code,
        )

    messages = [
        ("system", system_prompt),
        ("human", user_prompt),
    ]

    last_error: Exception = ValueError("document_chunk: no attempts made")
    for attempt in range(max_retries + 1):
        try:
            response = llm.invoke(messages)
            raw_text = response.content if hasattr(response, "content") else str(response)
            data = _extract_json(raw_text)
            return _to_chunk_doc(chunk.id, data)
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            last_error = exc
            if attempt < max_retries:
                messages.append(
                    (
                        "human",
                        f"Your previous response could not be parsed as valid JSON "
                        f"matching the required schema (error: {exc}). Respond again "
                        f"with ONLY the raw JSON object, nothing else.",
                    )
                )
                continue

    # Fail-safe ChunkDoc
    return ChunkDoc(
        chunk_id=chunk.id,
        summary="",
        inputs=[],
        outputs=[],
        business_logic=f"[DOCUMENTATION FAILED after {max_retries + 1} attempts: {last_error}]",
        dependencies_used=[],
    )


# ============================================================================
# Master Markdown Specification Generator (SME Standard)
# ============================================================================

def _detect_main_entry_point(chunks: List[Chunk]) -> Optional[str]:
    """Identify the primary execution entry point among the chunks."""
    entry_candidates = ["MAIN", "MAIN-PARA", "MAINPROCESS", "MAIN_PROCESS", "START", "INIT", "PROCESS"]

    # 1. Exact match on standard entry routine names
    for candidate in entry_candidates:
        for c in chunks:
            if c.name.upper() == candidate or c.name.upper().endswith(f"::{candidate}"):
                return c.id

    # 2. Look for chunk with 'main' in name (e.g. public static void main)
    for c in chunks:
        if "main" in c.name.lower():
            return c.id

    # 3. Fall back to the first chunk
    return chunks[0].id if chunks else None


def generate_master_documentation(
    chunks: List[Chunk],
    docs: Dict[str, ChunkDoc],
    entry_point: Optional[str] = None,
    project_name: str = "Legacy Codebase",
) -> str:
    """Generate a cohesive, publication-ready Master Markdown Specification.

    Follows the 3-section SME format:
    1. Program Description
    2. Function-wise Explanations (with Main Entry Point & Input Variables highlighted)
    3. Key Technical Operations & Business Logic Table (| Section | Description |)

    Args:
        chunks: List of all parsed code chunks in processing order.
        docs: Mapping of chunk_id -> ChunkDoc documentation objects.
        entry_point: Optional override for the main entry point identifier.
        project_name: Name of the legacy application or system.

    Returns:
        Complete Markdown string conforming to enterprise standards.
    """
    discovered_entry = entry_point or _detect_main_entry_point(chunks)

    # Collect distinct files and languages
    files_analyzed = sorted(list(set(c.file_path for c in chunks if c.file_path)))
    languages = sorted(list(set(c.language.upper() for c in chunks if c.language)))
    lang_str = ", ".join(languages) if languages else "Legacy Multi-Language"

    md_lines: List[str] = []

    # ========================================================================
    # SECTION 1: Program Description
    # ========================================================================
    md_lines.append(f"# {project_name} - Technical Specification & Documentation")
    md_lines.append("")
    md_lines.append("## 1. Program Description")
    md_lines.append("")
    md_lines.append(
        f"This document provides comprehensive reverse-engineered technical and business "
        f"specifications for the **{project_name}** legacy codebase. The analyzed software "
        f"is implemented in **{lang_str}** across {len(files_analyzed)} primary source file(s)."
    )
    md_lines.append("")
    md_lines.append("### Architecture Overview & Key Highlights")
    md_lines.append(f"- **Primary Source Files**: {len(files_analyzed)}")
    for f in files_analyzed:
        md_lines.append(f"  - `{f}`")
    md_lines.append(f"- **Total Functional Units Analyzed**: {len(chunks)}")
    md_lines.append(f"- **Primary Entry Point**: `{discovered_entry}`")
    md_lines.append("")
    md_lines.append(
        "The system executes business logic, input validation, core arithmetic/data processing, "
        "and downstream error handling as detailed in the functional breakdowns below."
    )
    md_lines.append("")

    # ========================================================================
    # SECTION 2: Function-wise Explanations
    # ========================================================================
    md_lines.append("## 2. Function-wise Explanations")
    md_lines.append("")

    # Highlight Main Entry Point First
    if discovered_entry:
        entry_chunk = next((c for c in chunks if c.id == discovered_entry), None)
        entry_doc = docs.get(discovered_entry)

        md_lines.append("### ★ Main Entry Point")
        md_lines.append(f"**Routine / Identifier**: `{discovered_entry}`")
        if entry_chunk:
            md_lines.append(f"- **File Path**: `{entry_chunk.file_path}`")
            md_lines.append(f"- **Scope**: `{entry_chunk.scope or '(global)'}`")
            md_lines.append(f"- **Lines**: {entry_chunk.start_line} – {entry_chunk.end_line}")

        if entry_doc:
            inputs_str = ", ".join(f"`{x}`" for x in entry_doc.inputs) if entry_doc.inputs else "*None (reads global working-storage / system state)*"
            outputs_str = ", ".join(f"`{x}`" for x in entry_doc.outputs) if entry_doc.outputs else "*None (side-effects / state mutation)*"
            md_lines.append(f"- **Input Variables**: {inputs_str}")
            md_lines.append(f"- **Output Variables / Results**: {outputs_str}")
            md_lines.append(f"- **Summary**: {entry_doc.summary}")
            md_lines.append(f"- **Business Logic**: {entry_doc.business_logic}")
        else:
            md_lines.append("- *Entry point routine orchestrates the primary workflow execution.*")
        md_lines.append("")
        md_lines.append("---")
        md_lines.append("")

    # All Functions / Paragraphs Breakdown
    md_lines.append("### Component & Routine Breakdown")
    md_lines.append("")

    for chunk in chunks:
        doc = docs.get(chunk.id)
        is_entry = (chunk.id == discovered_entry)
        entry_badge = " *(Main Entry Point)*" if is_entry else ""

        md_lines.append(f"#### Function: `{chunk.name}`{entry_badge}")
        md_lines.append(f"- **Qualified ID**: `{chunk.id}`")
        md_lines.append(f"- **Scope**: `{chunk.scope or '(none)'}` | **File**: `{chunk.file_path}` | **Lines**: {chunk.start_line}–{chunk.end_line}")

        if doc:
            inputs_formatted = ", ".join(f"`{x}`" for x in doc.inputs) if doc.inputs else "*None / Unspecified*"
            outputs_formatted = ", ".join(f"`{x}`" for x in doc.outputs) if doc.outputs else "*None / State Mutation*"
            md_lines.append(f"- **Input Variables**: {inputs_formatted}")
            md_lines.append(f"- **Outputs**: {outputs_formatted}")
            md_lines.append(f"- **Summary**: {doc.summary}")
            if doc.business_logic:
                md_lines.append(f"- **Detailed Logic**: {doc.business_logic}")
            if doc.dependencies_used:
                deps_str = ", ".join(f"`{d}`" for d in doc.dependencies_used)
                md_lines.append(f"- **Dependencies Relied Upon**: {deps_str}")
        else:
            md_lines.append("- *Standard structural routine.*")

        md_lines.append("")

    # ========================================================================
    # SECTION 3: Key Technical Operations & Business Logic Table
    # ========================================================================
    md_lines.append("## 3. Key Technical Operations & Business Logic")
    md_lines.append("")
    md_lines.append(
        "The following 2-column table summarizes all critical mathematical calculations, "
        "database operations/joins, input validations, and core business outputs across the program:"
    )
    md_lines.append("")
    md_lines.append("| Section | Description |")
    md_lines.append("| :--- | :--- |")

    for chunk in chunks:
        doc = docs.get(chunk.id)
        section_name = f"`{chunk.name}`"

        if doc and (doc.summary or doc.business_logic):
            # Extract key operational sentence or summary
            desc_parts = []
            if doc.summary:
                desc_parts.append(doc.summary)
            if doc.inputs:
                desc_parts.append(f"**Inputs**: {', '.join(doc.inputs)}.")
            if doc.outputs:
                desc_parts.append(f"**Outputs**: {', '.join(doc.outputs)}.")

            desc_text = " ".join(desc_parts).replace("\n", " ").replace("|", "\\|")
            md_lines.append(f"| {section_name} | {desc_text} |")
        else:
            md_lines.append(f"| {section_name} | Subroutine execution block spanning lines {chunk.start_line}–{chunk.end_line}. |")

    md_lines.append("")
    return "\n".join(md_lines)


# ============================================================================
# Selective JSON Output for Human Review (Memory & Storage Optimization)
# ============================================================================

def export_flagged_json_only(flagged_items: List[dict], output_path: str) -> None:
    """Save structured JSON records strictly for flagged review chunks.

    Prevents disk and memory clutter by isolating review items that scored below
    threshold or experienced processing ambiguity.

    Args:
        flagged_items: List of flagged review items from the pipeline.
        output_path: Path where the flagged JSON report should be stored.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(flagged_items, f, indent=2)
    logger.info("Exported %d flagged review item(s) to %s", len(flagged_items), output_path)