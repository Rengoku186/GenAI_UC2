import os
import pytest
from unittest.mock import MagicMock, patch

from src.tools.dependency_scanner import (
    detect_language_by_extension,
    detect_language_with_ai,
    detect_language,
    parse_file_chunks,
    scan_project,
    _LANGUAGE_DETECTION_CACHE,
)


@pytest.fixture(autouse=True)
def clear_detection_cache():
    """Ensure cache is reset before each test."""
    _LANGUAGE_DETECTION_CACHE.clear()
    yield
    _LANGUAGE_DETECTION_CACHE.clear()


# ============================================================================
# 1. Extension-Based Detection Tests
# ============================================================================

def test_detect_language_by_extension():
    assert detect_language_by_extension("program.cbl") == "cobol"
    assert detect_language_by_extension("payroll.cob") == "cobol"
    assert detect_language_by_extension("MODULE.COBOL") == "cobol"
    assert detect_language_by_extension("subroutine.cpy") == "cobol"
    assert detect_language_by_extension("legacy.pco") == "cobol"

    assert detect_language_by_extension("form.frm") == "vb"
    assert detect_language_by_extension("module.bas") == "vb"
    assert detect_language_by_extension("clsAccount.cls") == "vb"
    assert detect_language_by_extension("script.vbs") == "vb"
    assert detect_language_by_extension("logic.vb") == "vb"

    assert detect_language_by_extension("Service.java") == "java"
    assert detect_language_by_extension("Helper.jav") == "java"

    assert detect_language_by_extension("readme.md") == "unknown"
    assert detect_language_by_extension("script.py") == "unknown"
    assert detect_language_by_extension("unknown_file") == "unknown"


# ============================================================================
# 2. AI Language Detection & Fallback Tests
# ============================================================================

def test_detect_language_with_ai_success_json():
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = '{"language": "cobol", "confidence": 0.98}'
    mock_llm.invoke.return_value = mock_response

    with patch("src.tools.dependency_scanner.get_llm", return_value=mock_llm):
        code_snippet = "IDENTIFICATION DIVISION.\nPROGRAM-ID. BILL100."
        result = detect_language_with_ai(code_snippet, file_path="mystery_file.txt")
        assert result == "cobol"


def test_detect_language_with_ai_handles_aliases():
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = '```json\n{"language": "Visual Basic", "confidence": 0.95}\n```'
    mock_llm.invoke.return_value = mock_response

    with patch("src.tools.dependency_scanner.get_llm", return_value=mock_llm):
        code_snippet = "Sub ProcessPayroll()\nMsgBox \"Processing\"\nEnd Sub"
        result = detect_language_with_ai(code_snippet, file_path="legacy.unknown")
        assert result == "vb"


def test_detect_language_with_ai_failure_returns_none():
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = RuntimeError("API key invalid or connection timed out")

    with patch("src.tools.dependency_scanner.get_llm", return_value=mock_llm):
        result = detect_language_with_ai("public class Service {}", file_path="Service.txt")
        assert result is None


def test_detect_language_fallback_to_extension_on_ai_failure(tmp_path):
    java_file = tmp_path / "BillingService.java"
    java_file.write_text("public class BillingService { public void run() {} }", encoding="utf-8")

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = Exception("LLM unavailable")

    with patch("src.tools.dependency_scanner.get_llm", return_value=mock_llm):
        # Should gracefully catch the LLM exception and fallback to extension (.java)
        result = detect_language(str(java_file), use_ai=True)
        assert result == "java"


def test_detect_language_offline_mode(tmp_path):
    cobol_file = tmp_path / "BILL100.cbl"
    cobol_file.write_text("       PROCEDURE DIVISION.", encoding="utf-8")

    with patch("src.tools.dependency_scanner.get_llm") as mock_get_llm:
        result = detect_language(str(cobol_file), use_ai=False)
        assert result == "cobol"
        # Offline mode must not call get_llm
        mock_get_llm.assert_not_called()


# ============================================================================
# 3. File Chunk Parsing Tests
# ============================================================================

def test_parse_cobol_chunks(tmp_path):
    cbl_file = tmp_path / "SAMPLE.cbl"
    cbl_file.write_text("""       IDENTIFICATION DIVISION.
       PROGRAM-ID. SAMPLE1.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  VAR1 PIC X VALUE 'A'.
       PROCEDURE DIVISION.
       INIT-PARA.
           DISPLAY "INIT".
       CALC-PARA.
           COMPUTE X = 1 + 1.
       EXIT-PARA.
           STOP RUN.
""", encoding="utf-8")

    chunks = parse_file_chunks(str(cbl_file), use_ai=False)
    assert len(chunks) == 3
    names = [c[2] for c in chunks]
    assert names == ["INIT-PARA", "CALC-PARA", "EXIT-PARA"]

    # Verify qualified IDs and scopes
    assert chunks[0][0].endswith("::SAMPLE1::INIT-PARA")
    assert chunks[0][1] == "SAMPLE1"
    assert chunks[0][4] == 7  # start line for INIT-PARA
    assert chunks[0][5] == 8  # end line


