"""Unit tests for COBOL, VB, and Java language parsers."""

import pytest
from pathlib import Path
from src.parsers.cobol_parser import CobolParser
from src.parsers.vb_parser import VBParser
from src.parsers.java_parser import JavaParser


def test_cobol_parser_chunks_and_dependencies():
    cobol_code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TESTPROG.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-AMT PIC 9(5)V99.
       PROCEDURE DIVISION.
       0000-MAIN.
           PERFORM 1000-CALC
           STOP RUN.
       1000-CALC.
           ADD 100 TO WS-AMT.
    """
    parser = CobolParser("test.cbl", content=cobol_code)
    chunks = parser.parse_chunks()
    assert len(chunks) >= 2
    
    edges = parser.extract_dependencies(chunks)
    assert any(e.edge_type == "calls" and "1000" in e.target_chunk for e in edges)


def test_vb_parser_chunks_and_dependencies():
    vb_code = """
    Public Class MathService
        Public Function Add(a As Integer, b As Integer) As Integer
            Return a + b
        End Function
        Public Sub Run()
            Dim x = Add(5, 10)
        End Sub
    End Class
    """
    parser = VBParser("math.vb", content=vb_code)
    chunks = parser.parse_chunks()
    assert len(chunks) >= 2
    
    edges = parser.extract_dependencies(chunks)
    assert any(e.edge_type == "calls" and "Add" in e.symbol for e in edges)


def test_java_parser_chunks_and_dependencies():
    java_code = """
    package com.example;
    import java.util.List;

    public class AccountService {
        public double calculateFee(double balance) {
            return balance * 0.01;
        }

        public void applyFee(double balance) {
            double fee = calculateFee(balance);
        }
    }
    """
    parser = JavaParser("AccountService.java", content=java_code)
    chunks = parser.parse_chunks()
    assert len(chunks) >= 2
    
    edges = parser.extract_dependencies(chunks)
    assert any(e.edge_type == "calls" and "calculateFee" in e.symbol for e in edges)
