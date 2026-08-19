# Legacy System Documentation: Account Transaction Processor

- **Source File:** `account_processor.java`
- **Original Architecture:** Legacy Java Service (`com.legacybank.core.services.AccountProcessor`)
- **Target Modern Services:** Python 3.11+ (`account_processor.py`) & Java 17+ (`AccountProcessor.java`)
- **Automated Verification:** 100% Pytest & JUnit 5 Suite Passed

---

## 1. Executive Purpose & Business Domain
The `AccountProcessor` service processes banking cash flows (deposits, standard withdrawals, and overdraft protections) with automated fee assessment:
1. Validating positive transaction amounts.
2. Enforcing a **$2,500.00 daily cumulative withdrawal limit**.
3. Applying a **$35.00 overdraft fee** when balances are exceeded and overdraft protection is enabled.
4. Applying a **$12.00 low-balance maintenance penalty** on Checking accounts when resulting balances fall below **$100.00**.

---

## 2. Core Entities & Data Contracts

| Entity | Fields | Description |
| :--- | :--- | :--- |
| `BankAccount` | `accountId`, `accountType`, `currentBalance`, `overdraftProtectionEnabled`, `dailyWithdrawnAmount`, `transactionHistory` | Primary banking ledger entity |
| `TransactionRecord` | `transactionId`, `accountId`, `type`, `amount`, `resultingBalance`, `isApproved`, `statusMessage`, `timestamp` | Audit log event for deposits & withdrawals |

---

## 3. Algorithmic Business Rules & Policy

### Rule 1: Cash Deposits (`processDeposit`)
- Amount must be strictly $> \$0.00$.
- Balance is increased by amount scaled with `ROUND_HALF_UP` to 2 decimal places.

### Rule 2: Daily Withdrawal Ceiling (`processWithdrawal`)
$$	ext{Daily Withdrawn} + 	ext{Amount} \le \$2,500.00$$
- If exceeded, transaction is rejected with `"Exceeded daily withdrawal limit."`

### Rule 3: Standard Withdrawal & Checking Account Penalty
- If $	ext{Current Balance} \ge 	ext{Amount}$:
  - $	ext{New Balance} = 	ext{Current Balance} - 	ext{Amount}$
  - If $	ext{Account Type} == 	ext{CHECKING}$ and $	ext{New Balance} < \$100.00$:
    - Apply $\$12.00$ penalty: $	ext{New Balance} = 	ext{New Balance} - \$12.00$.

### Rule 4: Overdraft Protection
- If $	ext{Current Balance} < 	ext{Amount}$ and $	ext{overdraftProtectionEnabled} == 	ext{true}$:
  - Approve withdrawal with $\$35.00$ fee:
  $$	ext{New Balance} = 	ext{Current Balance} - 	ext{Amount} - \$35.00$$
- If $	ext{overdraftProtectionEnabled} == 	ext{false}$:
  - Reject transaction with `"Insufficient funds and overdraft protection disabled."`