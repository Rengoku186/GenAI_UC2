"""Agent 8: Code Generator Agent (Modern Java 17+/21+ target only)."""

from __future__ import annotations
import re
from pydantic import BaseModel, Field
from src.agents.base_agent import BaseAgent
from src.orchestrator.state import PipelineState, GeneratedCode, ChunkMetadata, DocSection
from src.prompts.codegen_prompts import (
    CODEGEN_SYSTEM_PROMPT,
    CODEGEN_USER_PROMPT
)


class CodeGenSchema(BaseModel):
    module_name: str = Field(description="Suggested Java module/file stem name")
    target_java_code: str = Field(description="Modern Java 17+/21+ service implementation")
    java_class_name: str = Field(default="", description="Java class or record name")
    java_package: str = Field(default="com.modern.services", description="Java package name")


class CodeGeneratorAgent(BaseAgent):
    """Generates modern Java 17+/21+ services from refined documentation and legacy source chunks."""

    def __init__(self, config_dir: str = "configs"):
        super().__init__("code_generator", config_dir=config_dir)

    def generate_chunk_code(self, chunk: ChunkMetadata, doc: DocSection) -> GeneratedCode:
        """Generates modern Java 17+/21+ code for a single chunk."""
        self.logger.debug("Generating Java 17+ code for chunk %s (%s)", chunk.chunk_id, chunk.language)

        def mock_codegen() -> CodeGenSchema:
            clean_name = chunk.name.upper()
            if chunk.language == "cobol":
                if "TIER" in clean_name or "2100" in clean_name:
                    java_code = '''package com.modern.services;

import java.math.BigDecimal;
import java.math.RoundingMode;

/**
 * Loan tier surcharge calculator — modernized from COBOL CALCULATE-TIER-SURCHARGE paragraph.
 */
public class LoanTierSurchargeService {

    /**
     * Calculates the surcharge based on the customer credit tier.
     *
     * @param creditTier      Customer credit tier: A, B, C, or other.
     * @param principalAmount Loan principal amount.
     * @return Surcharge amount rounded to 2 decimal places.
     */
    public BigDecimal calculateTierSurcharge(String creditTier, BigDecimal principalAmount) {
        if (principalAmount == null) return BigDecimal.ZERO;
        String tier = (creditTier != null) ? creditTier.trim().toUpperCase() : "";

        return switch (tier) {
            case "A" -> BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);
            case "B" -> principalAmount.multiply(new BigDecimal("0.005")).setScale(2, RoundingMode.HALF_UP);
            case "C" -> principalAmount.multiply(new BigDecimal("0.015")).setScale(2, RoundingMode.HALF_UP);
            default -> principalAmount.multiply(new BigDecimal("0.030")).setScale(2, RoundingMode.HALF_UP);
        };
    }
}
'''
                    return CodeGenSchema(
                        module_name="loan_tier_surcharge",
                        target_java_code=java_code.strip(),
                        java_class_name="LoanTierSurchargeService"
                    )
                elif "INTEREST" in clean_name or "2200" in clean_name:
                    java_code = '''package com.modern.services;

import java.math.BigDecimal;
import java.math.RoundingMode;

/**
 * Loan interest calculator — modernized from COBOL CALCULATE-INTEREST paragraph.
 */
public class LoanInterestService {

    /** Result record containing computed interest values. */
    public record InterestResult(BigDecimal monthlyRate, BigDecimal monthlyInterest, BigDecimal totalInterest) {}

    /**
     * Calculates monthly interest rate and charge from annual percentage.
     *
     * @param principal     Loan principal amount.
     * @param annualRatePct Annual interest rate in percent (e.g. 6.0 for 6%).
     * @param priorTotal    Previously accumulated total interest.
     * @return InterestResult with monthly rate, monthly interest, and running total.
     */
    public InterestResult calculateInterest(BigDecimal principal, BigDecimal annualRatePct, BigDecimal priorTotal) {
        BigDecimal prior = priorTotal != null ? priorTotal : BigDecimal.ZERO;
        BigDecimal monthlyRate = annualRatePct.divide(new BigDecimal("1200.0"), 6, RoundingMode.HALF_UP);
        BigDecimal monthlyInterest = principal.multiply(monthlyRate).setScale(2, RoundingMode.HALF_UP);
        BigDecimal newTotal = prior.add(monthlyInterest);
        return new InterestResult(monthlyRate, monthlyInterest, newTotal);
    }
}
'''
                    return CodeGenSchema(
                        module_name="loan_interest_calculator",
                        target_java_code=java_code.strip(),
                        java_class_name="LoanInterestService"
                    )
                elif "AMORTIZATION" in clean_name or "2300" in clean_name:
                    java_code = '''package com.modern.services;

import java.math.BigDecimal;
import java.math.RoundingMode;

/**
 * Loan amortization service — modernized from COBOL COMPUTE-AMORTIZATION paragraph.
 */
public class LoanAmortizationService {

    /** Result record for amortization computation. */
    public record AmortizationResult(BigDecimal monthlyPayment, BigDecimal principalPaid, BigDecimal finalBalance) {}

    /**
     * Computes monthly payment, principal paid, and remaining balance.
     *
     * @param principal       Loan principal.
     * @param termMonths      Loan term in months (must be > 0).
     * @param monthlyRate     Monthly interest rate.
     * @param monthlyInterest Monthly interest amount.
     * @param tierSurcharge   Optional tier surcharge.
     * @return AmortizationResult.
     * @throws IllegalArgumentException if termMonths <= 0.
     */
    public AmortizationResult computeAmortization(BigDecimal principal, int termMonths,
            BigDecimal monthlyRate, BigDecimal monthlyInterest, BigDecimal tierSurcharge) {
        if (termMonths <= 0) throw new IllegalArgumentException("Loan term months must be > 0");

        BigDecimal surcharge = tierSurcharge != null ? tierSurcharge : BigDecimal.ZERO;
        BigDecimal monthlyPayment;

        if (monthlyRate.compareTo(BigDecimal.ZERO) > 0) {
            double r = monthlyRate.doubleValue();
            double p = principal.doubleValue();
            double pay = (p * r) / (1.0 - Math.pow(1.0 + r, -termMonths));
            monthlyPayment = BigDecimal.valueOf(pay).setScale(2, RoundingMode.HALF_UP);
        } else {
            monthlyPayment = principal.divide(BigDecimal.valueOf(termMonths), 2, RoundingMode.HALF_UP);
        }

        BigDecimal principalPaid = monthlyPayment.subtract(monthlyInterest).setScale(2, RoundingMode.HALF_UP);
        BigDecimal finalBalance = principal.subtract(principalPaid).add(surcharge).setScale(2, RoundingMode.HALF_UP);
        return new AmortizationResult(monthlyPayment, principalPaid, finalBalance);
    }
}
'''
                    return CodeGenSchema(
                        module_name="loan_amortization",
                        target_java_code=java_code.strip(),
                        java_class_name="LoanAmortizationService"
                    )
                else:
                    class_name = "".join(w.capitalize() for w in re.sub(r"[^a-zA-Z0-9]", " ", chunk.name).split()) + "Service"
                    java_code = f'''package com.modern.services;

import java.util.Map;
import java.util.HashMap;

/** Modernized service for COBOL block {chunk.name}. */
public class {class_name} {{
    public Map<String, Object> execute(Map<String, Object> context) {{
        Map<String, Object> ctx = context != null ? new HashMap<>(context) : new HashMap<>();
        ctx.put("status", "SUCCESS");
        ctx.put("processed", true);
        return ctx;
    }}
}}
'''
                    return CodeGenSchema(
                        module_name=re.sub(r"[^a-zA-Z0-9_]", "_", chunk.name.lower()).strip("_"),
                        target_java_code=java_code.strip(),
                        java_class_name=class_name
                    )

            elif chunk.language == "vb":
                if "ValidateCustomer" in chunk.name:
                    java_code = '''package com.modern.services;

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Pattern;

/**
 * Customer validator — modernized from VB ValidateCustomer routine.
 */
public class CustomerValidator {

    private static final Pattern EMAIL_PATTERN = Pattern.compile("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$");

    /** Immutable customer data record. */
    public record CustomerRecord(
            String customerId, String fullName, int age, int creditScore,
            double annualIncome, double totalDebt, String email, boolean isActive) {}

    /** Validation result record. */
    public record ValidationResult(
            boolean isValid, String riskCategory, double maxLoanEligibility,
            double debtToIncomeRatio, List<String> errorMessages) {}

    /**
     * Validates a customer record and determines loan eligibility.
     *
     * @param cust The customer record.
     * @return ValidationResult with risk category and eligibility.
     */
    public ValidationResult validateCustomer(CustomerRecord cust) {
        List<String> errors = new ArrayList<>();

        if (cust.age() < 18 || cust.age() > 120)
            errors.add("Customer age must be between 18 and 120.");
        if (cust.creditScore() < 300 || cust.creditScore() > 850)
            errors.add("Credit score is out of standard range (300-850).");
        if (cust.email() == null || !EMAIL_PATTERN.matcher(cust.email()).matches())
            errors.add("Invalid customer email address format.");

        double dti = cust.annualIncome() > 0
                ? Math.round((cust.totalDebt() / cust.annualIncome()) * 10000.0) / 100.0
                : 999.99;
        if (cust.annualIncome() <= 0)
            errors.add("Annual income must be strictly greater than zero.");
        if (!cust.isActive())
            errors.add("Inactive customer accounts cannot be processed for credit.");

        if (errors.isEmpty()) {
            String risk = determineRiskCategory(cust.creditScore(), dti);
            double limit = calculateLoanLimit(cust.annualIncome(), risk);
            return new ValidationResult(true, risk, limit, dti, List.of());
        }
        return new ValidationResult(false, "REJECTED", 0.0, dti, errors);
    }

    /** Determines risk category from credit score and DTI ratio. */
    public static String determineRiskCategory(int score, double dti) {
        if (score >= 750 && dti <= 35.0) return "LOW_RISK_PRIME";
        if (score >= 650 && dti <= 45.0) return "MEDIUM_RISK_STANDARD";
        if (score >= 580 && dti <= 50.0) return "HIGH_RISK_SUBPRIME";
        return "INELIGIBLE";
    }

    /** Calculates maximum loan eligibility based on income and risk tier. */
    public static double calculateLoanLimit(double income, String riskTier) {
        return switch (riskTier) {
            case "LOW_RISK_PRIME" -> Math.round(income * 4.5 * 100.0) / 100.0;
            case "MEDIUM_RISK_STANDARD" -> Math.round(income * 3.0 * 100.0) / 100.0;
            case "HIGH_RISK_SUBPRIME" -> Math.round(income * 1.5 * 100.0) / 100.0;
            default -> 0.0;
        };
    }
}
'''
                    return CodeGenSchema(
                        module_name="customer_validator",
                        target_java_code=java_code.strip(),
                        java_class_name="CustomerValidator"
                    )
                elif "DetermineRiskCategory" in chunk.name:
                    java_code = '''package com.modern.services;

/** Risk category determination — modernized from VB DetermineRiskCategory. */
public class RiskCategoryService {

    /**
     * Determines credit risk category from score and debt-to-income ratio.
     *
     * @param score Credit score (300–850).
     * @param dti   Debt-to-income ratio as percentage.
     * @return Risk tier string.
     */
    public static String determineRiskCategory(int score, double dti) {
        if (score >= 750 && dti <= 35.0) return "LOW_RISK_PRIME";
        if (score >= 650 && dti <= 45.0) return "MEDIUM_RISK_STANDARD";
        if (score >= 580 && dti <= 50.0) return "HIGH_RISK_SUBPRIME";
        return "INELIGIBLE";
    }
}
'''
                    return CodeGenSchema(
                        module_name="risk_category_service",
                        target_java_code=java_code.strip(),
                        java_class_name="RiskCategoryService"
                    )
                elif "CalculateLoanLimit" in chunk.name:
                    java_code = '''package com.modern.services;

/** Loan limit calculator — modernized from VB CalculateLoanLimit function. */
public class LoanLimitService {

    /**
     * Calculates maximum loan eligibility based on income and risk tier.
     *
     * @param income   Annual income.
     * @param riskTier Determined risk tier.
     * @return Maximum loan amount.
     */
    public static double calculateLoanLimit(double income, String riskTier) {
        return switch (riskTier) {
            case "LOW_RISK_PRIME" -> Math.round(income * 4.5 * 100.0) / 100.0;
            case "MEDIUM_RISK_STANDARD" -> Math.round(income * 3.0 * 100.0) / 100.0;
            case "HIGH_RISK_SUBPRIME" -> Math.round(income * 1.5 * 100.0) / 100.0;
            default -> 0.0;
        };
    }
}
'''
                    return CodeGenSchema(
                        module_name="loan_limit_service",
                        target_java_code=java_code.strip(),
                        java_class_name="LoanLimitService"
                    )
                else:
                    class_name = "".join(w.capitalize() for w in re.sub(r"[^a-zA-Z0-9]", " ", chunk.name).split()) + "Service"
                    java_code = f'''package com.modern.services;

import java.util.Map;

/** Modernized Java service for VB routine {chunk.name}. */
public class {class_name} {{
    public Map<String, String> execute() {{
        return Map.of("status", "SUCCESS", "routine", "{chunk.name}");
    }}
}}
'''
                    return CodeGenSchema(
                        module_name=re.sub(r"[^a-zA-Z0-9_]", "_", chunk.name.lower()).strip("_"),
                        target_java_code=java_code.strip(),
                        java_class_name=class_name
                    )

            elif chunk.language == "java":
                if "processDeposit" in chunk.name:
                    java_code = '''package com.modern.services;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.List;

/**
 * Deposit processing service — modernized from legacy Java AccountProcessor.processDeposit.
 */
public class ModernDepositService {

    /** Immutable transaction record. */
    public record TransactionRecord(
            String transactionId, String accountId, String type,
            BigDecimal amount, BigDecimal resultingBalance,
            boolean isApproved, String statusMessage) {}

    /** Mutable bank account aggregate. */
    public static class BankAccount {
        private final String accountId;
        private BigDecimal currentBalance;
        private final List<TransactionRecord> transactionHistory = new ArrayList<>();

        public BankAccount(String accountId, BigDecimal initialBalance) {
            this.accountId = accountId;
            this.currentBalance = initialBalance != null ? initialBalance : BigDecimal.ZERO;
        }

        public String getAccountId() { return accountId; }
        public BigDecimal getCurrentBalance() { return currentBalance; }
        public void setCurrentBalance(BigDecimal balance) { this.currentBalance = balance; }
        public List<TransactionRecord> getTransactionHistory() { return transactionHistory; }
    }

    /**
     * Processes a cash deposit into the bank account.
     *
     * @param account The bank account.
     * @param txId    Transaction identifier.
     * @param amount  Deposit amount (must be positive).
     * @return TransactionRecord with approval status and new balance.
     */
    public TransactionRecord processDeposit(BankAccount account, String txId, BigDecimal amount) {
        if (amount == null || amount.compareTo(BigDecimal.ZERO) <= 0) {
            TransactionRecord rejected = new TransactionRecord(
                    txId, account.getAccountId(), "DEPOSIT", amount,
                    account.getCurrentBalance(), false, "Deposit amount must be positive.");
            account.getTransactionHistory().add(rejected);
            return rejected;
        }

        BigDecimal newBal = account.getCurrentBalance().add(amount).setScale(2, RoundingMode.HALF_UP);
        account.setCurrentBalance(newBal);
        TransactionRecord success = new TransactionRecord(
                txId, account.getAccountId(), "DEPOSIT", amount,
                newBal, true, "Deposit completed successfully.");
        account.getTransactionHistory().add(success);
        return success;
    }
}
'''
                    return CodeGenSchema(
                        module_name="deposit_service",
                        target_java_code=java_code.strip(),
                        java_class_name="ModernDepositService"
                    )
                elif "processWithdrawal" in chunk.name:
                    java_code = '''package com.modern.services;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.List;

/**
 * Withdrawal processing service — modernized from legacy Java AccountProcessor.processWithdrawal.
 */
public class ModernWithdrawalService {

    private static final BigDecimal OVERDRAFT_FEE = new BigDecimal("35.00");
    private static final BigDecimal DAILY_WITHDRAWAL_LIMIT = new BigDecimal("2500.00");

    /** Immutable transaction record. */
    public record TransactionRecord(
            String transactionId, String accountId, String type,
            BigDecimal amount, BigDecimal resultingBalance,
            boolean isApproved, String statusMessage) {}

    /** Mutable bank account aggregate. */
    public static class BankAccount {
        private final String accountId;
        private BigDecimal currentBalance;
        private final boolean overdraftProtectionEnabled;
        private BigDecimal dailyWithdrawnAmount = BigDecimal.ZERO;
        private final List<TransactionRecord> transactionHistory = new ArrayList<>();

        public BankAccount(String accountId, BigDecimal initialBalance, boolean overdraftProtection) {
            this.accountId = accountId;
            this.currentBalance = initialBalance != null ? initialBalance : BigDecimal.ZERO;
            this.overdraftProtectionEnabled = overdraftProtection;
        }

        public String getAccountId() { return accountId; }
        public BigDecimal getCurrentBalance() { return currentBalance; }
        public void setCurrentBalance(BigDecimal balance) { this.currentBalance = balance; }
        public boolean isOverdraftProtectionEnabled() { return overdraftProtectionEnabled; }
        public BigDecimal getDailyWithdrawnAmount() { return dailyWithdrawnAmount; }
        public void addDailyWithdrawnAmount(BigDecimal amount) {
            this.dailyWithdrawnAmount = this.dailyWithdrawnAmount.add(amount);
        }
        public List<TransactionRecord> getTransactionHistory() { return transactionHistory; }
    }

    /**
     * Processes a cash withdrawal with overdraft protection and daily limit checks.
     *
     * @param account The bank account.
     * @param txId    Transaction identifier.
     * @param amount  Withdrawal amount (must be positive).
     * @return TransactionRecord with approval status and resulting balance.
     */
    public TransactionRecord processWithdrawal(BankAccount account, String txId, BigDecimal amount) {
        if (amount == null || amount.compareTo(BigDecimal.ZERO) <= 0) {
            TransactionRecord rejected = new TransactionRecord(
                    txId, account.getAccountId(), "WITHDRAWAL", amount,
                    account.getCurrentBalance(), false, "Withdrawal amount must be positive.");
            account.getTransactionHistory().add(rejected);
            return rejected;
        }

        if (account.getDailyWithdrawnAmount().add(amount).compareTo(DAILY_WITHDRAWAL_LIMIT) > 0) {
            TransactionRecord rejected = new TransactionRecord(
                    txId, account.getAccountId(), "WITHDRAWAL", amount,
                    account.getCurrentBalance(), false, "Exceeded daily withdrawal limit.");
            account.getTransactionHistory().add(rejected);
            return rejected;
        }

        if (account.getCurrentBalance().compareTo(amount) >= 0) {
            BigDecimal newBal = account.getCurrentBalance().subtract(amount).setScale(2, RoundingMode.HALF_UP);
            account.setCurrentBalance(newBal);
            account.addDailyWithdrawnAmount(amount);
            TransactionRecord success = new TransactionRecord(
                    txId, account.getAccountId(), "WITHDRAWAL", amount, newBal, true, "Withdrawal approved.");
            account.getTransactionHistory().add(success);
            return success;
        } else if (account.isOverdraftProtectionEnabled()) {
            BigDecimal newBal = account.getCurrentBalance().subtract(amount).subtract(OVERDRAFT_FEE)
                    .setScale(2, RoundingMode.HALF_UP);
            account.setCurrentBalance(newBal);
            account.addDailyWithdrawnAmount(amount);
            TransactionRecord success = new TransactionRecord(
                    txId, account.getAccountId(), "WITHDRAWAL", amount, newBal, true,
                    "Overdraft approved with $35 fee applied.");
            account.getTransactionHistory().add(success);
            return success;
        } else {
            TransactionRecord rejected = new TransactionRecord(
                    txId, account.getAccountId(), "WITHDRAWAL", amount,
                    account.getCurrentBalance(), false,
                    "Insufficient funds and overdraft protection disabled.");
            account.getTransactionHistory().add(rejected);
            return rejected;
        }
    }
}
'''
                    return CodeGenSchema(
                        module_name="withdrawal_service",
                        target_java_code=java_code.strip(),
                        java_class_name="ModernWithdrawalService"
                    )
                else:
                    class_name = "".join(w.capitalize() for w in re.sub(r"[^a-zA-Z0-9]", " ", chunk.name).split()) + "Service"
                    java_code = f'''package com.modern.services;

import java.util.Map;

/** Modernized Java 17+ service for legacy method {chunk.name}. */
public class {class_name} {{
    public Map<String, String> execute() {{
        return Map.of("status", "SUCCESS", "method", "{chunk.name}");
    }}
}}
'''
                    return CodeGenSchema(
                        module_name=re.sub(r"[^a-zA-Z0-9_]", "_", chunk.name.lower()).strip("_"),
                        target_java_code=java_code.strip(),
                        java_class_name=class_name
                    )

            # Generic fallback
            class_name = "GenericService"
            return CodeGenSchema(
                module_name="generic_service",
                target_java_code=f'package com.modern.services;\n/** Generic service for chunk {chunk.chunk_id}. */\npublic class {class_name} {{\n    public String execute() {{ return "{chunk.chunk_id}"; }}\n}}',
                java_class_name=class_name
            )

        user_prompt = CODEGEN_USER_PROMPT.format(
            language=chunk.language,
            chunk_id=chunk.chunk_id,
            name=chunk.name,
            purpose=doc.purpose,
            inputs=", ".join(doc.inputs),
            outputs=", ".join(doc.outputs),
            business_rules="\n".join([f"- {r}" for r in doc.business_rules]),
            control_flow=doc.control_flow,
            raw_code=chunk.raw_code
        )

        res = self.invoke_structured(
            schema=CodeGenSchema,
            system_prompt=CODEGEN_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            mock_fallback_generator=mock_codegen
        )

        self.logger.info("Generated Java 17+ code (%d lines) for chunk %s",
                         len(res.target_java_code.splitlines()), chunk.chunk_id)
        return GeneratedCode(
            chunk_id=chunk.chunk_id,
            target_code="",          # Java-only mode: no Python output
            module_name=res.module_name,
            imports=[],
            target_java_code=res.target_java_code,
            java_class_name=res.java_class_name,
            java_package=res.java_package,
            version=1
        )

    def execute(self, state: PipelineState) -> dict:
        chunks = {c.chunk_id: c for c in state.get("chunks", [])}
        docs = state.get("docs", {})
        generated = dict(state.get("generated_code", {}))

        target_chunk_id = state.get("current_chunk_id")
        if target_chunk_id and target_chunk_id in docs and target_chunk_id in chunks:
            target_chunks = [chunks[target_chunk_id]]
        else:
            target_chunks = [chunks[cid] for cid in docs if cid in chunks]

        self.logger.info("Generating modern Java 17+ code across %d chunks", len(target_chunks))
        for chunk in target_chunks:
            if chunk.chunk_id not in generated:
                doc = docs[chunk.chunk_id]
                code_obj = self.generate_chunk_code(chunk, doc)
                generated[chunk.chunk_id] = code_obj

        return {
            "generated_code": generated,
            "stage": "code_generation"
        }
