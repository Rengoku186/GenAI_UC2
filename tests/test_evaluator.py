import json
import pytest
from unittest.mock import MagicMock, patch

from src.schemas import Chunk, ChunkDoc, EvalResult
from src.agents.evaluator import (
    evaluate_chunk_doc,
    _preflight_variable_check,
    _extract_json,
    PASS_THRESHOLD,
)


def test_preflight_variable_check():
    code = "       COMPUTE INTEREST-VAL = ACCT-BAL * 0.05."

    # Accurate variables -> no issues, 0 penalty
    issues, penalty = _preflight_variable_check(code, inputs=["ACCT-BAL"], outputs=["INTEREST-VAL"])
    assert len(issues) == 0
    assert penalty == 0.0

    # Hallucinated non-existent variable -> issue flagged, penalty applied
    issues, penalty = _preflight_variable_check(code, inputs=["FAKE_INPUT_PARAM"], outputs=["INTEREST-VAL"])
    assert len(issues) == 1
    assert "FAKE_INPUT_PARAM" in issues[0]
    assert penalty > 0.0


def test_evaluate_chunk_doc_high_quality():
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = json.dumps({
        "business_logic_score": 95.0,
        "accuracy_score": 98.0,
        "variable_consistency_score": 100.0,
        "clarity_score": 95.0,
        "issues": [],
    })
    mock_llm.invoke.return_value = mock_response

    chunk = Chunk(
        id="BILL100::CALC-INTEREST",
        file_path="BILL100.cbl",
        name="CALC-INTEREST",
        code="       COMPUTE INTEREST-VAL = ACCT-BAL * 0.05.",
        language="cobol",
        start_line=19,
        end_line=21,
    )
    doc = ChunkDoc(
        chunk_id="BILL100::CALC-INTEREST",
        summary="Calculates 5% monthly interest on account balance.",
        inputs=["ACCT-BAL"],
        outputs=["INTEREST-VAL"],
        business_logic="Calculates interest using formula: INTEREST-VAL = ACCT-BAL * 0.05.",
    )

    with patch("src.agents.evaluator.get_llm", return_value=mock_llm):
        result = evaluate_chunk_doc(chunk, doc)

    assert result.overall_score >= 90.0
    assert result.needs_refinement is False
    assert len(result.issues) == 0


def test_evaluate_chunk_doc_missing_business_logic_penalized():
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = json.dumps({
        "business_logic_score": 50.0,  # Penalized for missing exact formula & rate
        "accuracy_score": 80.0,
        "variable_consistency_score": 80.0,
        "clarity_score": 70.0,
        "issues": ["[MISSING_FORMULA] The exact 5% calculation formula was not documented."],
    })
    mock_llm.invoke.return_value = mock_response

    chunk = Chunk(
        id="BILL100::CALC-INTEREST",
        file_path="BILL100.cbl",
        name="CALC-INTEREST",
        code="       COMPUTE INTEREST-VAL = ACCT-BAL * 0.05.",
        language="cobol",
        start_line=19,
        end_line=21,
    )
    # Vague documentation with missing formula
    doc = ChunkDoc(
        chunk_id="BILL100::CALC-INTEREST",
        summary="Processes interest.",
        inputs=["ACCT-BAL"],
        outputs=["INTEREST-VAL"],
        business_logic="Updates the interest field.",
    )

    with patch("src.agents.evaluator.get_llm", return_value=mock_llm):
        result = evaluate_chunk_doc(chunk, doc)

    # Weighted: 0.4*50 + 0.25*80 + 0.20*80 + 0.15*70 = 20 + 20 + 16 + 10.5 = 66.5 < 80
    assert result.overall_score < PASS_THRESHOLD
    assert result.needs_refinement is True
    assert any("[MISSING_FORMULA]" in i for i in result.issues)


def test_evaluate_chunk_doc_fast_path_boilerplate():
    # Boilerplate exit chunk should get fast-path 100 without LLM invocation
    exit_chunk = Chunk(
        id="BILL100::EXIT-PARA",
        file_path="BILL100.cbl",
        name="EXIT-PARA",
        code="       EXIT-PARA.\n           EXIT.",
        language="cobol",
        start_line=30,
        end_line=31,
    )
    doc = ChunkDoc(
        chunk_id="BILL100::EXIT-PARA",
        summary="Exit paragraph.",
        inputs=[],
        outputs=[],
        business_logic="Standard control exit routine.",
    )

    with patch("src.agents.evaluator.get_llm") as mock_get_llm:
        result = evaluate_chunk_doc(exit_chunk, doc)
        mock_get_llm.assert_not_called()

    assert result.overall_score == 100.0
    assert result.needs_refinement is False


def test_evaluate_chunk_doc_empty_doc_fails():
    chunk = Chunk(
        id="BILL100::CALC",
        file_path="BILL100.cbl",
        name="CALC",
        code="       COMPUTE X = 1.",
        language="cobol",
        start_line=1,
        end_line=1,
    )
    doc = ChunkDoc(
        chunk_id="BILL100::CALC",
        summary="",
        inputs=[],
        outputs=[],
        business_logic="",
    )

    result = evaluate_chunk_doc(chunk, doc)
    assert result.overall_score == 0.0
    assert result.needs_refinement is True
    assert "[EMPTY_DOC]" in result.issues[0]
