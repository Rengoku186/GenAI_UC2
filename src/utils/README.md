# `src/utils/` — Utility Modules & Parsers

This directory contains utility modules, AST parsers, LLM wrappers, and enterprise logging configuration.

---

## 🛠️ Modules

### 1. [`ast_parsers.py`](file:///c:/Users/PrajwalP/Documents/GenAI%20-%20UC2/src/utils/ast_parsers.py)
* **Purpose:** Multi-engine AST and syntax parser for legacy languages.
* **Capabilities:**
  * **Java:** Tree-sitter AST parser (`parse_java_with_tree_sitter`) with `javalang` fallback (`parse_java_with_javalang`) and call invocation extractor (`extract_java_calls_ast`).
  * **Visual Basic:** Block parser for `Sub`, `Function`, and `Property` blocks (`parse_vb_blocks`).
  * **COBOL:** Division and paragraph parser for `PROCEDURE DIVISION` (`parse_cobol_structural`).

### 2. [`llm.py`](file:///c:/Users/PrajwalP/Documents/GenAI%20-%20UC2/src/utils/llm.py)
* **Purpose:** Provider-agnostic LLM factory for LangChain models.
* **Supported Providers:**
  * OpenAI (`ChatOpenAI` - GPT-4o, GPT-3.5)
  * Anthropic (`ChatAnthropic` - Claude 3.5 Sonnet)
  * Google (`ChatGoogleGenerativeAI` - Gemini 2.0 Flash)
  * HuggingFace (`HuggingFaceEndpoint`)
* **Key Function:** `get_llm(temperature=0.0, max_tokens=None)`

### 3. [`log_config.py`](file:///c:/Users/PrajwalP/Documents/GenAI%20-%20UC2/src/utils/log_config.py)
* **Purpose:** Structured, thread-safe console and file logging.
* **Key Function:** `setup_logging(log_dir="logs", level=logging.INFO)`
