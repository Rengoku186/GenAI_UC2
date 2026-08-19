# `src/agents/` — Autonomous Agent Modules

This directory contains the core LLM-powered agents responsible for understanding, documenting, evaluating, and splitting legacy code units.

---

## 🤖 Modules

### 1. [`documenter.py`](file:///c:/Users/PrajwalP/Documents/GenAI%20-%20UC2/src/agents/documenter.py)
* **Purpose:** Generates comprehensive, standardized technical & business documentation for individual code chunks.
* **Key Functions:**
  * `document_chunk(chunk, feedback=None, previous_doc=None)`: Invokes the LLM with structured prompts tailored to COBOL, Visual Basic, or Java. Supports refinement feedback loops.
  * `generate_master_documentation(chunks, docs, entry_point, project_name)`: Merges all chunk docs into a coherent 3-section Master Markdown Specification (Executive Summary, Function-wise specs, Key Technical Operations Table).
  * `should_document_chunk(chunk)`: Filters out trivial boilerplate / empty chunks.

### 2. [`evaluator.py`](file:///c:/Users/PrajwalP/Documents/GenAI%20-%20UC2/src/agents/evaluator.py)
* **Purpose:** Acts as a quality gate evaluating generated documentation before acceptance.
* **Evaluation Criteria (Score $\ge 80$ to pass):**
  * `business_logic_score` (Weight: 25%)
  * `variable_mapping_score` (Weight: 20%)
  * `control_flow_score` (Weight: 15%)
  * `calculations_score` (Weight: 15%)
  * `dependencies_score` (Weight: 15%)
  * `clarity_score` (Weight: 10%)
* **Key Functions:**
  * `evaluate_chunk_doc(chunk, doc)`: Produces an `EvalResult` with score breakdown, specific issue tags (`[MISSING_FORMULA]`, `[VARIABLE_MISMATCH]`, `[MISSING_CONDITION]`, etc.), and actionable feedback for refinement.

### 3. [`splitter.py`](file:///c:/Users/PrajwalP/Documents/GenAI%20-%20UC2/src/agents/splitter.py)
* **Purpose:** Ensures code chunks do not exceed LLM context window limits while preserving syntactic integrity.
* **Key Functions:**
  * `split_chunk_if_oversized(chunk, max_tokens=3000)`: Recursively breaks large functions or paragraphs into sub-chunks with semantic line overlaps and parent ID tracking.
  * `create_chunk_from_node_data(qid, node_data)`: Converts raw graph node dictionaries into validated `Chunk` Pydantic models.
