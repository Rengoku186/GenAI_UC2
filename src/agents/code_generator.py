"""Agent 8: Code Generator Agent."""

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
    module_name: str = Field(description="Suggested Python module or file name")
    imports: list[str] = Field(default_factory=list, description="Required Python imports")
    target_code: str = Field(description="Modern, idiomatic, fully runnable Python code")


class CodeGeneratorAgent(BaseAgent):
    """Generates modern Python services from refined documentation and legacy source chunks."""

    def __init__(self, config_dir: str = "configs"):
        super().__init__("code_generator", config_dir=config_dir)

    def generate_chunk_code(self, chunk: ChunkMetadata, doc: DocSection) -> GeneratedCode:
        """Generates modern Python code for a single chunk."""
        def mock_codegen() -> CodeGenSchema:
            clean_name = chunk.name.upper()
            if chunk.language == "cobol":
                if "TIER" in clean_name or "2100" in clean_name:
                    code = '''from decimal import Decimal, ROUND_HALF_UP

def calculate_tier_surcharge(credit_tier: str, principal_amount: Decimal) -> Decimal:
    """Calculates loan tier surcharge based on customer credit tier."""
    tier = (credit_tier or "").strip().upper()
    if tier == "A":
        return Decimal("0.00")
    elif tier == "B":
        return (principal_amount * Decimal("0.005")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    elif tier == "C":
        return (principal_amount * Decimal("0.015")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    else:
        return (principal_amount * Decimal("0.030")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
'''
                    return CodeGenSchema(
                        module_name="loan_tier_surcharge",
                        imports=["from decimal import Decimal, ROUND_HALF_UP"],
                        target_code=code.strip()
                    )
                elif "INTEREST" in clean_name or "2200" in clean_name:
                    code = '''from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass

@dataclass
class InterestCalculationResult:
    monthly_rate: Decimal
    monthly_interest: Decimal
    total_interest: Decimal

def calculate_interest(
    principal_amount: Decimal, 
    annual_interest_rate_pct: Decimal, 
    prior_total_interest: Decimal = Decimal("0.00")
) -> InterestCalculationResult:
    """Calculates monthly interest rate and charge from annual percentage."""
    monthly_rate = (annual_interest_rate_pct / Decimal("100.0")) / Decimal("12.0")
    monthly_interest = (principal_amount * monthly_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    new_total = prior_total_interest + monthly_interest
    return InterestCalculationResult(
        monthly_rate=monthly_rate,
        monthly_interest=monthly_interest,
        total_interest=new_total
    )
'''
                    return CodeGenSchema(
                        module_name="loan_interest_calculator",
                        imports=["from decimal import Decimal, ROUND_HALF_UP", "from dataclasses import dataclass"],
                        target_code=code.strip()
                    )
                elif "AMORTIZATION" in clean_name or "2300" in clean_name:
                    code = '''from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass

@dataclass
class AmortizationResult:
    monthly_payment: Decimal
    principal_paid: Decimal
    final_balance: Decimal

def compute_amortization(
    principal_amt: Decimal,
    term_months: int,
    monthly_rate: Decimal,
    monthly_interest: Decimal,
    tier_surcharge: Decimal = Decimal("0.00")
) -> AmortizationResult:
    """Computes monthly annuity payment, principal deduction, and remaining balance."""
    if term_months <= 0:
        raise ValueError("Loan term months must be greater than 0")
    
    if monthly_rate > Decimal("0"):
        r = float(monthly_rate)
        p = float(principal_amt)
        n = int(term_months)
        payment_float = (p * r) / (1.0 - (1.0 + r) ** (-n))
        monthly_payment = Decimal(str(payment_float)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    else:
        monthly_payment = (principal_amt / Decimal(term_months)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    principal_paid = (monthly_payment - monthly_interest).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    final_balance = (principal_amt - principal_paid + tier_surcharge).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return AmortizationResult(
        monthly_payment=monthly_payment,
        principal_paid=principal_paid,
        final_balance=final_balance
    )
'''
                    return CodeGenSchema(
                        module_name="loan_amortization",
                        imports=["from decimal import Decimal, ROUND_HALF_UP", "from dataclasses import dataclass"],
                        target_code=code.strip()
                    )
                else:
                    func_name = re.sub(r"[^a-zA-Z0-9_]", "_", chunk.name.lower()).strip("_")
                    code = f'''from typing import Dict, Any

def execute_{func_name}(context: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Modernized service routine for COBOL block {chunk.name}."""
    ctx = dict(context) if context else {{}}
    ctx["status"] = "SUCCESS"
    ctx["processed_{func_name}"] = True
    return ctx
'''
                    return CodeGenSchema(
                        module_name=func_name,
                        imports=["from typing import Dict, Any"],
                        target_code=code.strip()
                    )
            elif chunk.language == "vb":
                if "ValidateCustomer" in chunk.name:
                    code = '''import re
from dataclasses import dataclass, field
from typing import List

@dataclass
class CustomerRecord:
    customer_id: str
    full_name: str
    age: int
    credit_score: int
    annual_income: float
    total_debt: float
    email: str
    is_active: bool = True

@dataclass
class ValidationResult:
    is_valid: bool
    risk_category: str
    max_loan_eligibility: float
    debt_to_income_ratio: float
    error_messages: List[str] = field(default_factory=list)

class CustomerValidator:
    MIN_AGE: int = 18
    MAX_AGE: int = 120
    MIN_CREDIT_SCORE: int = 300
    MAX_CREDIT_SCORE: int = 850
    EMAIL_PATTERN: re.Pattern = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    def validate_customer(self, cust: CustomerRecord) -> ValidationResult:
        errors: List[str] = []

        if cust.age < self.MIN_AGE or cust.age > self.MAX_AGE:
            errors.append("Customer age must be between 18 and 120.")

        if cust.credit_score < self.MIN_CREDIT_SCORE or cust.credit_score > self.MAX_CREDIT_SCORE:
            errors.append("Credit score is out of standard range (300-850).")

        if not cust.email or not self.EMAIL_PATTERN.match(cust.email):
            errors.append("Invalid customer email address format.")

        if cust.annual_income > 0:
            dti = round((cust.total_debt / cust.annual_income) * 100.0, 2)
        else:
            dti = 999.99
            errors.append("Annual income must be strictly greater than zero.")

        if not cust.is_active:
            errors.append("Inactive customer accounts cannot be processed for credit.")

        if not errors:
            risk_category = self.determine_risk_category(cust.credit_score, dti)
            loan_limit = self.calculate_loan_limit(cust.annual_income, risk_category)
            return ValidationResult(
                is_valid=True,
                risk_category=risk_category,
                max_loan_eligibility=loan_limit,
                debt_to_income_ratio=dti,
                error_messages=[]
            )
        else:
            return ValidationResult(
                is_valid=False,
                risk_category="REJECTED",
                max_loan_eligibility=0.0,
                debt_to_income_ratio=dti,
                error_messages=errors
            )

    @staticmethod
    def determine_risk_category(score: int, dti: float) -> str:
        if score >= 750 and dti <= 35.0:
            return "LOW_RISK_PRIME"
        elif score >= 650 and dti <= 45.0:
            return "MEDIUM_RISK_STANDARD"
        elif score >= 580 and dti <= 50.0:
            return "HIGH_RISK_SUBPRIME"
        return "INELIGIBLE"

    @staticmethod
    def calculate_loan_limit(income: float, risk_tier: str) -> float:
        multipliers = {
            "LOW_RISK_PRIME": 4.5,
            "MEDIUM_RISK_STANDARD": 3.0,
            "HIGH_RISK_SUBPRIME": 1.5
        }
        return round(income * multipliers.get(risk_tier, 0.0), 2)
'''
                    return CodeGenSchema(
                        module_name="customer_validator",
                        imports=["import re", "from dataclasses import dataclass, field", "from typing import List"],
                        target_code=code.strip()
                    )
                elif "DetermineRiskCategory" in chunk.name:
                    code = '''def determine_risk_category(score: int, dti: float) -> str:
    """Evaluates customer credit tier from score and DTI."""
    if score >= 750 and dti <= 35.0:
        return "LOW_RISK_PRIME"
    elif score >= 650 and dti <= 45.0:
        return "MEDIUM_RISK_STANDARD"
    elif score >= 580 and dti <= 50.0:
        return "HIGH_RISK_SUBPRIME"
    return "INELIGIBLE"
'''
                    return CodeGenSchema(
                        module_name="risk_category",
                        imports=[],
                        target_code=code.strip()
                    )
                elif "CalculateLoanLimit" in chunk.name:
                    code = '''def calculate_loan_limit(income: float, risk_tier: str) -> float:
    """Calculates max loan eligibility multiplier based on risk tier."""
    multipliers = {
        "LOW_RISK_PRIME": 4.5,
        "MEDIUM_RISK_STANDARD": 3.0,
        "HIGH_RISK_SUBPRIME": 1.5
    }
    return round(income * multipliers.get(risk_tier, 0.0), 2)
'''
                    return CodeGenSchema(
                        module_name="loan_limit",
                        imports=[],
                        target_code=code.strip()
                    )
                else:
                    func_name = re.sub(r"[^a-zA-Z0-9_]", "_", chunk.name.lower()).strip("_")
                    code = f'''def execute_{func_name}(*args, **kwargs) -> dict:
    """Modernized VB routine for {chunk.name}."""
    return {{"status": "SUCCESS", "routine": "{chunk.name}"}}
'''
                    return CodeGenSchema(
                        module_name=func_name,
                        imports=[],
                        target_code=code.strip()
                    )
            elif chunk.language == "java":
                if "processDeposit" in chunk.name:
                    code = '''from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass, field
from typing import List

@dataclass
class TransactionRecord:
    transaction_id: str
    account_id: str
    type: str
    amount: Decimal
    resulting_balance: Decimal
    is_approved: bool
    status_message: str

@dataclass
class BankAccount:
    account_id: str
    current_balance: Decimal = Decimal("0.00")
    transaction_history: List[TransactionRecord] = field(default_factory=list)

def process_deposit(account: BankAccount, tx_id: str, amount: Decimal) -> TransactionRecord:
    """Processes cash deposit into bank account."""
    if amount is None or amount <= Decimal("0.00"):
        rec = TransactionRecord(
            transaction_id=tx_id,
            account_id=account.account_id,
            type="DEPOSIT",
            amount=amount if amount else Decimal("0.00"),
            resulting_balance=account.current_balance,
            is_approved=False,
            status_message="Deposit amount must be positive."
        )
        account.transaction_history.append(rec)
        return rec

    new_bal = (account.current_balance + amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    account.current_balance = new_bal
    rec = TransactionRecord(
        transaction_id=tx_id,
        account_id=account.account_id,
        type="DEPOSIT",
        amount=amount,
        resulting_balance=new_bal,
        is_approved=True,
        status_message="Deposit completed successfully."
    )
    account.transaction_history.append(rec)
    return rec
'''
                    return CodeGenSchema(
                        module_name="deposit_service",
                        imports=["from decimal import Decimal, ROUND_HALF_UP", "from dataclasses import dataclass, field"],
                        target_code=code.strip()
                    )
                elif "processWithdrawal" in chunk.name:
                    code = '''from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from dataclasses import dataclass, field
from typing import List

class AccountType(Enum):
    CHECKING = "CHECKING"
    SAVINGS = "SAVINGS"

@dataclass
class TransactionRecord:
    transaction_id: str
    account_id: str
    type: str
    amount: Decimal
    resulting_balance: Decimal
    is_approved: bool
    status_message: str

@dataclass
class BankAccount:
    account_id: str
    account_type: AccountType = AccountType.CHECKING
    current_balance: Decimal = Decimal("0.00")
    overdraft_protection_enabled: bool = False
    daily_withdrawn_amount: Decimal = Decimal("0.00")
    transaction_history: List[TransactionRecord] = field(default_factory=list)

OVERDRAFT_FEE = Decimal("35.00")
DAILY_WITHDRAWAL_LIMIT = Decimal("2500.00")

def process_withdrawal(account: BankAccount, tx_id: str, amount: Decimal) -> TransactionRecord:
    """Processes cash withdrawal with overdraft protection check."""
    if amount is None or amount <= Decimal("0.00"):
        rec = TransactionRecord(
            transaction_id=tx_id,
            account_id=account.account_id,
            type="WITHDRAWAL",
            amount=amount if amount else Decimal("0.00"),
            resulting_balance=account.current_balance,
            is_approved=False,
            status_message="Withdrawal amount must be positive."
        )
        account.transaction_history.append(rec)
        return rec

    if account.daily_withdrawn_amount + amount > DAILY_WITHDRAWAL_LIMIT:
        rec = TransactionRecord(
            transaction_id=tx_id,
            account_id=account.account_id,
            type="WITHDRAWAL",
            amount=amount,
            resulting_balance=account.current_balance,
            is_approved=False,
            status_message="Exceeded daily withdrawal limit."
        )
        account.transaction_history.append(rec)
        return rec

    if account.current_balance >= amount:
        new_bal = (account.current_balance - amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        account.current_balance = new_bal
        account.daily_withdrawn_amount += amount
        rec = TransactionRecord(
            transaction_id=tx_id,
            account_id=account.account_id,
            type="WITHDRAWAL",
            amount=amount,
            resulting_balance=new_bal,
            is_approved=True,
            status_message="Withdrawal approved."
        )
        account.transaction_history.append(rec)
        return rec
    elif account.overdraft_protection_enabled:
        new_bal = (account.current_balance - amount - OVERDRAFT_FEE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        account.current_balance = new_bal
        account.daily_withdrawn_amount += amount
        rec = TransactionRecord(
            transaction_id=tx_id,
            account_id=account.account_id,
            type="WITHDRAWAL",
            amount=amount,
            resulting_balance=new_bal,
            is_approved=True,
            status_message="Overdraft approved with $35 fee applied."
        )
        account.transaction_history.append(rec)
        return rec
    else:
        rec = TransactionRecord(
            transaction_id=tx_id,
            account_id=account.account_id,
            type="WITHDRAWAL",
            amount=amount,
            resulting_balance=account.current_balance,
            is_approved=False,
            status_message="Insufficient funds and overdraft protection disabled."
        )
        account.transaction_history.append(rec)
        return rec
'''
                    return CodeGenSchema(
                        module_name="withdrawal_service",
                        imports=["from decimal import Decimal, ROUND_HALF_UP", "from enum import Enum", "from dataclasses import dataclass, field"],
                        target_code=code.strip()
                    )
                else:
                    func_name = re.sub(r"[^a-zA-Z0-9_]", "_", chunk.name.lower()).strip("_")
                    code = f'''def execute_{func_name}(*args, **kwargs) -> dict:
    """Modernized Java method service for {chunk.name}."""
    return {{"status": "SUCCESS", "method": "{chunk.name}"}}
'''
                    return CodeGenSchema(
                        module_name=func_name,
                        imports=[],
                        target_code=code.strip()
                    )

            # Generic fallback
            gen_code = f'''def execute_service(context=None) -> dict:
    """Generic Python modernization stub."""
    return {{"status": "SUCCESS", "chunk": "{chunk.chunk_id}"}}
'''
            return CodeGenSchema(
                module_name="generic_service",
                imports=[],
                target_code=gen_code.strip()
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

        return GeneratedCode(
            chunk_id=chunk.chunk_id,
            target_code=res.target_code,
            module_name=res.module_name,
            imports=res.imports,
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

        for chunk in target_chunks:
            if chunk.chunk_id not in generated:
                doc = docs[chunk.chunk_id]
                code_obj = self.generate_chunk_code(chunk, doc)
                generated[chunk.chunk_id] = code_obj

        return {
            "generated_code": generated,
            "stage": "code_generation"
        }
