"""Unit tests for full-file synthesis engine — Java-only modernization mode."""

import pytest
from src.evaluation.full_file_synthesizer import FullFileSynthesizer


def test_loan_calculator_full_synthesis():
    synth = FullFileSynthesizer.synthesize_file_modernization("loan_calculator.cbl", [], {}, {})
    assert synth["java_class_name"] == "LoanCalculator"
    # Java service must be present
    assert "class LoanCalculator" in synth["java_code"]
    # JUnit 5 test class must be present (no @Test methods when chunks are empty)
    assert "@DisplayName" in synth["java_tests"]
    assert "junit" in synth["java_tests"].lower()
    # Documentation must be populated
    assert len(synth["documentation_markdown"]) > 0
    # No Python output in Java-only mode
    assert "python_code" not in synth
    assert "python_tests" not in synth


def test_customer_validator_full_synthesis():
    synth = FullFileSynthesizer.synthesize_file_modernization("customer_validator.vb", [], {}, {})
    assert synth["java_class_name"] == "CustomerValidator"
    assert "class CustomerValidator" in synth["java_code"]
    assert "@DisplayName" in synth["java_tests"]
    assert "python_code" not in synth
    assert "python_tests" not in synth


def test_account_processor_full_synthesis():
    synth = FullFileSynthesizer.synthesize_file_modernization("AccountProcessor.java", [], {}, {})
    assert synth["java_class_name"] == "AccountProcessor"
    assert "class AccountProcessor" in synth["java_code"]
    assert "@DisplayName" in synth["java_tests"]
    assert "python_code" not in synth
    assert "python_tests" not in synth


def test_synthesizer_returns_required_keys():
    synth = FullFileSynthesizer.synthesize_file_modernization("DemoApplication.java", [], {}, {})
    for key in ("source_file", "java_class_name", "java_code", "java_tests", "documentation_markdown"):
        assert key in synth, f"Missing key: {key}"
    # No Python output
    assert "python_code" not in synth
    assert "python_tests" not in synth
