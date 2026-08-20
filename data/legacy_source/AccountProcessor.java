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
        private String type;
        private BigDecimal amount;
        private BigDecimal resultingBalance;
        private LocalDateTime timestamp;
        private boolean isApproved;
        private String statusMessage;

        public TransactionRecord(
                String txId,
                String accId,
                String type,
                BigDecimal amount,
                BigDecimal balance,
                boolean approved,
                String msg) {

            this.transactionId = txId;
            this.accountId = accId;
            this.type = type;
            this.amount = amount;
            this.resultingBalance = balance;
            this.timestamp = LocalDateTime.now();
            this.isApproved = approved;
            this.statusMessage = msg;
        }

        public String getTransactionId() {
            return transactionId;
        }

        public BigDecimal getResultingBalance() {
            return resultingBalance;
        }

        public boolean isApproved() {
            return isApproved;
        }

        public String getStatusMessage() {
            return statusMessage;
        }

        public String getAccountId() {
            return accountId;
        }

        public String getType() {
            return type;
        }

        public BigDecimal getAmount() {
            return amount;
        }

        public LocalDateTime getTimestamp() {
            return timestamp;
        }
    }

    public static class BankAccount {
        private String accountId;
        private AccountType accountType;
        private BigDecimal currentBalance;
        private boolean overdraftProtectionEnabled;
        private BigDecimal dailyWithdrawnAmount;
        private List<TransactionRecord> transactionHistory;

        public BankAccount(
                String accountId,
                AccountType accountType,
                BigDecimal initialBalance,
                boolean overdraftProtection) {

            this.accountId = accountId;
            this.accountType = accountType;
            this.currentBalance =
                    initialBalance != null
                            ? initialBalance
                            : BigDecimal.ZERO;

            this.overdraftProtectionEnabled = overdraftProtection;
            this.dailyWithdrawnAmount = BigDecimal.ZERO;
            this.transactionHistory = new ArrayList<>();
        }

        public String getAccountId() {
            return accountId;
        }

        public AccountType getAccountType() {
            return accountType;
        }

        public BigDecimal getCurrentBalance() {
            return currentBalance;
        }

        public void setCurrentBalance(BigDecimal balance) {
            this.currentBalance = balance;
        }

        public boolean isOverdraftProtectionEnabled() {
            return overdraftProtectionEnabled;
        }

        public BigDecimal getDailyWithdrawnAmount() {
            return dailyWithdrawnAmount;
        }

        public void addDailyWithdrawnAmount(BigDecimal amount) {
            this.dailyWithdrawnAmount =
                    this.dailyWithdrawnAmount.add(amount);
        }

        public List<TransactionRecord> getTransactionHistory() {
            return Collections.unmodifiableList(transactionHistory);
        }

        public void recordTransaction(TransactionRecord record) {
            this.transactionHistory.add(record);
        }
    }

    /**
     * Process a cash deposit into account.
     */
    public TransactionRecord processDeposit(BankAccount account, String txId, BigDecimal amount) {

        if (amount == null ||
                amount.compareTo(BigDecimal.ZERO) <= 0) {

            TransactionRecord rejected =
                    new TransactionRecord(
                            txId,
                            account.getAccountId(),
                            "DEPOSIT",
                            amount,
                            account.getCurrentBalance(),
                            false,
                            "Deposit amount must be positive.");

            account.recordTransaction(rejected);
            return rejected;
        }

        BigDecimal newBalance =
                account.getCurrentBalance()
                        .add(amount)
                        .setScale(2, RoundingMode.HALF_UP);

        account.setCurrentBalance(newBalance);

        TransactionRecord success =
                new TransactionRecord(
                        txId,
                        account.getAccountId(),
                        "DEPOSIT",
                        amount,
                        newBalance,
                        true,
                        "Deposit completed successfully.");

        account.recordTransaction(success);

        return success;
    }

    /**
     * Process withdrawal with overdraft and daily limit checks.
     */
    public TransactionRecord processWithdrawal(BankAccount account, String txId, BigDecimal amount) {

        if (amount == null ||
                amount.compareTo(BigDecimal.ZERO) <= 0) {

            TransactionRecord rejected =
                    new TransactionRecord(
                            txId,
                            account.getAccountId(),
                            "WITHDRAWAL",
                            amount,
                            account.getCurrentBalance(),
                            false,
                            "Withdrawal amount must be positive.");

            account.recordTransaction(rejected);
            return rejected;
        }

        // Daily withdrawal limit check
        if (account.getDailyWithdrawnAmount()
                .add(amount)
                .compareTo(DAILY_WITHDRAWAL_LIMIT) > 0) {

            TransactionRecord rejected =
                    new TransactionRecord(
                            txId,
                            account.getAccountId(),
                            "WITHDRAWAL",
                            amount,
                            account.getCurrentBalance(),
                            false,
                            "Exceeded daily withdrawal limit.");

            account.recordTransaction(rejected);
            return rejected;
        }

        BigDecimal currentBal =
                account.getCurrentBalance();

        // Sufficient balance
        if (currentBal.compareTo(amount) >= 0) {

            BigDecimal newBalance =
                    currentBal
                            .subtract(amount)
                            .setScale(2, RoundingMode.HALF_UP);

            account.setCurrentBalance(newBalance);
            account.addDailyWithdrawnAmount(amount);

            // Low balance penalty for checking account
            if (account.getAccountType() == AccountType.CHECKING
                    && newBalance.compareTo(
                            MINIMUM_BALANCE_MAINTENANCE) < 0) {

                newBalance =
                        newBalance
                                .subtract(LOW_BALANCE_PENALTY)
                                .setScale(2, RoundingMode.HALF_UP);

                account.setCurrentBalance(newBalance);
            }

            TransactionRecord success =
                    new TransactionRecord(
                            txId,
                            account.getAccountId(),
                            "WITHDRAWAL",
                            amount,
                            newBalance,
                            true,
                            "Withdrawal approved.");

            account.recordTransaction(success);

            return success;
        }

        // Insufficient balance but overdraft is enabled
        else if (account.isOverdraftProtectionEnabled()) {

            BigDecimal newBalance =
                    currentBal
                            .subtract(amount)
                            .subtract(OVERDRAFT_FEE)
                            .setScale(2, RoundingMode.HALF_UP);

            account.setCurrentBalance(newBalance);
            account.addDailyWithdrawnAmount(amount);

            TransactionRecord overdraftTx =
                    new TransactionRecord(
                            txId,
                            account.getAccountId(),
                            "WITHDRAWAL",
                            amount,
                            newBalance,
                            true,
                            "Overdraft approved with $35 fee applied.");

            account.recordTransaction(overdraftTx);

            return overdraftTx;
        }

        // Insufficient balance and overdraft disabled
        else {

            TransactionRecord rejected =
                    new TransactionRecord(
                            txId,
                            account.getAccountId(),
                            "WITHDRAWAL",
                            amount,
                            currentBal,
                            false,
                            "Insufficient funds and overdraft protection disabled.");

            account.recordTransaction(rejected);

            return rejected;
        }
    }

    // ============================================================
    // MAIN METHOD - USED FOR TESTING
    // ============================================================

    public static void main(String[] args) {

        AccountProcessor processor = new AccountProcessor();

        // Create a checking account with $1,000
        BankAccount account =
                new BankAccount(
                        "ACC1001",
                        AccountType.CHECKING,
                        new BigDecimal("1000.00"),
                        true);

        System.out.println("======================================");
        System.out.println("     ACCOUNT PROCESSOR DEMO");
        System.out.println("======================================");

        System.out.println("\nInitial Account Details:");
        System.out.println("Account ID: " + account.getAccountId());
        System.out.println("Account Type: " + account.getAccountType());
        System.out.println("Initial Balance: $" +
                account.getCurrentBalance());
        System.out.println("Overdraft Protection: " +
                account.isOverdraftProtectionEnabled());

        // --------------------------------------------------------
        // 1. Deposit
        // --------------------------------------------------------

        System.out.println("\n--- Transaction 1: Deposit $500 ---");

        TransactionRecord deposit =
                processor.processDeposit(
                        account,
                        "TX001",
                        new BigDecimal("500.00"));

        printTransaction(deposit);

        // --------------------------------------------------------
        // 2. Normal withdrawal
        // --------------------------------------------------------

        System.out.println("\n--- Transaction 2: Withdraw $200 ---");

        TransactionRecord withdrawal1 =
                processor.processWithdrawal(
                        account,
                        "TX002",
                        new BigDecimal("200.00"));

        printTransaction(withdrawal1);

        // --------------------------------------------------------
        // 3. Withdrawal causing low balance penalty
        // --------------------------------------------------------

        System.out.println("\n--- Transaction 3: Withdraw $1,150 ---");

        TransactionRecord withdrawal2 =
                processor.processWithdrawal(
                        account,
                        "TX003",
                        new BigDecimal("1150.00"));

        printTransaction(withdrawal2);

        // --------------------------------------------------------
        // 4. Overdraft transaction
        // --------------------------------------------------------

        System.out.println("\n--- Transaction 4: Withdraw $500 ---");

        TransactionRecord withdrawal3 =
                processor.processWithdrawal(
                        account,
                        "TX004",
                        new BigDecimal("500.00"));

        printTransaction(withdrawal3);

        // --------------------------------------------------------
        // Final account state
        // --------------------------------------------------------

        System.out.println("\n======================================");
        System.out.println("       FINAL ACCOUNT STATE");
        System.out.println("======================================");

        System.out.println("Account ID: " +
                account.getAccountId());

        System.out.println("Current Balance: $" +
                account.getCurrentBalance());

        System.out.println("Daily Withdrawn Amount: $" +
                account.getDailyWithdrawnAmount());

        System.out.println("Number of Transactions: " +
                account.getTransactionHistory().size());

        // --------------------------------------------------------
        // Transaction history
        // --------------------------------------------------------

        System.out.println("\n======================================");
        System.out.println("       TRANSACTION HISTORY");
        System.out.println("======================================");

        for (TransactionRecord record :
                account.getTransactionHistory()) {

            System.out.println(
                    record.getTransactionId()
                            + " | "
                            + record.getType()
                            + " | Amount: $"
                            + record.getAmount()
                            + " | Approved: "
                            + record.isApproved()
                            + " | Balance: $"
                            + record.getResultingBalance()
                            + " | "
                            + record.getStatusMessage());
        }
    }

    /**
     * Helper method to print transaction information.
     */
    private static void printTransaction(
            TransactionRecord transaction) {

        System.out.println(
                "Transaction ID: "
                        + transaction.getTransactionId());

        System.out.println(
                "Approved: "
                        + transaction.isApproved());

        System.out.println(
                "Resulting Balance: $"
                        + transaction.getResultingBalance());

        System.out.println(
                "Status: "
                        + transaction.getStatusMessage());
    }
}