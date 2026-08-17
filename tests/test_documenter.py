import os
import json
import pytest
from unittest.mock import MagicMock, patch

from src.schemas import Chunk, ChunkDoc
from src.agents.documenter import (
    should_document_chunk,
    document_chunk,
    generate_master_documentation,
    export_flagged_json_only,
    _extract_json,
    _to_chunk_doc,
)


def test_should_document_chunk():
    # Boilerplate / exit chunk -> False
    exit_chunk = Chunk(
        id="cbl::EXIT-PARA",
        file_path="app.cbl",
        name="EXIT-PARA",
        code="       EXIT-PARA.\n           EXIT.",
        start_line=50,
        end_line=51,
    )
    assert should_document_chunk(exit_chunk) is False

    # Empty chunk -> False
    empty_chunk = Chunk(
        id="cbl::EMPTY",
        file_path="app.cbl",
        name="EMPTY",
        code="   \n   \n",
        start_line=1,
        end_line=2,
    )
    assert should_document_chunk(empty_chunk) is False

    # Substantial business logic chunk -> True
    logic_chunk = Chunk(
        id="cbl::CALC-INTEREST",
        file_path="app.cbl",
        name="CALC-INTEREST",
        code="       CALC-INTEREST.\n           COMPUTE INTEREST-VAL = ACCT-BAL * 0.05.\n           MOVE 'Y' TO CALC-DONE.",
        start_line=20,
        end_line=23,
    )
    assert should_document_chunk(logic_chunk) is True


def test_extract_json_resilience():
    # Clean JSON
    assert _extract_json('{"summary": "Test"}') == {"summary": "Test"}

    # Markdown fenced JSON
    fenced = "```json\n{\n  \"summary\": \"Fenced Test\",\n  \"inputs\": [\"A\"]\n}\n```"
    res = _extract_json(fenced)
    assert res["summary"] == "Fenced Test"
    assert res["inputs"] == ["A"]

    # Surrounding prose
    prose = "Here is the documentation:\n```\n{\"summary\": \"Prose Test\"}\n```\nHope this helps!"
    assert _extract_json(prose) == {"summary": "Prose Test"}


def test_document_chunk_success():
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = json.dumps({
        "summary": "Calculates monthly interest based on balance.",
        "inputs": ["ACCT-BAL"],
        "outputs": ["INTEREST-VAL"],
        "calculations_and_joins": "INTEREST-VAL = ACCT-BAL * 0.05",
        "business_logic": "Applies a 5% monthly interest rate to positive account balances.",
        "dependencies_used": ["DB::GET_ACCT"],
    })
    mock_llm.invoke.return_value = mock_response

    chunk = Chunk(
        id="BILL100::CALC-INTEREST",
        file_path="BILL100.cbl",
        name="CALC-INTEREST",
        code="       COMPUTE INTEREST-VAL = ACCT-BAL * 0.05.",
        language="cobol",
        start_line=20,
        end_line=21,
    )

    with patch("src.agents.documenter.get_llm", return_value=mock_llm):
        doc = document_chunk(chunk, dep_docs=[])

    assert doc.chunk_id == "BILL100::CALC-INTEREST"
    assert doc.summary == "Calculates monthly interest based on balance."
    assert "ACCT-BAL" in doc.inputs
    assert "INTEREST-VAL" in doc.outputs
    assert "5%" in doc.business_logic or "0.05" in doc.business_logic


def test_document_chunk_refinement_loop():
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = json.dumps({
        "summary": "Refined summary addressing missing variable.",
        "inputs": ["ACCT-BAL", "RATE-OVERRIDE"],
        "outputs": ["INTEREST-VAL"],
        "calculations_and_joins": "INTEREST-VAL = ACCT-BAL * RATE-OVERRIDE",
        "business_logic": "Corrected logic accounting for rate override.",
        "dependencies_used": [],
    })
    mock_llm.invoke.return_value = mock_response

    chunk = Chunk(
        id="BILL100::CALC",
        file_path="BILL100.cbl",
        name="CALC",
        code="       COMPUTE INTEREST-VAL = ACCT-BAL * RATE-OVERRIDE.",
        language="cobol",
        start_line=1,
        end_line=2,
    )
    prev_doc = ChunkDoc(
        chunk_id="BILL100::CALC",
        summary="Old summary",
        inputs=["ACCT-BAL"],
        outputs=["INTEREST-VAL"],
        business_logic="Old logic",
    )

    eval_critique = ["Missing RATE-OVERRIDE input variable", "Formula explanation incomplete"]

    with patch("src.agents.documenter.get_llm", return_value=mock_llm):
        doc = document_chunk(chunk, dep_docs=[], eval_issues=eval_critique, previous_doc=prev_doc)

    assert "RATE-OVERRIDE" in doc.inputs
    assert doc.summary == "Refined summary addressing missing variable."


def test_generate_master_documentation_three_sections():
    c1 = Chunk(
        id="BILL100::MAIN-PARA",
        file_path="BILL100.cbl",
        name="MAIN-PARA",
        code="       PERFORM VALIDATE-INPUT.\n       PERFORM CALC-INTEREST.",
        language="cobol",
        start_line=9,
        end_line=13,
    )
    c2 = Chunk(
        id="BILL100::VALIDATE-INPUT",
        file_path="BILL100.cbl",
        name="VALIDATE-INPUT",
        code="       IF ACCT-BAL < 0 PERFORM RAISE-ERROR END-IF.",
        language="cobol",
        start_line=14,
        end_line=18,
    )

    doc1 = ChunkDoc(
        chunk_id="BILL100::MAIN-PARA",
        summary="Main driver routine that coordinates validation and calculation.",
        inputs=["ACCT-BAL"],
        outputs=["REJECT-FLAG", "INTEREST-VAL"],
        business_logic="Orchestrates the lifecycle of monthly bill processing.",
    )
    doc2 = ChunkDoc(
        chunk_id="BILL100::VALIDATE-INPUT",
        summary="Validates account balance bounds.",
        inputs=["ACCT-BAL"],
        outputs=["REJECT-FLAG"],
        business_logic="Flags account if ACCT-BAL is negative.",
    )

    master_md = generate_master_documentation(
        chunks=[c1, c2],
        docs={"BILL100::MAIN-PARA": doc1, "BILL100::VALIDATE-INPUT": doc2},
        project_name="Billing System",
    )

    # 1. Section 1: Program Description
    assert "# Billing System - Technical Specification & Documentation" in master_md
    assert "## 1. Program Description" in master_md

    # 2. Section 2: Function-wise Explanations (with Main Entry Point & Inputs)
    assert "## 2. Function-wise Explanations" in master_md
    assert "### ★ Main Entry Point" in master_md
    assert "BILL100::MAIN-PARA" in master_md
    assert "Input Variables" in master_md
    assert "`ACCT-BAL`" in master_md

    # 3. Section 3: Key Technical Operations & Business Logic Table
    assert "## 3. Key Technical Operations & Business Logic" in master_md
    assert "| Section | Description |" in master_md
    assert "| `MAIN-PARA` |" in master_md
    assert "| `VALIDATE-INPUT` |" in master_md


def test_export_flagged_json_only(tmp_path):
    flagged = [
        {
            "chunk_id": "BILL100::FLAGGED",
            "overall_score": 55.0,
            "issues": ["Low confidence calculation"],
        }
    ]
    out_file = tmp_path / "flagged_items.json"
    export_flagged_json_only(flagged, str(out_file))

    assert os.path.exists(out_file)
    with open(out_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) == 1
    assert data[0]["chunk_id"] == "BILL100::FLAGGED"
