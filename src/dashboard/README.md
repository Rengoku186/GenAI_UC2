# `src/dashboard/` — Streamlit Human Review Dashboard

This directory houses the interactive **Human-in-the-Loop Review Dashboard** built with Streamlit.

---

## 🖥️ Overview

The dashboard allows Subject Matter Experts (SMEs), Solution Architects, and Developers to:
- **Inspect Generated Documentation:** Browse the generated Master Markdown specification and individual chunk documentation.
- **Review Flagged Items:** Review low-scoring or ambiguous chunks flagged during pipeline evaluation (`docs/flagged_items.json`).
- **Knowledge Store Explorer:** Query the ChromaDB vector database and view indexed code chunks and metadata.
- **Trigger Pipeline Runs:** Upload legacy files directly via UI and trigger analysis workflows.

---

## 🚀 Running the Dashboard

Launch directly from the repository root:
```bash
streamlit run src/dashboard/app.py
```
Or via the main CLI:
```bash
python main.py --dashboard
```

---

## 📁 Files

- [`app.py`](file:///c:/Users/PrajwalP/Documents/GenAI%20-%20UC2/src/dashboard/app.py): The main Streamlit web application script.
