import json
import re
from src.schemas import Chunk, ChunkDoc, EvalResult
from src.utils.llm import get_llm

PASS_THRESHOLD = 80.0

EVAL_SYSTEM_PROMPT = """You are a meticulous QA reviewer checking AI-generated \
documentation of legacy code against the actual source code, ahead of a \
modernization effort. You are skeptical by default - your job is to catch \
inaccuracies, hallucinated behavior, and missing information, not to be generous.

You must respond with ONLY a single valid JSON object, no markdown fences, no \
prose before or after it, matching exactly this shape:
{
  "overall_score": <float 0-100>,
  "issues": ["<specific issue 1>", "<specific issue 2>", ...]
}

Scoring guide:
- 90-100: doc is accurate, complete, and matches the code with no meaningful gaps
- 70-89: doc is mostly accurate but missing minor details or slightly imprecise
- 40-69: doc has real gaps or a questionable claim not supported by the code
- 0-39: doc is inaccurate, hallucinated, or fails to reflect the code's actual behavior
If issues list is non-empty, the score must reflect their severity - do not give \
a high score alongside serious issues."""

# NOTE: previously this template had no {code} placeholder at all - the
# evaluator was scoring documentation against the doc's own internal
# consistency, never against the real source. That's why it never caught
# fabricated variable names (PRINCIPAL-AMOUNT, ERROR-CODE, etc.) - it never
# saw the actual code to compare against. Fixed below.
EVAL_USER_TEMPLATE = """CHUNK (id: {chunk_id}, language: {language})

ACTUAL SOURCE CODE:
```{language}
{code}
```

GENERATED DOCUMENTATION TO EVALUATE:
Summary: {summary}
Inputs: {inputs}
Outputs: {outputs}
Business logic: {business_logic}
Dependencies used: {dependencies_used}

Check the documentation against the ACTUAL SOURCE CODE above, line by line if \
necessary. Flag anything inaccurate, unsupported by the code, hallucinated \
(e.g. variable names or fields that don't appear in the code), or missing. \
Respond with the required JSON object."""


def _extract_json(raw_text: str) -> dict:
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


def evaluate_chunk_doc(chunk: Chunk, doc: ChunkDoc, max_retries: int = 2) -> EvalResult:
    # Short-circuit: documenter already failed (see documenter.py's fallback
    # ChunkDoc on repeated JSON-parse failure) - no need to spend an LLM call
    # scoring a doc we already know is empty.
    if not doc.summary.strip() or not doc.business_logic.strip():
        return EvalResult(
            chunk_id=chunk.id,
            overall_score=0.0,
            issues=["Documentation generation failed or returned empty content."],
            needs_refinement=True,
        )

    # Guard: refuse to evaluate against nothing. Mirrors the same guard added
    # to documenter.py - if the chunk has no code, scoring "accuracy" against
    # it is meaningless.
    if not chunk.code or not chunk.code.strip():
        raise ValueError(
            f"evaluate_chunk_doc: chunk {chunk.id!r} has empty/missing 'code' - "
            f"cannot evaluate documentation accuracy against nothing."
        )

    llm = get_llm(temperature=0.0)
    user_prompt = EVAL_USER_TEMPLATE.format(
        chunk_id=chunk.id,
        language=chunk.language,
        code=chunk.code,
        summary=doc.summary,
        inputs=", ".join(doc.inputs) if doc.inputs else "(none listed)",
        outputs=", ".join(doc.outputs) if doc.outputs else "(none listed)",
        business_logic=doc.business_logic,
        dependencies_used=", ".join(doc.dependencies_used) if doc.dependencies_used else "(none listed)",
    )

    # Sanity check: catch any future regression where {code} silently stops
    # being interpolated into the prompt.
    assert chunk.code.strip() in user_prompt, (
        f"evaluate_chunk_doc: chunk.code was not found in the rendered prompt "
        f"for {chunk.id!r} - check that EVAL_USER_TEMPLATE still contains a "
        f"{{code}} placeholder."
    )

    messages = [("system", EVAL_SYSTEM_PROMPT), ("human", user_prompt)]

    last_error: Exception = ValueError("evaluate_chunk_doc: no attempts made")
    for attempt in range(max_retries + 1):
        try:
            response = llm.invoke(messages)
            raw_text = response.content if hasattr(response, "content") else str(response)
            data = _extract_json(raw_text)
            score = float(data.get("overall_score", 0.0))
            score = max(0.0, min(100.0, score))
            issues = [str(x) for x in data.get("issues", [])]
            return EvalResult(
                chunk_id=chunk.id,
                overall_score=score,
                issues=issues,
                needs_refinement=score < PASS_THRESHOLD,
            )
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            last_error = exc
            if attempt < max_retries:
                messages.append(("human",
                    f"Your previous response could not be parsed (error: {exc}). "
                    f"Respond again with ONLY the raw JSON object, nothing else."))
                continue

    # Fail safe, not fail loud - same rationale as documenter.py: don't crash
    # the whole graph on one bad LLM response. Score 0 routes this chunk into
    # the existing refine -> flag_for_human path automatically.
    return EvalResult(
        chunk_id=chunk.id,
        overall_score=0.0,
        issues=[f"Evaluation failed after {max_retries + 1} attempts: {last_error}"],
        needs_refinement=True,
    )