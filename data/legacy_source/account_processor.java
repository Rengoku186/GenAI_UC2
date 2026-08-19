package com.legacybank.core.services;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * Legacy Account Transaction Processor.
 * Handles deposits, withdrawals, overdraft protection, and fee calculations.
 */
public class AccountProcessor {

    private static final BigDecimal OVERDRAFT_FEE = new BigDecimal("35.00");
    private static final BigDecimal DAILY_WITHDRAWAL_LIMIT = new BigDecimal("2500.00");
    private static final BigDecimal MINIMUM_BALANCE_MAINTENANCE = new BigDecimal("100.00");
    private static final BigDecimal LOW_BALANCE_PENALTY = new BigDecimal("12.00");

    public enum AccountType {
        CHECKING, SAVINGS, MONEY_MARKET
    }

    public static class TransactionRecord {
        private String transactionId;
        private String accountId;
        private String type; // "DEPOSIT" or "WITHDRAWAL"
        private BigDecimal amount;
        private BigDecimal resultingBalance;
        private LocalDateTime timestamp;
        private boolean isApproved;
        private String statusMessage;

        public TransactionRecord(String txId, String accId, String type, BigDecimal amount, 
                                 BigDecimal balance, boolean approved, String msg) {
            this.transactionId = txId;
            this.accountId = accId;
            this.type = type;
            this.amount = amount;
            this.resultingBalance = balance;
            this.timestamp = LocalDateTime.now();
            this.isApproved = approved;
            this.statusMessage = msg;
        }

        public String getTransactionId() { return transactionId; }
        public BigDecimal getResultingBalance() { return resultingBalance; }
        public boolean isApproved() { return isApproved; }
        public String getStatusMessage() { return statusMessage; }
    }

    public static class BankAccount {
        private String accountId;
        private AccountType accountType;
        private BigDecimal currentBalance;
        private boolean overdraftProtectionEnabled;
        private BigDecimal dailyWithdrawnAmount;
        private List<TransactionRecord> transactionHistory;

        public BankAccount(String accountId, AccountType accountType, BigDecimal initialBalance, boolean overdraftProtection) {
            this.accountId = accountId;
            this.accountType = accountType;
            this.currentBalance = initialBalance != null ? initialBalance : BigDecimal.ZERO;
            this.overdraftProtectionEnabled = overdraftProtection;
            this.dailyWithdrawnAmount = BigDecimal.ZERO;
            this.transactionHistory = new ArrayList<>();
        }

        public String getAccountId() { return accountId; }
        public AccountType getAccountType() { return accountType; }
        public BigDecimal getCurrentBalance() { return currentBalance; }
        public void setCurrentBalance(BigDecimal balance) { this.currentBalance = balance; }
        public boolean isOverdraftProtectionEnabled() { return overdraftProtectionEnabled; }
        public BigDecimal getDailyWithdrawnAmount() { return dailyWithdrawnAmount; }
        public void addDailyWithdrawnAmount(BigDecimal amount) { this.dailyWithdrawnAmount = this.dailyWithdrawnAmount.add(amount); }
        public List<TransactionRecord> getTransactionHistory() { return Collections.unmodifiableList(transactionHistory); }
        public void recordTransaction(TransactionRecord record) { this.transactionHistory.add(record); }
    }

    /**
     * Process a cash deposit into account.
     */
    public TransactionRecord processDeposit(BankAccount account, String txId, BigDecimal amount) {
        if (amount == null || amount.compareTo(BigDecimal.ZERO) <= 0) {
            TransactionRecord rejected = new TransactionRecord(txId, account.getAccountId(), "DEPOSIT", 
                    amount, account.getCurrentBalance(), false, "Deposit amount must be positive.");
            account.recordTransaction(rejected);
            return rejected;
        }

        BigDecimal newBalance = account.getCurrentBalance().add(amount).setScale(2, RoundingMode.HALF_UP);
        account.setCurrentBalance(newBalance);
        TransactionRecord success = new TransactionRecord(txId, account.getAccountId(), "DEPOSIT", 
                amount, newBalance, true, "Deposit completed successfully.");
        account.recordTransaction(success);
        return success;
    }

    /**
     * Process withdrawal with overdraft and daily limit checks.
     */
    public TransactionRecord processWithdrawal(BankAccount account, String txId, BigDecimal amount) {
        if (amount == null || amount.compareTo(BigDecimal.ZERO) <= 0) {
            TransactionRecord rejected = new TransactionRecord(txId, account.getAccountId(), "WITHDRAWAL", 
                    amount, account.getCurrentBalance(), false, "Withdrawal amount must be positive.");
            account.recordTransaction(rejected);
            return rejected;
        }

        // Daily limit check
        if (account.getDailyWithdrawnAmount().add(amount).compareTo(DAILY_WITHDRAWAL_LIMIT) > 0) {
            TransactionRecord rejected = new TransactionRecord(txId, account.getAccountId(), "WITHDRAWAL", 
                    amount, account.getCurrentBalance(), false, "Exceeded daily withdrawal limit.");
            account.recordTransaction(rejected);
            return rejected;
        }

        BigDecimal currentBal = account.getCurrentBalance();
        if (currentBal.compareTo(amount) >= 0) {
            BigDecimal newBalance = currentBal.subtract(amount).setScale(2, RoundingMode.HALF_UP);
            account.setCurrentBalance(newBalance);
            account.addDailyWithdrawnAmount(amount);
            
            // Check low balance maintenance penalty on checking
            if (account.getAccountType() == AccountType.CHECKING && newBalance.compareTo(MINIMUM_BALANCE_MAINTENANCE) < 0) {
                newBalance = newBalance.subtract(LOW_BALANCE_PENALTY);
                account.setCurrentBalance(newBalance);
            }

            TransactionRecord success = new TransactionRecord(txId, account.getAccountId(), "WITHDRAWAL", 
                    amount, newBalance, true, "Withdrawal approved.");
            account.recordTransaction(success);
            return success;
        } else if (account.isOverdraftProtectionEnabled()) {
            // Overdraft allowed with fee
            BigDecimal newBalance = currentBal.subtract(amount).subtract(OVERDRAFT_FEE).setScale(2, RoundingMode.HALF_UP);
            account.setCurrentBalance(newBalance);
            account.addDailyWithdrawnAmount(amount);
            
            TransactionRecord overdraftTx = new TransactionRecord(txId, account.getAccountId(), "WITHDRAWAL", 
                    amount, newBalance, true, "Overdraft approved with $35 fee applied.");
            account.recordTransaction(overdraftTx);
            return overdraftTx;
        } else {
            TransactionRecord rejected = new TransactionRecord(txId, account.getAccountId(), "WITHDRAWAL", 
                    amount, currentBal, false, "Insufficient funds and overdraft protection disabled.");
            account.recordTransaction(rejected);
            return rejected;
        }
    }
}
