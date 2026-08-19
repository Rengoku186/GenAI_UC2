# `src/tools/` — Static Analysis & Graph Analysis Tools

This directory contains static analysis engines for AST chunk extraction, dependency call graph construction, and cyclic dependency resolution.

---

## 🛠️ Modules

### 1. [`dependency_scanner.py`](file:///c:/Users/PrajwalP/Documents/GenAI%20-%20UC2/src/tools/dependency_scanner.py)
* **Purpose:** Performs 2-pass multi-language static analysis to construct an interconnected call graph across the codebase.
* **Core Functions:**
  * `scan_project(file_paths, use_ai=True)`: Parses files, extracts callable blocks, maps intra- and cross-file dependencies, and returns a `networkx.DiGraph`.
  * `parse_file_chunks(file_path, code_content, language)`: Splits files into language-specific functional units (methods, subroutines, paragraphs).
* **Node Granularity:** Fully qualified ID format: `<file_path>::<scope>::<name>`.

### 2. [`cycle_detector.py`](file:///c:/Users/PrajwalP/Documents/GenAI%20-%20UC2/src/tools/cycle_detector.py)
* **Purpose:** Detects circular call loops (e.g., mutual recursion or cyclic dependencies) and condenses the graph into a strictly acyclic processing order.
* **Core Functions:**
  * `prepare_processing_graph(graph)`: Runs Tarjan's Strongly Connected Components (SCC) algorithm to collapse cyclic subgraphs into unified super-nodes, returning `(condensed_dag, topological_processing_order)`.
  * `find_cycles(graph)`: Identifies and reports all elementary cycles in the graph.
