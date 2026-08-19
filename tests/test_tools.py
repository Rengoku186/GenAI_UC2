"""Unit tests for AST tools, NetworkX graph tools, static analysis, and sandbox execution."""

import pytest
from src.tools.ast_tools import ASTTools
from src.tools.graph_tools import GraphTools
from src.tools.static_analysis_tools import StaticAnalysisTools
from src.tools.sandbox_exec import SandboxExecutor
from src.orchestrator.state import ChunkMetadata, DependencyEdge


def test_ast_tools_language_detection():
    assert ASTTools.detect_language("sample.cbl") == "cobol"
    assert ASTTools.detect_language("module.vb") == "vb"
    assert ASTTools.detect_language("service.java") == "java"


def test_graph_tools_analysis():
    chunks = [
        ChunkMetadata(chunk_id="C1", source_file="f1", language="cobol", line_start=1, line_end=10, name="MAIN", raw_code=""),
        ChunkMetadata(chunk_id="C2", source_file="f1", language="cobol", line_start=11, line_end=20, name="SUB", raw_code="")
    ]
    edges = [
        DependencyEdge(source_chunk="C1", target_chunk="C2", edge_type="calls", symbol="SUB")
    ]

    G = GraphTools.build_networkx_graph(chunks, edges)
    analysis = GraphTools.analyze_graph(G)
    assert analysis["node_count"] == 2
    assert analysis["edge_count"] == 1
    assert analysis["is_dag"] is True


def test_static_analysis_tools():
    valid_code = "def add(x: int, y: int) -> int:\n    return x + y\n"
    res = StaticAnalysisTools.validate_python_syntax(valid_code)
    assert res["valid_syntax"] is True
    assert "add" in res["functions"]

    invalid_code = "def bad_syntax(:"
    res_inv = StaticAnalysisTools.validate_python_syntax(invalid_code)
    assert res_inv["valid_syntax"] is False


def test_sandbox_executor_pytest():
    sandbox = SandboxExecutor(timeout_seconds=10)
    code = "def square(x):\n    return x * x\n"
    test = "import pytest\nfrom target_module import square\n\ndef test_sq():\n    assert square(3) == 9\n"

    result = sandbox.run_pytest("chunk_test", code, test)
    assert result.all_passed is True
    assert result.pass_count >= 1
    assert result.fail_count == 0


def test_java_static_analysis_tools():
    valid_java = """
    package com.example;
    import java.math.BigDecimal;

    public class PaymentProcessor {
        public BigDecimal processPayment(BigDecimal amount, String tier) {
            if (amount == null) {
                return BigDecimal.ZERO;
            }
            return amount.multiply(new BigDecimal("1.05"));
        }
    }
    """
    res = StaticAnalysisTools.validate_java_syntax(valid_java)
    assert res["valid_syntax"] is True
    assert "PaymentProcessor" in res["classes"]
    assert "processPayment" in res["methods"]
    assert "java.math.BigDecimal" in res["imports"]

    complexity = StaticAnalysisTools.calculate_java_cyclomatic_complexity(valid_java)
    assert complexity >= 2

    invalid_java = "public class Broken { void test() { if (true) { } "
    res_inv = StaticAnalysisTools.validate_java_syntax(invalid_java)
    assert res_inv["valid_syntax"] is False

