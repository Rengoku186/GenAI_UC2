# `docs/` — Documentation & Evaluation Artifacts

This directory contains the generated technical specifications, master markdown documentation, and human-in-the-loop flagged items produced by the pipeline.

---

## 📄 Artifacts

| File | Description |
| :--- | :--- |
| [`documentation.md`](file:///c:/Users/PrajwalP/Documents/GenAI%20-%20UC2/docs/documentation.md) | The publication-ready **Master Markdown Specification** assembling all verified chunk documentation, executive summaries, function specs, and technical operations tables. |
| [`flagged_items.json`](file:///c:/Users/PrajwalP/Documents/GenAI%20-%20UC2/docs/flagged_items.json) | Structured log of code chunks that failed the evaluator quality threshold ($\ge 80$) after maximum refinement retries, formatted for SME inspection and manual review. |

---

## 🔍 Flagged Items Schema

When a chunk fails evaluation after maximum retries, an entry is recorded in `flagged_items.json`:

```json
[
  {
    "chunk_id": "samples/java/BillingService.java::BillingService::processBilling",
    "overall_score": 41.2,
    "issues": [
      "[VARIABLE_MISMATCH] Input variable was not found in the source code tokens.",
      "[MISSING_FORMULA] The documentation does not specify calculation logic."
    ],
    "reason": "Max refinement retries reached"
  }
]
```