def test_parse_vb_chunks(tmp_path):
    vb_file = tmp_path / "OrderModule.bas"
    vb_file.write_text("""Attribute VB_Name = "OrderModule"

Public Sub ProcessOrder()
    Call ValidateOrder
End Sub

Private Function ValidateOrder() As Boolean
    ValidateOrder = True
End Function
""", encoding="utf-8")

    chunks = parse_file_chunks(str(vb_file), use_ai=False)
    assert len(chunks) == 2
    names = [c[2] for c in chunks]
    assert "ProcessOrder" in names
    assert "ValidateOrder" in names
    assert chunks[0][1] == "OrderModule"


def test_parse_java_chunks(tmp_path):
    java_file = tmp_path / "UserService.java"
    java_file.write_text("""package com.example.service;

public class UserService {

    public void createUser() {
        validateUser();
    }

    private boolean validateUser() {
        return true;
    }
}
""", encoding="utf-8")

    chunks = parse_file_chunks(str(java_file), use_ai=False)
    assert len(chunks) == 2
    names = [c[2] for c in chunks]
    assert "createUser" in names
    assert "validateUser" in names
    assert chunks[0][1] == "com.example.service.UserService"


def test_parse_unstructured_file_fallback(tmp_path):
    txt_file = tmp_path / "script.txt"
    txt_file.write_text("PRINT 'Hello'\nPRINT 'World'\n", encoding="utf-8")

    chunks = parse_file_chunks(str(txt_file), use_ai=False)
    assert len(chunks) == 1
    assert chunks[0][2] == "MAIN"
    assert chunks[0][4] == 1
    assert chunks[0][5] == 2


# ============================================================================
# 4. Dependency Scan & Disambiguation Tests
# ============================================================================

def test_scan_cobol_sample(tmp_path):
    cobol_file = tmp_path / "BILL100.cbl"
    cobol_file.write_text("""       IDENTIFICATION DIVISION.
       PROGRAM-ID. BILL100.
       PROCEDURE DIVISION.
       MAIN-PARA.
           PERFORM VALIDATE-INPUT
           PERFORM CALC-INTEREST
           STOP RUN.

       VALIDATE-INPUT.
           IF ACCT-BAL < 0
               PERFORM RAISE-ERROR
           END-IF.

       CALC-INTEREST.
           COMPUTE INTEREST-VAL = 100.0 * 0.05.

       RAISE-ERROR.
           DISPLAY "ERROR".
""", encoding="utf-8")

    graph = scan_project([str(cobol_file)], use_ai=False)

    # Check nodes
    assert len(graph.nodes) >= 4
    main_node = [n for n in graph.nodes if n.endswith("::MAIN-PARA")][0]
    val_node = [n for n in graph.nodes if n.endswith("::VALIDATE-INPUT")][0]
    calc_node = [n for n in graph.nodes if n.endswith("::CALC-INTEREST")][0]
    err_node = [n for n in graph.nodes if n.endswith("::RAISE-ERROR")][0]

    # Check edges
    assert graph.has_edge(main_node, val_node)
    assert graph.has_edge(main_node, calc_node)
    assert graph.has_edge(val_node, err_node)

    # Check node metadata
    assert val_node in graph.nodes[main_node]["depends_on"]
    assert calc_node in graph.nodes[main_node]["depends_on"]
    assert graph.nodes[main_node]["language"] == "cobol"


