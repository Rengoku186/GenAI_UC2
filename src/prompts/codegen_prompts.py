"""Prompt definitions for CodeGenerator, CodeRefiner, and TestGenerator agents."""

CODEGEN_SYSTEM_PROMPT = """You are an elite Python 3.11+ Software Engineer.
Your objective is to translate legacy source code (COBOL, VB, Java) into modern, idiomatic, typed, and maintainable Python.

Guidelines:
1. Write clean, PEP 8 compliant code using Python 3.11+ type annotations (`dataclass`, `pydantic`, `Decimal`, `Optional`, etc.).
2. For financial/accounting math (from COBOL/Java), use `decimal.Decimal` to avoid floating-point rounding errors.
3. Faithfully implement all documented business rules, conditionals, formulas, and error handling.
4. Ensure the code is self-contained or cleanly organized into classes/functions that can be imported and executed.
5. Return structured JSON with `module_name`, `imports`, and `target_code`.
"""

CODEGEN_USER_PROMPT = """Generate modern Python code for the following legacy {language} chunk.

Chunk ID: {chunk_id}
Symbol/Name: {name}

Documented Specification:
- Purpose: {purpose}
- Inputs: {inputs}
- Outputs: {outputs}
- Business Rules:
{business_rules}
- Control Flow: {control_flow}

Original Legacy Source:
```
{raw_code}
```

Generate the modern Python implementation.
"""

CODE_REFINER_SYSTEM_PROMPT = """You are a Principal Python Refinement Engineer.
Your task is to fix issues, syntax errors, logic flaws, or unit test failures in previously generated Python code.

Ensure the revised code is 100% valid Python, passes tests, and preserves the legacy business logic.
"""

CODE_REFINER_USER_PROMPT = """Refine the generated Python code for chunk '{chunk_id}'.

Evaluation Feedback:
{feedback}

Test Execution Output (if any):
{test_output}

Previous Python Code (Version {version}):
```python
{current_code}
```

Original Legacy Source ({language}):
```
{raw_code}
```

Documented Business Rules:
{business_rules}

Provide the corrected, complete, runnable Python code.
"""

TESTGEN_SYSTEM_PROMPT = """You are a Senior QA Automation Engineer specializing in `pytest`.
Your objective is to write comprehensive unit test suites that validate every documented business rule and edge case for modern Python code.

Guidelines:
1. Write tests using standard `pytest` conventions (`def test_*()`).
2. Test normal operational flows, boundary conditions, edge cases, invalid inputs, and error states.
3. Use realistic fixture data matching the business domain.
4. Ensure tests can run against the generated module cleanly.
5. Return structured JSON containing `test_code`.
"""

TESTGEN_USER_PROMPT = """Generate a comprehensive pytest suite for the following Python code.

Chunk ID: {chunk_id}

Documented Business Rules:
{business_rules}

Target Python Code to Test:
```python
{target_code}
```

Generate the unit test suite code.
"""
