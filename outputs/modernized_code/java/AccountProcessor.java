package com.modern.services;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * Modernized Account Processor Service (Java 17+/21+).
 * Clean rewrite of legacy AccountProcessor.
 */
public class AccountProcessor {

    private static final BigDecimal OVERDRAFT_FEE = new BigDecimal("35.00");
    private static final BigDecimal DAILY_WITHDRAWAL_LIMIT = new BigDecimal("2500.00");
    private static final BigDecimal MINIMUM_BALANCE_MAINTENANCE = new BigDecimal("100.00");
    private static final BigDecimal LOW_BALANCE_PENALTY = new BigDecimal("12.00");

    public enum AccountType {
        CHECKING, SAVINGS, MONEY_MARKET
    }

    public record TransactionRecord(
        String transactionId,
        String accountId,
        String type,
        BigDecimal amount,
        BigDecimal resultingBalance,
        boolean isApproved,
        String statusMessage,
        LocalDateTime timestamp
    ) {
        public TransactionRecord(String txId, String accId, String type, BigDecimal amount, BigDecimal balance, boolean approved, String msg) {
            this(txId, accId, type, amount, balance, approved, msg, LocalDateTime.now());
        }
    }

    public static class BankAccount {
        private final String accountId;
        private final AccountType accountType;
        private BigDecimal currentBalance;
        private final boolean overdraftProtectionEnabled;
        private BigDecimal dailyWithdrawnAmount = BigDecimal.ZERO;
        private final List<TransactionRecord> transactionHistory = new ArrayList<>();

        public BankAccount(String accountId, AccountType accountType, BigDecimal initialBalance, boolean overdraftProtection) {
            this.accountId = accountId;
            this.accountType = accountType;
            this.currentBalance = initialBalance != null ? initialBalance : BigDecimal.ZERO;
            this.overdraftProtectionEnabled = overdraftProtection;
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

    public TransactionRecord processDeposit(BankAccount account, String txId, BigDecimal amount) {
        if (amount == null || amount.compareTo(BigDecimal.ZERO) <= 0) {
            TransactionRecord rejected = new TransactionRecord(txId, account.getAccountId(), "DEPOSIT", amount, account.getCurrentBalance(), false, "Deposit amount must be positive.");
            account.recordTransaction(rejected);
            return rejected;
        }

        BigDecimal newBalance = account.getCurrentBalance().add(amount).setScale(2, RoundingMode.HALF_UP);
        account.setCurrentBalance(newBalance);
        TransactionRecord success = new TransactionRecord(txId, account.getAccountId(), "DEPOSIT", amount, newBalance, true, "Deposit completed successfully.");
        account.recordTransaction(success);
        return success;
    }

    public TransactionRecord processWithdrawal(BankAccount account, String txId, BigDecimal amount) {
        if (amount == null || amount.compareTo(BigDecimal.ZERO) <= 0) {
            TransactionRecord rejected = new TransactionRecord(txId, account.getAccountId(), "WITHDRAWAL", amount, account.getCurrentBalance(), false, "Withdrawal amount must be positive.");
            account.recordTransaction(rejected);
            return rejected;
        }

        if (account.getDailyWithdrawnAmount().add(amount).compareTo(DAILY_WITHDRAWAL_LIMIT) > 0) {
            TransactionRecord rejected = new TransactionRecord(txId, account.getAccountId(), "WITHDRAWAL", amount, account.getCurrentBalance(), false, "Exceeded daily withdrawal limit.");
            account.recordTransaction(rejected);
            return rejected;
        }

        BigDecimal currentBal = account.getCurrentBalance();
        if (currentBal.compareTo(amount) >= 0) {
            BigDecimal newBalance = currentBal.subtract(amount).setScale(2, RoundingMode.HALF_UP);
            account.setCurrentBalance(newBalance);
            account.addDailyWithdrawnAmount(amount);

            if (account.getAccountType() == AccountType.CHECKING && newBalance.compareTo(MINIMUM_BALANCE_MAINTENANCE) < 0) {
                newBalance = newBalance.subtract(LOW_BALANCE_PENALTY);
                account.setCurrentBalance(newBalance);
            }

            TransactionRecord success = new TransactionRecord(txId, account.getAccountId(), "WITHDRAWAL", amount, newBalance, true, "Withdrawal approved.");
            account.recordTransaction(success);
            return success;
        } else if (account.isOverdraftProtectionEnabled()) {
            BigDecimal newBalance = currentBal.subtract(amount).subtract(OVERDRAFT_FEE).setScale(2, RoundingMode.HALF_UP);
            account.setCurrentBalance(newBalance);
            account.addDailyWithdrawnAmount(amount);

            TransactionRecord success = new TransactionRecord(txId, account.getAccountId(), "WITHDRAWAL", amount, newBalance, true, "Overdraft approved with $35 fee applied.");
            account.recordTransaction(success);
            return success;
        } else {
            TransactionRecord rejected = new TransactionRecord(txId, account.getAccountId(), "WITHDRAWAL", amount, currentBal, false, "Insufficient funds and overdraft protection disabled.");
            account.recordTransaction(rejected);
            return rejected;
        }
    }
}