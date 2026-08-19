# `tests/` — Automated Test Suite

This directory contains the unit, integration, and regression test suite executed via `pytest`.

---

## 🧪 Test Modules

| Test File | Target Component | What It Validates |
| :--- | :--- | :--- |
| [`test_ast_parsers.py`](file:///c:/Users/PrajwalP/Documents/GenAI%20-%20UC2/tests/test_ast_parsers.py) | `src/utils/ast_parsers.py` | Java Tree-sitter & Javalang AST parsing, VB block parsing, COBOL structural paragraph parsing. |
| [`test_dependency_scanner.py`](file:///c:/Users/PrajwalP/Documents/GenAI%20-%20UC2/tests/test_dependency_scanner.py) | `src/tools/dependency_scanner.py` | 2-pass static call resolution, language detection, cross-file edge creation, and error resilience. |
| [`test_documenter.py`](file:///c:/Users/PrajwalP/Documents/GenAI%20-%20UC2/tests/test_documenter.py) | `src/agents/documenter.py` | Prompt construction, feedback injection, JSON parsing, and master documentation Markdown assembly. |
| [`test_evaluator.py`](file:///c:/Users/PrajwalP/Documents/GenAI%20-%20UC2/tests/test_evaluator.py) | `src/agents/evaluator.py` | 6-metric scoring algorithm, issue tagging, pass/fail thresholding, and feedback generation. |
| [`test_splitter.py`](file:///c:/Users/PrajwalP/Documents/GenAI%20-%20UC2/tests/test_splitter.py) | `src/agents/splitter.py` | Recursive token boundary splitting, sub-chunk overlap preservation, and metadata propagation. |

---

## 🏃 Running Tests

```bash
# Run the entire test suite
pytest

# Run tests with verbose output
pytest -v

# Run a specific test suite
pytest tests/test_evaluator.py
```
