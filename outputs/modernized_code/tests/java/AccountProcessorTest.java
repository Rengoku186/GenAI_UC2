package com.modern.services;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.BeforeEach;
import java.math.BigDecimal;
import static org.junit.jupiter.api.Assertions.*;

class AccountProcessorTest {

    private AccountProcessor processor;

    @BeforeEach
    void setUp() {
        processor = new AccountProcessor();
    }

    @Test
    void testDepositSuccess() {
        var acc = new AccountProcessor.BankAccount("ACC01", AccountProcessor.AccountType.CHECKING, new BigDecimal("500.00"), true);
        var tx = processor.processDeposit(acc, "TX01", new BigDecimal("250.00"));
        assertTrue(tx.isApproved());
        assertEquals(new BigDecimal("750.00"), tx.resultingBalance());
    }

    @Test
    void testOverdraftWithdrawal() {
        var acc = new AccountProcessor.BankAccount("ACC02", AccountProcessor.AccountType.SAVINGS, new BigDecimal("50.00"), true);
        var tx = processor.processWithdrawal(acc, "TX02", new BigDecimal("100.00"));
        assertTrue(tx.isApproved());
        assertEquals(new BigDecimal("-85.00"), tx.resultingBalance());
    }
}