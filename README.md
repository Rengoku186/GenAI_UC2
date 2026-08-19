# Legacy Code Modernization Agentic System ⚡

An autonomous, multi-agent system built on **LangGraph**, **LangChain**, **NetworkX**, and **Streamlit** that converts legacy **COBOL**, **Visual Basic**, and **Java** codebases into modern **Java 17+/21+** microservices — complete with automated documentation, tests, and a triage dashboard.

---

## 🌟 Key Features

- **Multi-Language Ingestion & Parsing**: Extracts semantic paragraphs (COBOL), modules/functions (VB), and classes/methods (Java) into discrete chunks.
- **Cross-Chunk Dependency Mapping**: Builds NetworkX directed graphs for inter-chunk procedure calls, copybooks, shared data, and file/DB I/O.
- **Automated Documentation**: Synthesizes formal specifications — purpose, inputs, outputs, business rules, and control flow — for each chunk.
- **LLM-as-Judge & Static Validation**: Multi-stage evaluation of documentation completeness, Java syntax, cyclomatic complexity, and functional parity.
- **Refinement Loops with Retry Caps**: Automated iteration between Evaluators and Refiners with configurable retry limits (`configs/thresholds.yaml`).
- **Dual Test Generation & Sandbox Execution**: Generates both **pytest** and **JUnit 5** test suites from documented business rules, then executes pytest in an isolated subprocess sandbox.
- **Full-File Synthesis**: Merges chunk-level outputs into cohesive, modularized modern Java services and full documentation via `FullFileSynthesizer`.
- **Execution Knowledge Store**: Captures structured pipeline logs per-run into a `.knowledge_store` file for audit and replay.
- **Three-State Observability Dashboard**: Streamlit dashboard classifying chunks as **Auto-Passed**, **Auto-Passed after Refinement**, or **Flagged for Human Review**, sorted lowest-confidence first.

---

## 🏗 System Architecture

```mermaid
flowchart TD
    Start([Legacy Source Code]) --> Chunker[1. Ingestion & Chunker Agent]
    Chunker --> ChunkEval{3. Chunk Evaluator}
    ChunkEval -- Needs Split Fix under cap --> Chunker
    ChunkEval -- Passed / Exceeded Cap --> DepMapper[2. Dependency Mapper Agent]
    DepMapper --> DepEval{4. Dependency Evaluator}
    DepEval -- Missing Edges under cap --> DepMapper
    DepEval -- Passed / Exceeded Cap --> Documenter[5. Documenter Agent]
    Documenter --> DocEval{6. Doc Evaluator}
    DocEval -- Issues under cap --> DocRefiner[7. Doc Refiner Agent]
    DocRefiner --> DocEval
    DocEval -- Passed / Exceeded Cap --> CodeGen[8. Code Generator Agent]
    CodeGen --> CodeEval{9. Code Evaluator}
    CodeEval -- Syntax/Parity Flaw under cap --> CodeRefiner[10. Code Refiner Agent]
    CodeRefiner --> CodeEval
    CodeEval -- Passed / Exceeded Cap --> TestGen[11. Test Generator Agent]
    TestGen --> TestExec[12. Test Executor Agent]
    TestExec -- Test Failures under cap --> CodeRefiner
    TestExec -- All Passed / Exceeded Cap --> ReportBuilder[13. Report Builder]
    ReportBuilder --> Dashboard([Streamlit Triage Dashboard])
```

---

## 📁 Repository Structure

