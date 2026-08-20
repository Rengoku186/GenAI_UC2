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
                # ── Smart per-method Java stub derived from actual raw_code ──
                import re as _re
                raw    = chunk.raw_code.strip()
                cname  = "".join(w.capitalize() for w in _re.sub(r"[^a-zA-Z0-9]", " ", chunk.name).split())
                pkg    = "package com.modern.services;"
                name   = chunk.name

                # Try to extract the actual method/field declarations from raw source
                # and modernise them directly into the class body
                method_bodies: list[str] = []

                # Case 1: raw code contains a method/constructor signature
                method_match = _re.search(
                    r'((?:public|private|protected|static|final|synchronized|default)\s+)+'
                    r'([\w<>\[\],\s]+)\s+(' + _re.escape(name) + r')\s*\(([^)]*)\)\s*\{(.*?)\}',
                    raw, _re.DOTALL
                )
                if method_match:
                    # Use the raw implementation directly, wrapped in modern class
                    mod_sig = method_match.group(0).strip()
                    method_bodies.append(mod_sig)
                elif name.startswith("get"):
                    field = name[3:]
                    field_lc = field[0].lower() + field[1:]
                    ret_match = _re.search(r'return\s+([\w.]+)', raw)
                    ret_expr  = ret_match.group(1) if ret_match else field_lc
                    # Infer return type from raw code if available
                    type_match = _re.search(r'(?:public|private)\s+([\w<>\[\]]+)\s+get' + _re.escape(field), raw)
                    ret_type   = type_match.group(1) if type_match else "Object"
                    method_bodies.append(
                        f"    public {ret_type} {name}() {{ return {ret_expr}; }}"
                    )
                elif name.startswith("set"):
                    field    = name[3:]
                    field_lc = field[0].lower() + field[1:]
                    type_match = _re.search(r'(?:public|private)\s+void\s+set' + _re.escape(field) + r'\s*\(\s*([\w<>\[\]]+)', raw)
                    param_type = type_match.group(1) if type_match else "Object"
                    method_bodies.append(
                        f"    public void {name}({param_type} {field_lc}) {{ this.{field_lc} = {field_lc}; }}"
                    )
                elif name.startswith("is") or name.startswith("has"):
                    field    = name[2:]
                    field_lc = field[0].lower() + field[1:]
                    method_bodies.append(
                        f"    public boolean {name}() {{ return {field_lc}; }}"
                    )
                elif name.startswith("add") or name.startswith("record"):
                    type_match = _re.search(r'\(\s*([\w<>\[\]]+)\s+\w+\s*\)', raw)
                    param_type = type_match.group(1) if type_match else "Object"
                    field_lc   = name[3:4].lower() + name[4:] if len(name) > 3 else "value"
                    method_bodies.append(
                        f"    public void {name}({param_type} value) {{ this.{field_lc} = this.{field_lc} + value; }}"
                    )
                elif name == "main":
                    method_bodies.append(
                        f"    public static void main(String[] args) {{\n"
                        f"        System.out.println(\"{cname} — standalone demo entry point\");\n"
                        f"    }}"
                    )
                elif name == "HEADER":
                    # Header chunk: just package + imports, no class body methods needed
                    java_code = raw if raw else f"{pkg}\n"
                    return CodeGenSchema(
                        module_name=re.sub(r"[^a-zA-Z0-9_]", "_", chunk.name.lower()).strip("_"),
                        target_java_code=java_code.strip(),
                        java_class_name=cname
                    )
                else:
                    method_bodies.append(
                        f"    public void {name}() {{\n"
                        f"        // Modernized implementation of legacy {name}\n"
                        f"    }}"
                    )

                java_code = (
                    f"{pkg}\n\n"
                    f"/** Modernized Java 17+ class for legacy {chunk.name}. */\n"
                    f"public class {cname} {{\n\n"
                    + "\n\n".join(method_bodies) + "\n\n"
                    + "}"
                )
                return CodeGenSchema(
                    module_name=re.sub(r"[^a-zA-Z0-9_]", "_", chunk.name.lower()).strip("_"),
                    target_java_code=java_code.strip(),
                    java_class_name=cname
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