def test_same_name_subroutines_different_files(tmp_path):
    f1 = tmp_path / "file1.cbl"
    f1.write_text("""       IDENTIFICATION DIVISION.
       PROGRAM-ID. PROG1.
       PROCEDURE DIVISION.
       CALLER-SUB.
           PERFORM COMMON-SUB.
       COMMON-SUB.
           DISPLAY '1'.
""", encoding="utf-8")

    f2 = tmp_path / "file2.cbl"
    f2.write_text("""       IDENTIFICATION DIVISION.
       PROGRAM-ID. PROG2.
       PROCEDURE DIVISION.
       CALLER-SUB.
           PERFORM COMMON-SUB.
       COMMON-SUB.
           DISPLAY '2'.
""", encoding="utf-8")

    graph = scan_project([str(f1), str(f2)], use_ai=False)

    assert len(graph.nodes) == 4

    caller1 = [n for n in graph.nodes if str(f1) in n and n.endswith("::CALLER-SUB")][0]
    common1 = [n for n in graph.nodes if str(f1) in n and n.endswith("::COMMON-SUB")][0]

    caller2 = [n for n in graph.nodes if str(f2) in n and n.endswith("::CALLER-SUB")][0]
    common2 = [n for n in graph.nodes if str(f2) in n and n.endswith("::COMMON-SUB")][0]

    # Disambiguation check: CALLER-SUB in file1 must link to COMMON-SUB in file1
    assert graph.has_edge(caller1, common1)
    assert not graph.has_edge(caller1, common2)

    # CALLER-SUB in file2 must link to COMMON-SUB in file2
    assert graph.has_edge(caller2, common2)
    assert not graph.has_edge(caller2, common1)


def test_scan_java_sample(tmp_path):
    java_file = tmp_path / "OrderService.java"
    java_file.write_text("""package com.example;

public class OrderService {
    public void checkout() {
        verifyStock();
        chargeCard();
    }

    public void verifyStock() {
    }

    public void chargeCard() {
    }
}
""", encoding="utf-8")

    graph = scan_project([str(java_file)], use_ai=False)
    assert len(graph.nodes) == 3

    checkout_node = [n for n in graph.nodes if n.endswith("::checkout")][0]
    stock_node = [n for n in graph.nodes if n.endswith("::verifyStock")][0]
    card_node = [n for n in graph.nodes if n.endswith("::chargeCard")][0]

    assert graph.has_edge(checkout_node, stock_node)
    assert graph.has_edge(checkout_node, card_node)
    assert graph.nodes[checkout_node]["language"] == "java"


def test_scan_vb_sample(tmp_path):
    vb_file = tmp_path / "Payroll.bas"
    vb_file.write_text("""Attribute VB_Name = "PayrollModule"

Public Sub Main()
    Call ProcessTaxes
    Call PrintSummary
End Sub

Public Sub ProcessTaxes()
End Sub

Public Sub PrintSummary()
End Sub
""", encoding="utf-8")

    graph = scan_project([str(vb_file)], use_ai=False)
    assert len(graph.nodes) == 3

    main_node = [n for n in graph.nodes if n.endswith("::Main")][0]
    tax_node = [n for n in graph.nodes if n.endswith("::ProcessTaxes")][0]
    summary_node = [n for n in graph.nodes if n.endswith("::PrintSummary")][0]

    assert graph.has_edge(main_node, tax_node)
    assert graph.has_edge(main_node, summary_node)
    assert graph.nodes[main_node]["language"] == "vb"


def test_scan_project_missing_or_empty_files(tmp_path):
    missing_file = str(tmp_path / "non_existent.cbl")
    empty_file = tmp_path / "empty.cbl"
    empty_file.write_text("", encoding="utf-8")

    # Should not crash on missing files or empty files
    graph = scan_project([missing_file, str(empty_file)], use_ai=False)
    assert len(graph.nodes) == 1  # Empty file gets single fallback MAIN chunk
    empty_node = list(graph.nodes)[0]
    assert "empty.cbl" in empty_node


def test_ai_detection_with_extensionless_file(tmp_path):
    mystery_file = tmp_path / "LEGACY_PAYROLL"
    mystery_file.write_text("""       IDENTIFICATION DIVISION.
       PROGRAM-ID. PAYROLL.
       PROCEDURE DIVISION.
       MAIN-PARA.
           DISPLAY 'HELLO'.
""", encoding="utf-8")

    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = '{"language": "cobol", "confidence": 0.99}'
    mock_llm.invoke.return_value = mock_response

    with patch("src.tools.dependency_scanner.get_llm", return_value=mock_llm):
        lang = detect_language(str(mystery_file), use_ai=True)
        assert lang == "cobol"


def test_detection_caching(tmp_path):
    sample_file = tmp_path / "CacheTest.java"
    sample_file.write_text("public class CacheTest {}", encoding="utf-8")

    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = '{"language": "java", "confidence": 0.99}'
    mock_llm.invoke.return_value = mock_response

    with patch("src.tools.dependency_scanner.get_llm", return_value=mock_llm):
        lang1 = detect_language(str(sample_file), use_ai=True)
        lang2 = detect_language(str(sample_file), use_ai=True)
        assert lang1 == "java"
        assert lang2 == "java"
        # Clear heuristic matches are classified locally and never incur an
        # LLM call; repeated detection is served from the detector cache.
        assert mock_llm.invoke.call_count == 0
