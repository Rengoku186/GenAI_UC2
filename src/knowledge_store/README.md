# `src/knowledge_store/` — Persistent Knowledge Repository

This directory contains the knowledge persistence engine for storing, indexing, and querying legacy code chunks and generated specifications.

---

## 💾 Overview

The [`store.py`](file:///c:/Users/PrajwalP/Documents/GenAI%20-%20UC2/src/knowledge_store/store.py) module manages persistent storage using **ChromaDB** vector database alongside local JSON metadata caching.

---

## 🔑 Key Capabilities

- **Vector Indexing:** Embeds chunk code and documentation summaries using HuggingFace / OpenAI / Google embeddings for semantic similarity search.
- **Metadata Management:** Stores structured metadata including:
  - File path, scope, method/paragraph name, line ranges.
  - Dependency lists (`depends_on`, `unresolved`).
  - Generated documentation models (`ChunkDoc`).
  - Evaluation scores and history.
- **RAG Support:** Provides lookup methods (`query()`, `get_chunk()`, `get_all_docs()`) for downstream migration and code conversion agents.

---

## 📁 Files

- [`store.py`](file:///c:/Users/PrajwalP/Documents/GenAI%20-%20UC2/src/knowledge_store/store.py): Implements the `KnowledgeStore` class and SQLite/Chroma persistence interfaces.