```
GenAI - UC2/
├── README.md
├── pyproject.toml
├── requirements.txt
├── .env.example
├── configs/
│   ├── agents.yaml             # Agent pipeline switches & stage configs
│   ├── llm_config.yaml         # LLM provider, model, and temperature per agent
│   └── thresholds.yaml         # Retry caps and confidence cutoffs
├── src/
│   ├── orchestrator/
│   │   ├── graph.py            # LangGraph StateGraph, run_pipeline(), & CLI entrypoint
│   │   ├── state.py            # Pydantic models & PipelineState TypedDict
│   │   └── router.py           # Conditional routing logic with retry limit enforcement
│   ├── agents/
│   │   ├── base_agent.py       # LLM provider & structured invocation base class
│   │   ├── ingestion_chunker.py
│   │   ├── dependency_mapper.py
│   │   ├── chunk_evaluator.py
│   │   ├── dependency_evaluator.py
│   │   ├── documenter.py
│   │   ├── doc_evaluator.py
│   │   ├── doc_refiner.py
│   │   ├── code_generator.py   # Generates Java 17+/21+ services
│   │   ├── code_evaluator.py
│   │   ├── code_refiner.py
│   │   ├── test_generator.py   # Generates pytest & JUnit 5 suites
│   │   └── test_executor.py    # Sandbox subprocess pytest runner
│   ├── parsers/
│   │   ├── cobol_parser.py     # COBOL DIVISION, SECTION, PARAGRAPH parser
│   │   ├── vb_parser.py        # VB6 / VB.NET Sub, Function, Module parser
│   │   └── java_parser.py      # Java Class, Interface, Method parser
│   ├── tools/
│   │   ├── ast_tools.py        # AST inspection and language detection
│   │   ├── graph_tools.py      # NetworkX topological sort and cycle detection
│   │   ├── static_analysis_tools.py # Syntax & cyclomatic complexity analysis
│   │   └── sandbox_exec.py     # Isolated temporary subprocess pytest execution
│   ├── prompts/                # Pydantic-structured system and human prompt templates
│   ├── evaluation/
│   │   ├── full_file_synthesizer.py # Merges chunks into complete Java services & docs
│   │   ├── metrics.py          # Confidence score & 3-state classification
│   │   ├── rubric.yaml         # Quality rubric criteria & weights
│   │   └── report_builder.py   # State aggregation into JSON evaluation reports
│   ├── utils/
│   │   ├── logger.py           # Structured logging setup
│   │   ├── pipeline_log_handler.py  # In-memory log capture per pipeline run
│   │   └── knowledge_store.py  # Persists execution trace to .knowledge_store files
│   └── dashboard/
│       ├── app.py              # Streamlit Web App entrypoint
│       └── components/         # Metric cards, Triage table, Diffs, Graph, Knowledge Store views
├── data/
│   └── legacy_source/          # Legacy Java source files (AccountProcessor, DemoApplication)
├── outputs/
│   └── evaluation_reports/     # Generated JSON run audit trails
├── tests/                      # Pytest unit and E2E test suites
│   ├── test_agents.py
│   ├── test_full_file_synthesizer.py
│   ├── test_graph_routing.py
│   ├── test_parsers.py
│   ├── test_pipeline_e2e.py
│   └── test_tools.py
└── notebooks/                  # Interactive demo Jupyter notebook
```

---

## 🚀 Quickstart Guide

### 1. Installation & Environment Setup

```bash
# Navigate to the repository
cd "GenAI - UC2"

# Install package and dependencies in editable mode
pip install -e .

# (Alternative) Install from requirements.txt directly
pip install -r requirements.txt

# Configure API keys — or leave LLM_PROVIDER=mock for full offline testing
cp .env.example .env
```

### 2. Run the Multi-Agent Modernization Pipeline

Execute the autonomous pipeline on the sample legacy Java files:

```bash
# Easiest way (auto-discovers sample files in data/legacy_source/)
python main.py

# Or run on a specific legacy file
python main.py data/legacy_source/AccountProcessor.java

# Or use the module path / installed CLI entrypoint
python -m src.orchestrator.graph
modernize data/legacy_source/DemoApplication.java
```

### 3. Launch the Observability Dashboard

```bash
# Easiest way
python main.py --dashboard

# Or run via streamlit directly
streamlit run src/dashboard/app.py

# Or use the installed CLI entrypoint
dashboard
```

---

## 📊 Three-State Classification System

The dashboard categorizes each migrated chunk into one of three explicit states:

