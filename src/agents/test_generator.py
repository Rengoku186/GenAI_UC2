"""Agent 11: Test Generator Agent (JUnit 5 for Java - Java-only mode)."""

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
        assertTrue(true); // Smoke test - extend with specific assertions
    }}
}}
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