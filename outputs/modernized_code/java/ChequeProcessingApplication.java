package com.modern.services;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.*;

/**
 * Modernized Enterprise Cheque Processing & Fraud Management Application (Java 17+/21+).
 * Clean rewrite of monolithic legacy DemoApplication.java.
 */
public class ChequeProcessingApplication {

    public enum ChequeStatus { ISSUED, PROCESSED, CANCELED, STUCK }
    public enum UserRole { EMPLOYEE, ACCOUNT_HOLDER, ADMIN }

    public record User(String username, String role) {}
    public record FIRDetails(String firNumber, String policeStation, LocalDate firDate, String remarks) {}
    public record ChequeRecord(String accountNumber, String chequeNumber, String currency, double amount, ChequeStatus status) {}

    public static class CurrencyExchangeService {
        private final Map<String, Double> rates = Map.of(
            "USD", 1.0, "EUR", 1.09, "GBP", 1.27, "JPY", 0.0067, "CAD", 0.74, "INR", 0.012
        );

        public double getExchangeRate(String currency) {
            return rates.getOrDefault(currency.toUpperCase(), 0.0);
        }

        public double convertCurrency(double amount, String fromCurr, String toCurr) {
            double from = getExchangeRate(fromCurr);
            double to = getExchangeRate(toCurr);
            if (from <= 0 || to <= 0) return 0.0;
            return Math.round((amount * from / to) * 100.0) / 100.0;
        }
    }

    public static class FraudDetectionService {
        public boolean isFraudulent(String account, double amount, boolean signatureValid) {
            return !signatureValid || amount > 50000.0;
        }
    }

    public static class ExceptionReportManager {
        public record ExceptionRecord(String accountNumber, String chequeNumber, String type, String details, FIRDetails fir) {}
        private final List<ExceptionRecord> records = new ArrayList<>();

        public void reportException(String acc, String chq, String type, String details) {
            records.add(new ExceptionRecord(acc, chq, type, details, null));
        }
        public List<ExceptionRecord> getRecords() { return Collections.unmodifiableList(records); }
    }
}