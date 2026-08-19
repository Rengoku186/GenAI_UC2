"""Agent 11: Test Generator Agent."""

from __future__ import annotations
import re
from pydantic import BaseModel, Field
from src.agents.base_agent import BaseAgent
from src.orchestrator.state import PipelineState, ChunkMetadata, DocSection, GeneratedCode, TestResult
from src.prompts.codegen_prompts import (
    TESTGEN_SYSTEM_PROMPT,
    TESTGEN_USER_PROMPT
)


class TestGenSchema(BaseModel):
    test_code: str = Field(description="Complete, executable pytest suite code")


class TestGeneratorAgent(BaseAgent):
    """Generates pytest test suites derived directly from documented business rules."""
    __test__ = False

    def __init__(self, config_dir: str = "configs"):
        super().__init__("test_generator", config_dir=config_dir)

    def generate_chunk_tests(self, chunk: ChunkMetadata, doc: DocSection, code_obj: GeneratedCode) -> TestResult:
        """Generates pytest unit test suite for a single chunk."""
        def mock_testgen() -> TestGenSchema:
            clean_name = chunk.name.upper()
            if chunk.language == "cobol":
                if "TIER" in clean_name or "2100" in clean_name:
                    tests = '''import pytest
from decimal import Decimal
from target_module import calculate_tier_surcharge

def test_tier_a_surcharge():
    result = calculate_tier_surcharge("A", Decimal("10000.00"))
    assert result == Decimal("0.00")

def test_tier_b_surcharge():
    result = calculate_tier_surcharge("B", Decimal("10000.00"))
    assert result == Decimal("50.00")

def test_tier_c_surcharge():
    result = calculate_tier_surcharge("C", Decimal("10000.00"))
    assert result == Decimal("150.00")

def test_tier_other_surcharge():
    result = calculate_tier_surcharge("D", Decimal("10000.00"))
    assert result == Decimal("300.00")
'''
                elif "INTEREST" in clean_name or "2200" in clean_name:
                    tests = '''import pytest
from decimal import Decimal
from target_module import calculate_interest

def test_calculate_monthly_interest():
    res = calculate_interest(Decimal("12000.00"), Decimal("6.00"))
    assert res.monthly_rate == Decimal("0.005")
    assert res.monthly_interest == Decimal("60.00")
    assert res.total_interest == Decimal("60.00")

def test_accumulate_prior_interest():
    res = calculate_interest(Decimal("10000.00"), Decimal("12.00"), prior_total_interest=Decimal("100.00"))
    assert res.monthly_rate == Decimal("0.01")
    assert res.monthly_interest == Decimal("100.00")
    assert res.total_interest == Decimal("200.00")
'''
                elif "AMORTIZATION" in clean_name or "2300" in clean_name:
                    tests = '''import pytest
from decimal import Decimal
from target_module import compute_amortization

def test_amortization_zero_rate():
    res = compute_amortization(
        principal_amt=Decimal("1200.00"),
        term_months=12,
        monthly_rate=Decimal("0.00"),
        monthly_interest=Decimal("0.00"),
        tier_surcharge=Decimal("0.00")
    )
    assert res.monthly_payment == Decimal("100.00")
    assert res.principal_paid == Decimal("100.00")
    assert res.final_balance == Decimal("1100.00")

def test_invalid_term_raises():
    with pytest.raises(ValueError):
        compute_amortization(Decimal("1000.00"), 0, Decimal("0.01"), Decimal("10.00"))
'''
                else:
                    func_name = re.sub(r"[^a-zA-Z0-9_]", "_", chunk.name.lower()).strip("_")
                    tests = f'''import pytest
from target_module import execute_{func_name}

def test_execute_{func_name}():
    res = execute_{func_name}({{"initial": True}})
    assert res["status"] == "SUCCESS"
    assert res["processed_{func_name}"] is True
'''
            elif chunk.language == "vb":
                if "ValidateCustomer" in chunk.name:
                    tests = '''import pytest
from target_module import CustomerValidator, CustomerRecord

def test_valid_prime_customer():
    val = CustomerValidator()
    cust = CustomerRecord(
        customer_id="CUST001",
        full_name="Alice Smith",
        age=35,
        credit_score=780,
        annual_income=100000.0,
        total_debt=20000.0,
        email="alice@example.com",
        is_active=True
    )
    res = val.validate_customer(cust)
    assert res.is_valid is True
    assert res.risk_category == "LOW_RISK_PRIME"
    assert res.max_loan_eligibility == 450000.0
    assert res.debt_to_income_ratio == 20.0

def test_underage_customer_rejected():
    val = CustomerValidator()
    cust = CustomerRecord(
        customer_id="CUST002",
        full_name="Minor User",
        age=16,
        credit_score=700,
        annual_income=50000.0,
        total_debt=5000.0,
        email="minor@example.com",
        is_active=True
    )
    res = val.validate_customer(cust)
    assert res.is_valid is False
    assert "Customer age must be between 18 and 120." in res.error_messages
'''
                elif "DetermineRiskCategory" in chunk.name:
                    tests = '''import pytest
from target_module import determine_risk_category

def test_prime_risk():
    assert determine_risk_category(760, 30.0) == "LOW_RISK_PRIME"

def test_standard_risk():
    assert determine_risk_category(660, 40.0) == "MEDIUM_RISK_STANDARD"
'''
                elif "CalculateLoanLimit" in chunk.name:
                    tests = '''import pytest
from target_module import calculate_loan_limit

def test_prime_limit():
    assert calculate_loan_limit(100000.0, "LOW_RISK_PRIME") == 450000.0

def test_standard_limit():
    assert calculate_loan_limit(100000.0, "MEDIUM_RISK_STANDARD") == 300000.0
'''
                else:
                    func_name = re.sub(r"[^a-zA-Z0-9_]", "_", chunk.name.lower()).strip("_")
                    tests = f'''import pytest
from target_module import execute_{func_name}

def test_execute_{func_name}():
    res = execute_{func_name}()
    assert res["status"] == "SUCCESS"
'''
            elif chunk.language == "java":
                if "processDeposit" in chunk.name:
                    tests = '''import pytest
from decimal import Decimal
from target_module import process_deposit, BankAccount

def test_process_deposit_success():
    acc = BankAccount(account_id="ACC001", current_balance=Decimal("500.00"))
    tx = process_deposit(acc, "TX001", Decimal("250.00"))
    assert tx.is_approved is True
    assert tx.resulting_balance == Decimal("750.00")
    assert acc.current_balance == Decimal("750.00")

def test_process_deposit_negative_rejected():
    acc = BankAccount(account_id="ACC002", current_balance=Decimal("100.00"))
    tx = process_deposit(acc, "TX002", Decimal("-50.00"))
    assert tx.is_approved is False
    assert acc.current_balance == Decimal("100.00")
'''
                elif "processWithdrawal" in chunk.name:
                    tests = '''import pytest
from decimal import Decimal
from target_module import process_withdrawal, BankAccount

def test_process_withdrawal_overdraft_fee():
    acc = BankAccount(account_id="ACC003", current_balance=Decimal("50.00"), overdraft_protection_enabled=True)
    tx = process_withdrawal(acc, "TX003", Decimal("100.00"))
    assert tx.is_approved is True
    assert tx.resulting_balance == Decimal("-85.00")
    assert acc.current_balance == Decimal("-85.00")

def test_process_withdrawal_daily_limit():
    acc = BankAccount(account_id="ACC004", current_balance=Decimal("5000.00"))
    tx = process_withdrawal(acc, "TX004", Decimal("3000.00"))
    assert tx.is_approved is False
'''
                else:
                    func_name = re.sub(r"[^a-zA-Z0-9_]", "_", chunk.name.lower()).strip("_")
                    tests = f'''import pytest
from target_module import execute_{func_name}

def test_execute_{func_name}():
    res = execute_{func_name}()
    assert res["status"] == "SUCCESS"
'''
            else:
                tests = '''import pytest
from target_module import execute_service

def test_execute_service():
    res = execute_service()
    assert res["status"] == "SUCCESS"
'''
            return TestGenSchema(test_code=tests.strip())

        user_prompt = TESTGEN_USER_PROMPT.format(
            chunk_id=chunk.chunk_id,
            business_rules="\n".join([f"- {r}" for r in doc.business_rules]),
            target_code=code_obj.target_code
        )

        res = self.invoke_structured(
            schema=TestGenSchema,
            system_prompt=TESTGEN_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            mock_fallback_generator=mock_testgen
        )

        return TestResult(
            chunk_id=chunk.chunk_id,
            test_code=res.test_code,
            pass_count=0,
            fail_count=0,
            coverage_pct=0.0,
            all_passed=False
        )

    def execute(self, state: PipelineState) -> dict:
        chunks = {c.chunk_id: c for c in state.get("chunks", [])}
        docs = state.get("docs", {})
        generated = state.get("generated_code", {})
        tests = dict(state.get("tests", {}))

        target_chunk_id = state.get("current_chunk_id")
        if target_chunk_id and target_chunk_id in generated and target_chunk_id in chunks:
            target_chunks = [chunks[target_chunk_id]]
        else:
            target_chunks = [chunks[cid] for cid in generated if cid in chunks]

        for chunk in target_chunks:
            if chunk.chunk_id not in tests:
                doc = docs.get(chunk.chunk_id, DocSection(chunk_id=chunk.chunk_id, purpose="Default", control_flow="Sequential"))
                code_obj = generated[chunk.chunk_id]
                t_obj = self.generate_chunk_tests(chunk, doc, code_obj)
                tests[chunk.chunk_id] = t_obj

        return {
            "tests": tests,
            "stage": "test_generation"
        }
