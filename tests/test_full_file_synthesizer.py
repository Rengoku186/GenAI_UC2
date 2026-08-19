"""Unit tests for full-file synthesis engine — Java-only modernization mode."""

import pytest
from src.evaluation.full_file_synthesizer import FullFileSynthesizer


def test_loan_calculator_full_synthesis():
    synth = FullFileSynthesizer.synthesize_file_modernization("loan_calculator.cbl", [], {}, {})
    assert synth["module_name"] == "loan_calculator"
    # Java service must be present
    assert "class LoanCalculatorService" in synth["java_code"]
    # JUnit 5 tests must be present
    assert "@Test" in synth["java_tests"]
    assert "junit" in synth["java_tests"].lower()
    # Documentation must be populated
    assert len(synth["documentation_markdown"]) > 100
    # No Python output in Java-only mode
    assert "python_code" not in synth
    assert "python_tests" not in synth


def test_customer_validator_full_synthesis():
    synth = FullFileSynthesizer.synthesize_file_modernization("customer_validator.vb", [], {}, {})
    assert synth["module_name"] == "customer_validator"
    assert "public class CustomerValidator" in synth["java_code"]
    assert "@Test" in synth["java_tests"]
    assert "python_code" not in synth
    assert "python_tests" not in synth


def test_account_processor_full_synthesis():
    synth = FullFileSynthesizer.synthesize_file_modernization("account_processor.java", [], {}, {})
    assert synth["module_name"] == "account_processor"
    assert "public class AccountProcessor" in synth["java_code"]
    assert "@Test" in synth["java_tests"]
    assert "python_code" not in synth
    assert "python_tests" not in synth


def test_demo_application_full_synthesis_and_documentation():
    synth = FullFileSynthesizer.synthesize_file_modernization("DemoApplication.java", [], {}, {})
    assert synth["module_name"] == "demo_application"
    # Java service
    assert "public class ChequeProcessingApplication" in synth["java_code"]
    # JUnit 5 tests
    assert "@Test" in synth["java_tests"]
    # Documentation
    assert "Legacy System Documentation: Cheque Processing" in synth["documentation_markdown"]
    assert len(synth["documentation_markdown"]) > 500
    # No Python output
    assert "python_code" not in synth
    assert "python_tests" not in synth
