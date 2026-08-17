"""Evaluator Agent for Automated Quality Assurance of Code Documentation.

Audits AI-generated legacy code documentation against the ground-truth source code.
Uses a 4-dimensional parameterized rubric emphasizing business logic completeness,
mathematical formula precision, decision threshold accuracy, and zero-hallucination
compliance with temperature=0.1.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from src.agents.documenter import should_document_chunk
from src.schemas import Chunk, ChunkDoc, EvalResult
from src.utils.llm import get_llm

logger = logging.getLogger(__name__)

# ============================================================================
# Rubric Configuration & Constants
# ============================================================================

PASS_THRESHOLD = 80.0

# Weights for multi-dimensional evaluation (sum = 1.00)
WEIGHT_BUSINESS_LOGIC = 0.40
WEIGHT_ACCURACY = 0.25
WEIGHT_VARIABLES = 0.20
WEIGHT_CLARITY = 0.15

EVAL_SYSTEM_PROMPT = """You are a senior legacy code QA auditor verifying reverse-engineered \
documentation against the actual source code ahead of an enterprise modernization. \
You are rigorous and skeptical by default. Your highest priority is verifying that the \
BUSINESS LOGIC is completely and accurately captured.

### Business Logic Verification Checklist:
1. **Formulas & Arithmetic**: Are all mathematical calculations and formulas explicitly stated with exact numbers, operators, and equations (e.g., 'INTEREST = BALANCE * 0.05')?
2. **Decision Rules & Thresholds**: Are all conditional comparisons (e.g., '<', '>', '=', '<=', '!=') and exact boundary values (e.g., 'ACCT-BAL < 0') documented?
3. **State Changes & Flags**: Are all field modifications, flag toggles (e.g., 'REJECT-FLAG = Y'), and status updates explained?
4. **Data Access & Joins**: Are all database lookups, queries, or table joins described?
5. **Error & Exception Paths**: Are all failure conditions and error routines documented?
*Note: Vague generic text like "processes data" or "performs checks" without concrete formulas or thresholds must be severely penalized.*

### 4-Parameter Scoring Rubric (Each 0-100):
- **business_logic_score (40% weight)**: Coverage and precision of formulas, calculation rules, decision thresholds, and error branches.
- **accuracy_score (25% weight)**: Zero-hallucination compliance. Deduct heavily if the doc invents non-existent behavior, variables, or rules.
- **variable_consistency_score (20% weight)**: Correctness of listed input variables (read) and output variables (written) against the code.
- **clarity_score (15% weight)**: Plain-English clarity, conciseness, and actionability for a business analyst.

### Response Format:
You MUST respond with ONLY a single valid JSON object matching exactly this schema:
{{
  "business_logic_score": <float 0-100>,
  "accuracy_score": <float 0-100>,
  "variable_consistency_score": <float 0-100>,
  "clarity_score": <float 0-100>,
  "issues": [
    "[CATEGORY] Specific, actionable description of the issue or missing business rule"
  ]
}}

Categories for issues: [MISSING_FORMULA], [MISSING_CONDITION], [MISSING_ERROR_PATH], [HALLUCINATION], [VARIABLE_MISMATCH], [UNCLEAR_LOGIC].
"""

EVAL_USER_TEMPLATE = """CHUNK UNDER AUDIT
id: {chunk_id}
language: {language}
lines: {start_line}-{end_line}

ACTUAL SOURCE CODE:
```{language}
{code}
```

GENERATED DOCUMENTATION TO EVALUATE:
Summary: {summary}
Input Variables: {inputs}
Output Variables: {outputs}
Business Logic & Calculations: {business_logic}
Dependencies Relied Upon: {dependencies_used}

