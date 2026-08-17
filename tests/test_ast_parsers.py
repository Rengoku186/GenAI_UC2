import pytest
from src.utils.ast_parsers import (
    parse_java_with_tree_sitter,
    parse_java_with_javalang,
    extract_java_calls_ast,
    parse_vb_blocks,
    parse_cobol_structural,
)


def test_java_tree_sitter_nested_and_methods():
    code = """package com.enterprise.billing;

public class InvoiceManager {

    public InvoiceManager() {
        initDefaults();
    }

    public void processInvoice(int invoiceId) {
        validateInvoice(invoiceId);
        chargeCard();
    }

    private boolean validateInvoice(int id) {
        return true;
    }

    public static class Helper {
        public void doHelp() {
            logHelp();
        }
    }
}
"""
    chunks = parse_java_with_tree_sitter("InvoiceManager.java", code)
    assert chunks is not None
    assert len(chunks) == 4

    names = [c[2] for c in chunks]
    assert "InvoiceManager" in names  # constructor
    assert "processInvoice" in names
    assert "validateInvoice" in names
    assert "doHelp" in names

    scopes = [c[1] for c in chunks]
    assert "com.enterprise.billing.InvoiceManager" in scopes
    assert "com.enterprise.billing.InvoiceManager.Helper" in scopes


def test_extract_java_calls_ast():
    snippet = """
    public void executePayment() {
        authGate.verify();
        gateway.charge();
        receiptService.sendEmail();
    }
    """
    calls = extract_java_calls_ast(snippet)
    assert calls is not None
    assert "verify" in calls
    assert "charge" in calls
    assert "sendEmail" in calls


def test_vb_block_parsing():
    code = """Attribute VB_Name = "AccountModule"

Public Sub CreateAccount()
    Call ValidateInputs
    Call SaveToDatabase
End Sub

Private Function ValidateInputs() As Boolean
    ValidateInputs = True
End Function

Public Property Get AccountBalance() As Double
    AccountBalance = mBalance
End Property
"""
    chunks = parse_vb_blocks("AccountModule.bas", code)
    assert len(chunks) == 3

    names = [c[2] for c in chunks]
    assert names == ["CreateAccount", "ValidateInputs", "AccountBalance"]
    assert chunks[0][1] == "AccountModule"
    assert chunks[0][4] == 3  # start line
    assert chunks[0][5] == 6  # end line spanning End Sub


def test_cobol_structural_parsing():
    code = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. LEDGER01.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-TOTAL PIC 9(5) VALUE 0.
       PROCEDURE DIVISION.
       INIT-LEDGER.
           MOVE 0 TO WS-TOTAL.
       PROCESS-ENTRIES.
           PERFORM COMPUTE-TAX.
       COMPUTE-TAX.
           COMPUTE WS-TOTAL = WS-TOTAL * 1.10.
       EXIT-PROGRAM.
           STOP RUN.
"""
    chunks = parse_cobol_structural("LEDGER01.cbl", code)
    assert len(chunks) == 4
    names = [c[2] for c in chunks]
    assert names == ["INIT-LEDGER", "PROCESS-ENTRIES", "COMPUTE-TAX", "EXIT-PROGRAM"]
    assert chunks[0][1] == "LEDGER01"
