"""Agent 11: Test Generator Agent (JUnit 5 for Java — Java-only mode)."""

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
    java_test_code: str = Field(description="Complete JUnit 5 test suite code for the Java service")


class TestGeneratorAgent(BaseAgent):
    """Generates JUnit 5 unit test suites derived directly from documented business rules."""
    __test__ = False

    def __init__(self, config_dir: str = "configs"):
        super().__init__("test_generator", config_dir=config_dir)

    def generate_chunk_tests(self, chunk: ChunkMetadata, doc: DocSection, code_obj: GeneratedCode) -> TestResult:
        """Generates JUnit 5 test suite for a single chunk."""
        self.logger.debug("Generating JUnit 5 tests for chunk %s", chunk.chunk_id)

        def mock_testgen() -> TestGenSchema:
            clean_name = chunk.name.upper()
            if chunk.language == "cobol":
                if "TIER" in clean_name or "2100" in clean_name:
                    java_tests = '''package com.modern.services;

import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import static org.junit.jupiter.api.Assertions.*;

class LoanTierSurchargeServiceTest {
    private final LoanTierSurchargeService service = new LoanTierSurchargeService();

    @Test
    void testTierASurchargeIsZero() {
        BigDecimal res = service.calculateTierSurcharge("A", new BigDecimal("10000.00"));
        assertEquals(new BigDecimal("0.00"), res);
    }

    @Test
    void testTierBSurchargeIsHalfPercent() {
        BigDecimal res = service.calculateTierSurcharge("B", new BigDecimal("10000.00"));
        assertEquals(new BigDecimal("50.00"), res);
    }

    @Test
    void testTierCSurchargeIsOneAndHalfPercent() {
        BigDecimal res = service.calculateTierSurcharge("C", new BigDecimal("10000.00"));
        assertEquals(new BigDecimal("150.00"), res);
    }

    @Test
    void testUnknownTierSurchargeIsThreePercent() {
        BigDecimal res = service.calculateTierSurcharge("D", new BigDecimal("10000.00"));
        assertEquals(new BigDecimal("300.00"), res);
    }

    @Test
    void testNullPrincipalReturnsZero() {
        BigDecimal res = service.calculateTierSurcharge("A", null);
        assertEquals(BigDecimal.ZERO, res);
    }
}
'''
                elif "INTEREST" in clean_name or "2200" in clean_name:
                    java_tests = '''package com.modern.services;

import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import static org.junit.jupiter.api.Assertions.*;

class LoanInterestServiceTest {
    private final LoanInterestService service = new LoanInterestService();

    @Test
    void testCalculateMonthlyInterest() {
        var res = service.calculateInterest(new BigDecimal("12000.00"), new BigDecimal("6.00"), BigDecimal.ZERO);
        assertEquals(new BigDecimal("60.00"), res.monthlyInterest());
    }

    @Test
    void testAccumulatePriorInterest() {
        var res = service.calculateInterest(new BigDecimal("10000.00"), new BigDecimal("12.00"), new BigDecimal("100.00"));
        assertEquals(new BigDecimal("200.00"), res.totalInterest());
    }

    @Test
    void testNullPriorTreatedAsZero() {
        var res = service.calculateInterest(new BigDecimal("10000.00"), new BigDecimal("12.00"), null);
        assertEquals(new BigDecimal("100.00"), res.monthlyInterest());
    }
}
'''
                elif "AMORTIZATION" in clean_name or "2300" in clean_name:
                    java_tests = '''package com.modern.services;

import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import static org.junit.jupiter.api.Assertions.*;

class LoanAmortizationServiceTest {
    private final LoanAmortizationService service = new LoanAmortizationService();

    @Test
    void testAmortizationZeroRate() {
        var res = service.computeAmortization(
                new BigDecimal("1200.00"), 12, BigDecimal.ZERO, BigDecimal.ZERO, BigDecimal.ZERO);
        assertEquals(new BigDecimal("100.00"), res.monthlyPayment());
        assertEquals(new BigDecimal("100.00"), res.principalPaid());
    }

    @Test
    void testInvalidTermThrows() {
        assertThrows(IllegalArgumentException.class, () ->
                service.computeAmortization(new BigDecimal("1000.00"), 0,
                        new BigDecimal("0.01"), new BigDecimal("10.00"), BigDecimal.ZERO));
    }
}
'''
                else:
                    class_name = "".join(w.capitalize() for w in re.sub(r"[^a-zA-Z0-9]", " ", chunk.name).split()) + "Service"
                    java_tests = f'''package com.modern.services;

import org.junit.jupiter.api.Test;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.*;

class {class_name}Test {{
    @Test
    void testExecution() {{
        var service = new {class_name}();
        var res = service.execute(Map.of());
        assertEquals("SUCCESS", res.get("status"));
    }}
}}
'''
            elif chunk.language == "vb":
                if "ValidateCustomer" in chunk.name:
                    java_tests = '''package com.modern.services;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class CustomerValidatorTest {
    private final CustomerValidator validator = new CustomerValidator();

    @Test
    void testValidPrimeCustomer() {
        var cust = new CustomerValidator.CustomerRecord(
                "CUST001", "Alice Smith", 35, 780, 100000.0, 20000.0, "alice@example.com", true);
        var res = validator.validateCustomer(cust);
        assertTrue(res.isValid());
        assertEquals("LOW_RISK_PRIME", res.riskCategory());
        assertEquals(450000.0, res.maxLoanEligibility(), 0.01);
        assertEquals(20.0, res.debtToIncomeRatio(), 0.01);
    }

    @Test
    void testUnderageCustomerRejected() {
        var cust = new CustomerValidator.CustomerRecord(
                "CUST002", "Minor User", 16, 700, 50000.0, 5000.0, "minor@example.com", true);
        var res = validator.validateCustomer(cust);
        assertFalse(res.isValid());
        assertTrue(res.errorMessages().contains("Customer age must be between 18 and 120."));
    }

    @Test
    void testInactiveCustomerRejected() {
        var cust = new CustomerValidator.CustomerRecord(
                "CUST003", "Inactive User", 30, 700, 60000.0, 10000.0, "user@example.com", false);
        var res = validator.validateCustomer(cust);
        assertFalse(res.isValid());
        assertTrue(res.errorMessages().contains("Inactive customer accounts cannot be processed for credit."));
    }

    @Test
    void testZeroIncomeRejected() {
        var cust = new CustomerValidator.CustomerRecord(
                "CUST004", "Zero Income", 25, 700, 0.0, 0.0, "zero@example.com", true);
        var res = validator.validateCustomer(cust);
        assertFalse(res.isValid());
        assertTrue(res.errorMessages().contains("Annual income must be strictly greater than zero."));
    }
}
'''
                elif "DetermineRiskCategory" in chunk.name:
                    java_tests = '''package com.modern.services;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class RiskCategoryServiceTest {
    @Test
    void testPrimeRisk() {
        assertEquals("LOW_RISK_PRIME", RiskCategoryService.determineRiskCategory(760, 30.0));
    }

    @Test
    void testStandardRisk() {
        assertEquals("MEDIUM_RISK_STANDARD", RiskCategoryService.determineRiskCategory(660, 40.0));
    }

    @Test
    void testSubprimeRisk() {
        assertEquals("HIGH_RISK_SUBPRIME", RiskCategoryService.determineRiskCategory(590, 48.0));
    }

    @Test
    void testIneligible() {
        assertEquals("INELIGIBLE", RiskCategoryService.determineRiskCategory(500, 60.0));
    }
}
'''
                elif "CalculateLoanLimit" in chunk.name:
                    java_tests = '''package com.modern.services;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class LoanLimitServiceTest {
    @Test
    void testPrimeLoanLimit() {
        assertEquals(450000.0, LoanLimitService.calculateLoanLimit(100000.0, "LOW_RISK_PRIME"), 0.01);
    }

    @Test
    void testStandardLoanLimit() {
        assertEquals(300000.0, LoanLimitService.calculateLoanLimit(100000.0, "MEDIUM_RISK_STANDARD"), 0.01);
    }

    @Test
    void testUnknownTierReturnsZero() {
        assertEquals(0.0, LoanLimitService.calculateLoanLimit(100000.0, "UNKNOWN"), 0.01);
    }
}
'''
                else:
                    class_name = "".join(w.capitalize() for w in re.sub(r"[^a-zA-Z0-9]", " ", chunk.name).split()) + "Service"
                    java_tests = f'''package com.modern.services;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class {class_name}Test {{
    @Test
    void testRun() {{
        assertTrue(true); // Smoke test — extend with specific assertions
    }}
}}
'''
            elif chunk.language == "java":
                if "processDeposit" in chunk.name:
                    java_tests = '''package com.modern.services;

import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import static org.junit.jupiter.api.Assertions.*;

class ModernDepositServiceTest {
    private final ModernDepositService service = new ModernDepositService();

    @Test
    void testProcessDepositSuccess() {
        var acc = new ModernDepositService.BankAccount("ACC001", new BigDecimal("500.00"));
        var tx = service.processDeposit(acc, "TX001", new BigDecimal("250.00"));
        assertTrue(tx.isApproved());
        assertEquals(new BigDecimal("750.00"), tx.resultingBalance());
        assertEquals(new BigDecimal("750.00"), acc.getCurrentBalance());
    }

    @Test
    void testProcessDepositNegativeRejected() {
        var acc = new ModernDepositService.BankAccount("ACC002", new BigDecimal("100.00"));
        var tx = service.processDeposit(acc, "TX002", new BigDecimal("-50.00"));
        assertFalse(tx.isApproved());
        assertEquals(new BigDecimal("100.00"), acc.getCurrentBalance());
    }

    @Test
    void testProcessDepositNullAmountRejected() {
        var acc = new ModernDepositService.BankAccount("ACC003", new BigDecimal("100.00"));
        var tx = service.processDeposit(acc, "TX003", null);
        assertFalse(tx.isApproved());
    }
}
'''
                elif "processWithdrawal" in chunk.name:
                    java_tests = '''package com.modern.services;

import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import static org.junit.jupiter.api.Assertions.*;

class ModernWithdrawalServiceTest {
    private final ModernWithdrawalService service = new ModernWithdrawalService();

    @Test
    void testWithdrawalSuccess() {
        var acc = new ModernWithdrawalService.BankAccount("ACC001", new BigDecimal("500.00"), false);
        var tx = service.processWithdrawal(acc, "TX001", new BigDecimal("200.00"));
        assertTrue(tx.isApproved());
        assertEquals(new BigDecimal("300.00"), tx.resultingBalance());
    }

    @Test
    void testWithdrawalOverdraftApproved() {
        var acc = new ModernWithdrawalService.BankAccount("ACC002", new BigDecimal("50.00"), true);
        var tx = service.processWithdrawal(acc, "TX002", new BigDecimal("100.00"));
        assertTrue(tx.isApproved());
        assertEquals(new BigDecimal("-85.00"), tx.resultingBalance());
    }

    @Test
    void testWithdrawalDailyLimitExceeded() {
        var acc = new ModernWithdrawalService.BankAccount("ACC003", new BigDecimal("5000.00"), false);
        var tx = service.processWithdrawal(acc, "TX003", new BigDecimal("3000.00"));
        assertFalse(tx.isApproved());
        assertTrue(tx.statusMessage().contains("daily withdrawal limit"));
    }

    @Test
    void testInsufficientFundsNoOverdraft() {
        var acc = new ModernWithdrawalService.BankAccount("ACC004", new BigDecimal("50.00"), false);
        var tx = service.processWithdrawal(acc, "TX004", new BigDecimal("200.00"));
        assertFalse(tx.isApproved());
        assertTrue(tx.statusMessage().contains("Insufficient funds"));
    }
}
'''
                else:
                    class_name = "".join(w.capitalize() for w in re.sub(r"[^a-zA-Z0-9]", " ", chunk.name).split()) + "Service"
                    java_tests = f'''package com.modern.services;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class {class_name}Test {{
    @Test
    void testOk() {{
        assertTrue(true); // Smoke test — extend with specific assertions
    }}
}}
'''
            else:
                java_tests = '''package com.modern.services;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class GenericServiceTest {
    @Test
    void testRun() {
        assertTrue(true);
    }
}
'''

            return TestGenSchema(java_test_code=java_tests.strip())

        user_prompt = TESTGEN_USER_PROMPT.format(
            chunk_id=chunk.chunk_id,
            business_rules="\n".join([f"- {r}" for r in doc.business_rules]),
            target_java_code=code_obj.target_java_code
        )

        res = self.invoke_structured(
            schema=TestGenSchema,
            system_prompt=TESTGEN_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            mock_fallback_generator=mock_testgen
        )

        self.logger.info("Generated JUnit 5 test suite for chunk %s", chunk.chunk_id)
        return TestResult(
            chunk_id=chunk.chunk_id,
            test_code="",               # Java-only mode: no pytest
            java_test_code=res.java_test_code,
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

        self.logger.info("Generating JUnit 5 test suites across %d chunks", len(target_chunks))
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
