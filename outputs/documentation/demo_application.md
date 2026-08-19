# Legacy System Documentation: Cheque Processing & Fraud Management System

- **Source File:** `DemoApplication.java`
- **Original Architecture:** Legacy Monolithic Java Application (`public class DemoApplication`) with 15+ embedded static service components
- **Target Modern Services:** Python 3.11+ (`demo_application.py`) & Java 17+ (`ChequeProcessingApplication.java`)
- **Automated Verification:** 100% Pytest & JUnit 5 Suite Passed

---

## 1. Executive Summary & System Overview
`DemoApplication.java` is an enterprise banking cheque clearing and settlement ecosystem. The monolithic service orchestrates:
1. **User Authentication & RBAC:** Multi-attempt credential validation supporting `EMPLOYEE` and `ACCOUNT_HOLDER` security roles.
2. **Cheque Processing & Settlement:** Single and batch cheque debit/credit transaction workflows.
3. **Fraud Detection & Velocity Checks:** Anomaly scoring, velocity limit rules, duplicate cheque detection, and signature mismatch triggers.
4. **Multi-Currency FX Exchange:** Real-time exchange rate calculation, Bid/Ask spreads, and currency conversions (USD, EUR, GBP, JPY, CAD, INR).
5. **Exception & Legal FIR Management:** Logging of bounced/altered cheques and formal Police Station FIR complaint tracking.
6. **Digital Imaging & Clearinghouse Cryptography:** Image scanning, encryption with digital signatures, and interbank clearinghouse transmission.
7. **Administrative Operations:** IFSC/Bank code mappings, batch lifecycle orchestration, and stuck transaction recovery.

---

## 2. Core Service Components & Domain Architecture

| Component | Responsibility | Key Methods / Capabilities |
| :--- | :--- | :--- |
| `UserService` | Authentication & Security | `authenticate()`, `registerUser()`, max 3 login attempts |
| `ChequeProcessor` | Settlement Orchestration | `processCheque()`, `cancelCheque()`, integration with all sub-services |
| `CurrencyExchangeService` | FX Conversion & Spreads | `getExchangeRate()`, `convertCurrency()`, `getDetailedExchangeRates()` |
| `SignatureVerificationService`| Biometric/Signature Audit | `verifySignature()`, automated account signature caching |
| `FraudDetectionService` | Transaction Risk Analysis | Anomaly detection, duplicate cheque check, velocity alerts |
| `ExceptionReportManager` | Exception & Legal Records | `reportException()`, `recordFIRDetails()`, FIR date & police station audit |
| `ChequeStatusManager` | Lifecycle State Machine | `setStatus()`, `getStatus()` (`ISSUED`, `PROCESSED`, `CANCELED`) |
| `CryptographyService` | Interbank Security | `encryptData()`, `signData()` for clearinghouse transmissions |
| `ClearinghouseService` | External Bank Gateway | `submitToClearinghouse()` via SFTP/REST mock payload |
| `ChequePrintingService` | Slip Formatting | `printCheque()` ASCII layout generation |
| `AdminService` | Master Data Management | `addOrUpdateIFSC()`, `createBatch()`, `resetStuckTransaction()` |

---

## 3. Algorithmic Business Rules & Policies

### Rule 1: Multi-Tier Authentication & RBAC
- Users are granted 3 consecutive login attempts before system lockout.
- Roles `EMPLOYEE` and `ACCOUNT_HOLDER` determine access to admin menus (Options 13-15: IFSC, Batches, Stuck Resets).

### Rule 2: Multi-Currency Foreign Exchange Rate Calculation
$$\text{Converted Amount} = \text{Amount} \times \left(\frac{\text{Rate}(\text{To Currency})}{\text{Rate}(\text{From Currency})}\right)$$
- Supported FX pairings include USD (base 1.0), EUR (1.10), GBP (1.28), JPY (0.0067), CAD (0.74), INR (0.012).
- Spread logic applies Mid, Buy, Sell, and standard bank fee adjustments.

### Rule 3: Signature Verification & Fraud Detection
- Every transaction requires account signature matching against cached customer signatures.
- Fraud rules flag:
  - Transactions exceeding account balance or velocity limits.
  - Duplicate cheque numbers previously marked as `PROCESSED` or `CANCELED`.
  - Mismatched signature payloads.

### Rule 4: Exception Handling & Legal FIR Recording
- Bounced or fraudulent cheques generate an `ExceptionRecord`.
- For formal legal action, bank officers can attach an `FIRDetails` record containing:
  - `FIR Number`, `Police Station Name`, `FIR Date (YYYY-MM-DD)`, and legal `Remarks`.

### Rule 5: Cryptographic Digital Signing for Clearinghouse Transit
- Cheque images are converted into raw byte arrays.
- Payload is encrypted with a master key and digitally signed using a private key hash.
- Verified payloads are submitted directly to interbank clearinghouse queues.

---

## 4. System Workflow Diagram

```
User Login (3 Retries)
       │
       ▼
Main Menu Dispatcher
 ├── [1]  Process Single Cheque (Signature Check -> FX -> Fraud -> Core Banking Ledger)
 ├── [2]  Process Batch (Iterative multi-cheque processing with error isolation)
 ├── [3]  Cheque History (Account transaction audit trail)
 ├── [4]  Currency Exchange (FX rates, bid/ask, and conversions)
 ├── [5]  Generate Reports (Daily, Weekly, Monthly, Custom Date Range CSV exports)
 ├── [6]  Cheque Image Upload (Load image -> Encrypt -> Sign -> Dispatch to Clearinghouse)
 ├── [7]  Simulate Cheque Printing (Formatted ASCII cheque slip output)
 ├── [9]  Exception Reports (Bounced/duplicate audit log)
 ├── [10] Cheque Statuses (ISSUED / PROCESSED / CANCELED)
 ├── [11] Cancel Cheque (Immediate revocation of issued cheques)
 ├── [12] Record FIR/Police Complaint (Legal escalation with police station and FIR ID)
 └── [13-15] Admin (IFSC mappings, Batch lifecycle, Stuck transaction reset)
```