Audit this documentation against the ACTUAL SOURCE CODE line by line according to the 4 rubric dimensions.
Ensure all mathematical formulas, decision thresholds, and business rules are completely captured.
Respond strictly with the required JSON object."""


# ============================================================================
# Deterministic Pre-flight Checks
# ============================================================================

def _preflight_variable_check(code: str, inputs: List[str], outputs: List[str]) -> Tuple[List[str], float]:
    """Verify that documented variables actually appear in the source code.

    Returns:
        Tuple of (issues_list, penalty_points).
    """
    code_upper = code.upper()
    issues: List[str] = []
    penalty = 0.0

    all_vars = [("Input", v) for v in inputs] + [("Output", v) for v in outputs]
    for var_type, v in all_vars:
        clean_v = v.strip().upper()
        # Skip generic placeholder annotations
        if not clean_v or "NONE" in clean_v or "UNKNOWN" in clean_v or "GLOBAL" in clean_v:
            continue

        # Extract base identifier if qualified
        base_name = clean_v.split("::")[-1].split(".")[-1]

        # Check if base identifier appears in code tokens
        if base_name and base_name not in code_upper:
            issues.append(f"[VARIABLE_MISMATCH] {var_type} variable '{v}' was not found in the source code tokens.")
            penalty += 10.0

    return issues, min(penalty, 30.0)


# ============================================================================
# JSON Extraction & Processing
# ============================================================================

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


# ============================================================================
# Main Evaluation Function
# ============================================================================

def evaluate_chunk_doc(
    chunk: Chunk,
    doc: ChunkDoc,
    max_retries: int = 2,
) -> EvalResult:
    """Evaluate documentation quality against source code using a 4-parameter rubric.

    Args:
        chunk: The source code chunk.
        doc: The generated documentation to evaluate.
        max_retries: Maximum LLM retry attempts on unparseable responses.

    Returns:
        EvalResult with overall score, sub-scores, issue list, and refinement flag.
    """
    # 1. Guard against empty source code
    if not chunk.code or not chunk.code.strip():
        raise ValueError(
            f"evaluate_chunk_doc: chunk {chunk.id!r} has empty/missing 'code' - "
            f"cannot evaluate documentation accuracy against nothing."
        )

    # 2. Short-circuit: empty documentation automatically fails
    if not doc.summary.strip() or not doc.business_logic.strip():
        return EvalResult(
            chunk_id=chunk.id,
            overall_score=0.0,
            issues=["[EMPTY_DOC] Documentation generation failed or returned empty content."],
            needs_refinement=True,
        )

    # 3. Fast-path for non-functional / structural boilerplate chunks
    if not should_document_chunk(chunk):
        logger.debug("Fast-path evaluation for structural boilerplate chunk: %s", chunk.id)
        return EvalResult(
            chunk_id=chunk.id,
            overall_score=100.0,
            issues=[],
            needs_refinement=False,
        )

    # 4. Deterministic Pre-flight Variable Verification
    preflight_issues, deterministic_penalty = _preflight_variable_check(
        code=chunk.code,
        inputs=doc.inputs,
        outputs=doc.outputs,
    )

    # 5. LLM Semantic Evaluation with temperature=0.1
    llm = get_llm(temperature=0.1)

    user_prompt = EVAL_USER_TEMPLATE.format(
        chunk_id=chunk.id,
        language=chunk.language,
        start_line=chunk.start_line,
        end_line=chunk.end_line,
        code=chunk.code,
        summary=doc.summary,
        inputs=", ".join(doc.inputs) if doc.inputs else "(none listed)",
        outputs=", ".join(doc.outputs) if doc.outputs else "(none listed)",
        business_logic=doc.business_logic,
        dependencies_used=", ".join(doc.dependencies_used) if doc.dependencies_used else "(none listed)",
    )

    messages = [
        ("system", EVAL_SYSTEM_PROMPT),
        ("human", user_prompt),
    ]

    last_error: Exception = ValueError("evaluate_chunk_doc: no attempts made")
    for attempt in range(max_retries + 1):
        try:
            response = llm.invoke(messages)
            raw_text = response.content if hasattr(response, "content") else str(response)
            data = _extract_json(raw_text)

            # Extract sub-scores (0-100)
            bl_score = float(data.get("business_logic_score", 75.0))
            acc_score = float(data.get("accuracy_score", 75.0))
            var_score = float(data.get("variable_consistency_score", 75.0))
            clr_score = float(data.get("clarity_score", 75.0))

            # Clamp sub-scores
            bl_score = max(0.0, min(100.0, bl_score))
            acc_score = max(0.0, min(100.0, acc_score))
            var_score = max(0.0, min(100.0, var_score))
            clr_score = max(0.0, min(100.0, clr_score))

            # Deterministic weighted composite calculation
            weighted_score = (
                (WEIGHT_BUSINESS_LOGIC * bl_score)
                + (WEIGHT_ACCURACY * acc_score)
                + (WEIGHT_VARIABLES * var_score)
                + (WEIGHT_CLARITY * clr_score)
            )

            # Apply deterministic preflight penalty
            final_score = max(0.0, min(100.0, weighted_score - deterministic_penalty))

            # Collect issues
            llm_issues = [str(x) for x in data.get("issues", []) if str(x).strip()]
            all_issues = preflight_issues + llm_issues

            logger.info(
                "Evaluated chunk '%s': score=%.1f (BL=%.0f, Acc=%.0f, Var=%.0f, Clr=%.0f, Issues=%d)",
                chunk.id,
                final_score,
                bl_score,
                acc_score,
                var_score,
                clr_score,
                len(all_issues),
            )

            return EvalResult(
                chunk_id=chunk.id,
                overall_score=round(final_score, 1),
                issues=all_issues,
                needs_refinement=final_score < PASS_THRESHOLD,
            )

        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            last_error = exc
            if attempt < max_retries:
                messages.append(
                    (
                        "human",
                        f"Your previous response could not be parsed as valid JSON "
                        f"(error: {exc}). Respond again with ONLY the raw JSON object.",
                    )
                )
                continue

    # Fail-safe EvalResult
    return EvalResult(
        chunk_id=chunk.id,
        overall_score=0.0,
        issues=[f"[EVAL_FAILED] Evaluation failed after {max_retries + 1} attempts: {last_error}"],
        needs_refinement=True,
    )