"""Agent 5: Documenter Agent."""

from __future__ import annotations
from pydantic import BaseModel, Field
from src.agents.base_agent import BaseAgent
from src.orchestrator.state import PipelineState, DocSection, ChunkMetadata
from src.prompts.documenter_prompts import (
    DOCUMENTER_SYSTEM_PROMPT,
    DOCUMENTER_USER_PROMPT
)


class DocSectionSchema(BaseModel):
    purpose: str = Field(description="Summary of purpose and business intent")
    inputs: list[str] = Field(default_factory=list, description="Inputs, parameters, or fields consumed")
    outputs: list[str] = Field(default_factory=list, description="Outputs, return values, or modified fields")
    business_rules: list[str] = Field(default_factory=list, description="Explicit algorithmic rules, formulas, and conditions")
    control_flow: str = Field(description="Step-by-step control flow, branches, and error paths")


class DocumenterAgent(BaseAgent):
    """Generates structured, verifiable documentation for individual code chunks."""

    def __init__(self, config_dir: str = "configs"):
        super().__init__("documenter", config_dir=config_dir)

    def execute_chunk(self, chunk: ChunkMetadata, state: PipelineState) -> DocSection:
        """Generates documentation for a single chunk."""
        edges = state.get("dependency_graph", [])
        chunk_edges = [e for e in edges if e.source_chunk == chunk.chunk_id or e.target_chunk == chunk.chunk_id]
        dep_ctx = "\n".join([f"- {e.edge_type}: {e.source_chunk} -> {e.target_chunk} ({e.description})" for e in chunk_edges]) or "None"

        # Deterministic mock fallback generator for testing & offline mode
        def mock_doc() -> DocSectionSchema:
            if chunk.language == "cobol":
                if "TIER" in chunk.name or "2100" in chunk.name:
                    return DocSectionSchema(
                        purpose="Determines loan tier surcharge percentage based on applicant credit tier (A, B, C, or OTHER).",
                        inputs=["IN-CREDIT-TIER (char)", "IN-PRINCIPAL-AMT (numeric)"],
                        outputs=["WS-TIER-SURCHARGE (numeric)"],
                        business_rules=[
                            "Tier A: 0% surcharge ($0.00)",
                            "Tier B: 0.5% of principal amount (principal * 0.005)",
                            "Tier C: 1.5% of principal amount (principal * 0.015)",
                            "Other Tiers: 3.0% of principal amount (principal * 0.030)"
                        ],
                        control_flow="Evaluate IN-CREDIT-TIER and compute WS-TIER-SURCHARGE based on tiered rates."
                    )
                elif "INTEREST" in chunk.name or "2200" in chunk.name:
                    return DocSectionSchema(
                        purpose="Calculates monthly interest rate and single-period interest charge from annual rate.",
                        inputs=["IN-INTEREST-RATE (annual %)", "IN-PRINCIPAL-AMT (numeric)"],
                        outputs=["WS-MONTHLY-RATE (decimal)", "WS-MONTHLY-INTEREST (decimal)", "WS-TOTAL-INTEREST (accumulated)"],
                        business_rules=[
                            "Monthly interest rate = (Annual Interest Rate / 100.0) / 12.0",
                            "Monthly interest charge = Principal * Monthly Interest Rate",
                            "Total interest = Accumulated prior interest + Monthly interest charge"
                        ],
                        control_flow="Convert annual percentage to monthly factor, compute charge, and add to running total."
                    )
                elif "AMORTIZATION" in chunk.name or "2300" in chunk.name:
                    return DocSectionSchema(
                        purpose="Computes standard fixed-rate monthly amortization payment, principal deduction, and final balance.",
                        inputs=["IN-PRINCIPAL-AMT", "IN-TERM-MONTHS", "WS-MONTHLY-RATE", "WS-MONTHLY-INTEREST", "WS-TIER-SURCHARGE"],
                        outputs=["WS-MONTHLY-PAYMENT", "WS-PRINCIPAL-PAID", "WS-FINAL-BALANCE"],
                        business_rules=[
                            "Monthly Payment = (P * r) / (1 - (1 + r)^(-n)) when r > 0",
                            "Monthly Payment = P / n when r = 0 (zero interest loan)",
                            "Principal Paid = Monthly Payment - Monthly Interest",
                            "Final Balance = Principal - Principal Paid + Tier Surcharge"
                        ],
                        control_flow="Check if monthly rate is positive; calculate annuity payment; deduct interest; compute final balance."
                    )
            elif chunk.language == "vb":
                if "ValidateCustomer" in chunk.name:
                    return DocSectionSchema(
                        purpose="Validates customer credit profile, computes DTI ratio, and determines max loan eligibility.",
                        inputs=["CustomerRecord (Age, CreditScore, AnnualIncome, TotalDebt, Email, IsActive)"],
                        outputs=["ValidationResult (IsValid, RiskCategory, MaxLoanEligibility, DebtToIncomeRatio, ErrorMessages)"],
                        business_rules=[
                            "Age constraint: 18 <= Age <= 120",
                            "Credit score constraint: 300 <= CreditScore <= 850",
                            "Email regex format: ^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$",
                            "DTI calculation: (TotalDebt / AnnualIncome) * 100",
                            "Account must be active (IsActive == True)",
                            "Risk Tier Prime: Score >= 750 and DTI <= 35% -> Max Loan = Income * 4.5",
                            "Risk Tier Standard: Score >= 650 and DTI <= 45% -> Max Loan = Income * 3.0",
                            "Risk Tier Subprime: Score >= 580 and DTI <= 50% -> Max Loan = Income * 1.5",
                            "Other / Ineligible: Max Loan = 0.0"
                        ],
                        control_flow="Validate age, score, email, DTI; check active status; if no errors determine risk tier and loan limit; else reject."
                    )
            elif chunk.language == "java":
                if "processDeposit" in chunk.name:
                    return DocSectionSchema(
                        purpose="Processes deposit transaction into bank account, updating balance and appending audit trail.",
                        inputs=["BankAccount", "txId (String)", "amount (BigDecimal)"],
                        outputs=["TransactionRecord (isApproved, resultingBalance, statusMessage)"],
                        business_rules=[
                            "Deposit amount must be strictly greater than 0.00",
                            "New balance = Current balance + Deposit amount",
                            "Scale to 2 decimal places with HALF_UP rounding"
                        ],
                        control_flow="Verify positive amount; add to account balance; log approved transaction record."
                    )
                elif "processWithdrawal" in chunk.name:
                    return DocSectionSchema(
                        purpose="Processes withdrawal transaction with daily withdrawal limits, overdraft coverage, and low-balance fees.",
                        inputs=["BankAccount", "txId (String)", "amount (BigDecimal)"],
                        outputs=["TransactionRecord (isApproved, resultingBalance, statusMessage)"],
                        business_rules=[
                            "Withdrawal amount must be strictly greater than 0.00",
                            "Daily withdrawal accumulation limit = $2500.00 max",
                            "Standard withdrawal: allowed if Current Balance >= amount",
                            "Low balance maintenance penalty: if Checking and resulting balance < $100.00, apply $12.00 penalty",
                            "Overdraft: if Current Balance < amount and overdraftProtection is true, allow withdrawal and apply $35.00 fee",
                            "If overdraftProtection is false, reject transaction with Insufficient Funds"
                        ],
                        control_flow="Check amount > 0; check daily limit; if sufficient funds subtract amount and check checking penalty; else if overdraft enabled subtract amount and $35 fee; else reject."
                    )

            # Generic fallback
            return DocSectionSchema(
                purpose=f"Executes legacy logic for {chunk.name}.",
                inputs=["Context variables / parameters"],
                outputs=["Updated state or return value"],
                business_rules=[f"Maintains functional behavior of {chunk.name}"],
                control_flow=f"Sequential execution of statements in {chunk.name}."
            )

        user_prompt = DOCUMENTER_USER_PROMPT.format(
            language=chunk.language,
            chunk_id=chunk.chunk_id,
            name=chunk.name,
            chunk_type=chunk.chunk_type,
            source_file=chunk.source_file,
            line_start=chunk.line_start,
            line_end=chunk.line_end,
            dependency_context=dep_ctx,
            raw_code=chunk.raw_code
        )

        res = self.invoke_structured(
            schema=DocSectionSchema,
            system_prompt=DOCUMENTER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            mock_fallback_generator=mock_doc
        )

        return DocSection(
            chunk_id=chunk.chunk_id,
            purpose=res.purpose,
            inputs=res.inputs,
            outputs=res.outputs,
            business_rules=res.business_rules,
            control_flow=res.control_flow,
            version=1
        )

    def execute(self, state: PipelineState) -> dict:
        """Processes documentation for all chunks or current_chunk_id."""
        chunks = state.get("chunks", [])
        docs = dict(state.get("docs", {}))
        
        target_chunk_id = state.get("current_chunk_id")
        if target_chunk_id:
            target_chunks = [c for c in chunks if c.chunk_id == target_chunk_id]
        else:
            target_chunks = chunks

        for chunk in target_chunks:
            if chunk.chunk_id not in docs:
                doc = self.execute_chunk(chunk, state)
                docs[chunk.chunk_id] = doc

        return {
            "docs": docs,
            "stage": "documentation"
        }
