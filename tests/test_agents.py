"""Unit tests for individual modernization agents (Java-only target mode)."""

import pytest
from src.orchestrator.state import ChunkMetadata, PipelineState
from src.agents.documenter import DocumenterAgent
from src.agents.doc_evaluator import DocEvaluatorAgent
from src.agents.code_generator import CodeGeneratorAgent
from src.agents.code_evaluator import CodeEvaluatorAgent
from src.agents.test_generator import TestGeneratorAgent


def test_documenter_and_evaluator_flow():
    chunk = ChunkMetadata(
        chunk_id="TEST_CHUNK",
        source_file="sample.cbl",
        language="cobol",
        line_start=1,
        line_end=15,
        name="CALC-TIER",
        raw_code="EVALUATE TIER WHEN 'A' MOVE 0 TO WS-SURCHARGE END-EVALUATE."
    )
    doc_agent = DocumenterAgent()
    doc = doc_agent.execute_chunk(chunk, {"dependency_graph": []})
    assert doc.chunk_id == "TEST_CHUNK"
    assert len(doc.business_rules) > 0

    eval_agent = DocEvaluatorAgent()
    eval_res = eval_agent.evaluate_chunk_doc(chunk, doc, retry_count=0)
    assert eval_res.target_id == "TEST_CHUNK"
    assert eval_res.score > 0.0


def test_codegen_and_testgen_flow_java_only():
    chunk = ChunkMetadata(
        chunk_id="VB_VAL",
        source_file="validator.vb",
        language="vb",
        line_start=1,
        line_end=20,
        name="ValidateCustomer",
        raw_code="Function ValidateCustomer(cust) ... End Function"
    )
    doc_agent = DocumenterAgent()
    doc = doc_agent.execute_chunk(chunk, {"dependency_graph": []})

    code_agent = CodeGeneratorAgent()
    code_obj = code_agent.generate_chunk_code(chunk, doc)
    assert code_obj.chunk_id == "VB_VAL"
    # Java-only mode: target_code is empty
    assert code_obj.target_code == ""
    # Java code generated
    assert "public class CustomerValidator" in code_obj.target_java_code

    test_agent = TestGeneratorAgent()
    test_res = test_agent.generate_chunk_tests(chunk, doc, code_obj)
    # JUnit 5 generated
    assert "@Test" in test_res.java_test_code
    # Python test is empty in Java-only mode
    assert test_res.test_code == ""
