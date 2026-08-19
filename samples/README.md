# `samples/` — Sample Legacy Codebases

This directory contains test programs in supported legacy programming languages used for pipeline validation, demonstrations, and test suites.

---

## 📁 Subdirectories

| Subdirectory | Language | Files | Description |
| :--- | :--- | :--- | :--- |
| [`cobol/`](file:///c:/Users/PrajwalP/Documents/GenAI%20-%20UC2/samples/cobol) | COBOL (`.cbl`) | `BILL100.cbl`, `PAY200.cbl` | Batch billing and payroll processing with sections, paragraphs, and `PERFORM` calls. |
| [`java/`](file:///c:/Users/PrajwalP/Documents/GenAI%20-%20UC2/samples/java) | Java (`.java`) | `BillingService.java`, `DemoApplication.java` | Object-oriented billing services and enterprise test applications with method calls and validation logic. |
| [`vb/`](file:///c:/Users/PrajwalP/Documents/GenAI%20-%20UC2/samples/vb) | Visual Basic / VBA (`.bas`) | `PAY100.bas` | Payroll calculation modules with `Sub` and `Function` procedures and `GoSub`/`Call` statements. |

---

## 🚀 Running Samples

To test the system against any sample file:

```bash
# Run on Java sample
python main.py -f samples/java/BillingService.java -o docs/

# Run on COBOL sample
python main.py -f samples/cobol/BILL100.cbl -o docs/

# Run on VB sample
python main.py -f samples/vb/PAY100.bas -o docs/
```