| Status | Badge | Description | Action Required |
| :--- | :--- | :--- | :--- |
| **Auto-Passed** | 🟢 Green | Satisfied all quality thresholds on v1 without any evaluator rejection. | None — ready for production. |
| **Auto-Passed (Refined)** | 🟡 Yellow | Failed initial evaluation but corrected via automated refinement loops within retry caps. | Optional sanity check of diffs. |
| **Flagged for Human Review** | 🔴 Red | Unresolved issues after exhausting max retries, or explicitly flagged for manual check. | **Reviewer must inspect** via the dashboard diff viewer. |

---

## ⚙ Configuration & Customization

### `configs/thresholds.yaml`
```yaml
retry_caps:
  chunking: 2
  dependency_mapping: 2
  documentation: 3
  code_generation: 3
  test_generation: 3

confidence_thresholds:
  chunk_evaluation: 0.85
  dependency_evaluation: 0.85
  doc_evaluation: 0.80
  code_evaluation: 0.85
  test_coverage_min_pct: 80.0

human_in_the_loop:
  interrupt_on_low_confidence: false   # Pauses LangGraph on human-review flag
  interactive_approval_required: false
```

### `configs/llm_config.yaml`
```yaml
default:
  provider: "openai"   # "openai", "anthropic", or "mock"
  model: "gpt-4o"
  temperature: 0.2
  max_tokens: 4096
  timeout: 60

agents:
  doc_evaluator:
    temperature: 0.0   # Deterministic LLM-as-judge
  code_evaluator:
    temperature: 0.0
  dependency_mapper:
    temperature: 0.0
  # ... per-agent overrides for all 12 agents
```

### Environment Variables (`.env`)
```bash
OPENAI_API_KEY=your-openai-api-key-here
ANTHROPIC_API_KEY=your-anthropic-api-key-here
GOOGLE_API_KEY=your-gemini-api-key-here

LLM_PROVIDER=mock          # mock | openai | anthropic
CONFIG_DIR=configs/
DATA_DIR=data/
OUTPUT_DIR=outputs/
LOG_LEVEL=INFO
SANDBOX_TIMEOUT_SECONDS=15
```

---

## 🧪 Running Unit & Integration Tests

Run the full pytest suite:

```bash
pytest tests/ -v

# With coverage report
pytest tests/ -v --cov=src --cov-report=term-missing
```

Test files cover:
- `test_agents.py` — Agent instantiation and execution contracts
- `test_full_file_synthesizer.py` — Full-file synthesis and output validation
- `test_graph_routing.py` — LangGraph conditional routing logic
- `test_parsers.py` — COBOL, VB, and Java parser correctness
- `test_pipeline_e2e.py` — End-to-end mock pipeline run
- `test_tools.py` — AST, graph, sandbox, and static analysis tools

---

## 🔌 Integrating Real Legacy Codebases

1. Place legacy source files into `data/legacy_source/` (or any custom directory).
2. Set your `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` in `.env` and set `LLM_PROVIDER=openai`.
3. Run `python -m src.orchestrator.graph /path/to/your/files/*` (supports `.cbl`, `.vb`, `.java`).
4. Open the Streamlit dashboard to inspect triage rankings, visual diffs, generated Java services, and pytest execution results.
5. Review the generated `.knowledge_store` file in `outputs/` for a structured execution trace of the pipeline run.

---

## 🧩 Key Design Decisions

| Concern | Approach |
| :--- | :--- |
| **Orchestration** | LangGraph `StateGraph` with typed `PipelineState` shared across all nodes |
| **State Management** | Pydantic models with custom `merge_dicts` / `append_list` LangGraph reducers |
| **LLM Abstraction** | `BaseAgent` with provider-agnostic invocation; `mock` mode for offline testing |
| **Output Target** | Modern **Java 17+/21+** services (records, sealed classes, switch expressions) |
| **Test Frameworks** | **pytest** (executed in sandbox) + **JUnit 5** (generated for Java consumers) |
| **Observability** | Per-run `PipelineMemoryHandler` + `KnowledgeStore` + Streamlit dashboard |
| **Dependency Graph** | **NetworkX** directed graph for topological ordering and cycle detection |

