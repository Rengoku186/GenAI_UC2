import json
import re
from typing import List
from src.schemas import Chunk, ChunkDoc
from src.utils.llm import get_llm

LANGUAGE_LABELS = {
    "cobol": "COBOL",
    "vb": "Visual Basic",
    "java": "Java",
    "mixed": "multiple languages (mixed cycle group)",
    "unknown": "an unspecified legacy language",
}

DOC_SYSTEM_PROMPT = """You are a senior legacy systems analyst documenting old \
{language} code ahead of a modernization effort. You read legacy code carefully \
and produce precise, factual documentation. You never invent behavior that isn't \
evidenced in the code. If something is unclear or ambiguous, say so plainly \
instead of guessing.

You must respond with ONLY a single valid JSON object, no markdown fences, no \
prose before or after it, matching exactly this shape:
{{
  "summary": "<2-4 sentence plain-English summary of what this code does>",
  "inputs": ["<input 1>", "<input 2>", ...],
  "outputs": ["<output 1>", "<output 2>", ...],
  "business_logic": "<detailed explanation of the business rules/logic implemented, written for a business analyst, not just a developer>",
  "dependencies_used": ["<qualified id of each dependency actually relied upon>"]
}}
"""

# NOTE: previously this template referenced a "CODE:" section header but had
# no {code} placeholder, so the actual source was silently dropped by
# str.format() (extra kwargs are ignored, not errored). Fixed below - the
# {code} placeholder now actually renders the chunk's source inside a fenced
# block, and language_label is reused as the fence's syntax hint.
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
"outputs" on what the code actually reads/writes (parameters, files, database \
fields, global/working-storage variables, return values) - do not guess at \
business meaning beyond what the code shows. For "dependencies_used", only \
include ids from the dependency context above that this code's logic actually \
relies on."""

NO_DEPENDENCY_CONTEXT = "This chunk has no already-documented dependencies."


def _build_dependency_context(chunk: Chunk, dep_docs: List[ChunkDoc]) -> str:
    if not dep_docs:
        return NO_DEPENDENCY_CONTEXT
    parts = ["DEPENDENCIES ALREADY DOCUMENTED (for context only):"]
    for dep in dep_docs:
        outputs_str = ", ".join(dep.outputs) if dep.outputs else "none recorded"
        parts.append(f"- {dep.chunk_id}: {dep.summary} (outputs: {outputs_str})")
    return "\n".join(parts)


def _extract_json(raw_text: str) -> dict:
    """Best-effort extraction of a JSON object from an LLM response, tolerating
    markdown fences or stray text the model adds despite instructions."""
    text = raw_text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))

    raise ValueError(f"Could not extract JSON from LLM response: {raw_text[:200]}")


def _to_chunk_doc(chunk_id: str, data: dict) -> ChunkDoc:
    return ChunkDoc(
        chunk_id=chunk_id,
        summary=str(data.get("summary", "")).strip(),
        inputs=[str(x) for x in data.get("inputs", [])],
        outputs=[str(x) for x in data.get("outputs", [])],
        business_logic=str(data.get("business_logic", "")).strip(),
        dependencies_used=[str(x) for x in data.get("dependencies_used", [])],
    )


def document_chunk(chunk: Chunk, dep_docs: List[ChunkDoc], max_retries: int = 2) -> ChunkDoc:
    # Guard: refuse to prompt the LLM for a chunk with no source code at all.
    # This used to fail silently (empty code -> template dropped it anyway ->
    # LLM hallucinated plausible-sounding but fabricated content). Now it
    # fails loudly and immediately instead of burning retries on garbage.
    if not chunk.code or not chunk.code.strip():
        raise ValueError(
            f"document_chunk: chunk {chunk.id!r} has empty/missing 'code' - "
            f"refusing to generate documentation from nothing."
        )

    llm = get_llm(temperature=0.0)
    language_label = LANGUAGE_LABELS.get(chunk.language, chunk.language)

    system_prompt = DOC_SYSTEM_PROMPT.format(language=language_label)
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

    # Sanity check: catch any future regression where {code} silently stops
    # being interpolated (e.g. someone edits the template and drops the
    # placeholder again). Better to crash here than to silently document
    # nothing, as happened before this fix.
    assert chunk.code.strip() in user_prompt, (
        f"document_chunk: chunk.code was not found in the rendered prompt for "
        f"{chunk.id!r} - check that DOC_USER_TEMPLATE still contains a {{code}} "
        f"placeholder."
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
                messages.append(("human",
                    f"Your previous response could not be parsed as valid JSON "
                    f"matching the required schema (error: {exc}). Respond again "
                    f"with ONLY the raw JSON object, nothing else."))
                continue

    # Fail safe rather than crash the whole graph on one bad chunk - the
    # Evaluator will score this low (empty summary/logic) and it will get
    # flagged for human review via the existing refine -> flag_for_human path.
    return ChunkDoc(
        chunk_id=chunk.id,
        summary="",
        inputs=[],
        outputs=[],
        business_logic=f"[DOCUMENTATION FAILED after {max_retries + 1} attempts: {last_error}]",
        dependencies_used=[],
    )