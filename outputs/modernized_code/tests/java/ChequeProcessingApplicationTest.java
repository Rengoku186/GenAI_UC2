package com.modern.services;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class ChequeProcessingApplicationTest {

    @Test
    void testCurrencyConversion() {
        var fx = new ChequeProcessingApplication.CurrencyExchangeService();
        double converted = fx.convertCurrency(100.0, "EUR", "USD");
        assertEquals(109.0, converted);
    }

    @Test
    void testFraudDetection() {
        var fraud = new ChequeProcessingApplication.FraudDetectionService();
        assertTrue(fraud.isFraudulent("1001", 1000.0, false));
        assertFalse(fraud.isFraudulent("1001", 1000.0, true));
    }
}