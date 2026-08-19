# `src/` — Core Architecture & Source Code

This directory contains the entire source code for the **GenAI Legacy Code Conversion & Understanding System**.

---

## 🏛️ Module Overview

| Subpackage / File | Description | Key Components |
| :--- | :--- | :--- |
| [`agents/`](file:///c:/Users/PrajwalP/Documents/GenAI%20-%20UC2/src/agents/README.md) | Agentic LLM workers for documentation, evaluation, and code splitting | `documenter.py`, `evaluator.py`, `splitter.py` |
| [`dashboard/`](file:///c:/Users/PrajwalP/Documents/GenAI%20-%20UC2/src/dashboard/README.md) | Streamlit-based web dashboard for human review and SME verification | `app.py` |
| [`knowledge_store/`](file:///c:/Users/PrajwalP/Documents/GenAI%20-%20UC2/src/knowledge_store/README.md) | Persistent storage for processed chunks, vector embeddings, and docs | `store.py` |
| [`orchestrator/`](file:///c:/Users/PrajwalP/Documents/GenAI%20-%20UC2/src/orchestrator/README.md) | LangGraph Phase 1 state machine driving the sequential pipeline | `phase1_graph.py` |
| [`parsing/`](file:///c:/Users/PrajwalP/Documents/GenAI%20-%20UC2/src/parsing/README.md) | Two-tier language detection engine (heuristic + LLM fallback) | `language_detector.py` |
| [`tools/`](file:///c:/Users/PrajwalP/Documents/GenAI%20-%20UC2/src/tools/README.md) | Static analysis tools for call graphs and cycle condensation | `dependency_scanner.py`, `cycle_detector.py` |
| [`utils/`](file:///c:/Users/PrajwalP/Documents/GenAI%20-%20UC2/src/utils/README.md) | Tree-sitter/Javalang AST parsers, unified LLM client, and logging | `ast_parsers.py`, `llm.py`, `log_config.py` |
| [`schemas.py`](file:///c:/Users/PrajwalP/Documents/GenAI%20-%20UC2/src/schemas.py) | Pydantic data models for chunks, documentation, and evaluation results | `Chunk`, `ChunkDoc`, `EvalResult` |
| [`state.py`](file:///c:/Users/PrajwalP/Documents/GenAI%20-%20UC2/src/state.py) | TypedDict state definition for LangGraph pipeline | `PipelineState` |

---

## 🔄 Core Data Flow

1. **State Initialization:** A `PipelineState` dictionary is initialized with target `file_paths`.
2. **Scanning & Ingestion:** `dependency_scanner.scan_project` identifies functional units and resolves call references into an `nx.DiGraph`.
3. **DAG Condensation:** `cycle_detector.prepare_processing_graph` resolves cycles and provides a topological chunk queue.
4. **Iterative Processing:** For each chunk:
   - `splitter.py` ensures the chunk fits within token limits.
   - `documenter.py` drafts structured documentation.
   - `evaluator.py` scores the documentation (threshold $\ge 80$).
   - If score $< 80$, the chunk loops through documenter refinement (max 3 retries) before being saved or added to `flagged_items.json`.
5. **Persistence & Assembly:** Verified docs are stored in `KnowledgeStore` and compiled into `docs/documentation.md`.
