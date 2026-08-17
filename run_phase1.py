"""
Standalone Phase 1 test runner — Splitter -> Documenter -> Evaluator -> refine loop.
Does NOT touch main.py or phase2_graph.py (still a stub). Run directly:

    python run_phase1.py
    python run_phase1.py --file samples/cobol/BILL100.cbl samples/vb/SomeModule.bas
    python run_phase1.py --dir samples/cobol
"""
import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.orchestrator.phase1_graph import build_phase1_graph


def collect_default_samples():
    patterns = ["samples/cobol/*", "samples/vb/*", "samples/java/*"]
    files = []
    for p in patterns:
        files.extend(f for f in glob.glob(p) if os.path.isfile(f))
    return files


def main():
    parser = argparse.ArgumentParser(description="Run Phase 1 (understand legacy code) in isolation")
    parser.add_argument("--file", "-f", nargs="+", default=None, help="Specific legacy source file(s)")
    parser.add_argument("--dir", "-d", default=None, help="Run on every file inside this directory")
    args = parser.parse_args()

    if args.dir:
        file_paths = [f for f in glob.glob(os.path.join(args.dir, "*")) if os.path.isfile(f)]
    elif args.file:
        file_paths = args.file
    else:
        file_paths = collect_default_samples()

    if not file_paths:
        print("No input files found. Use --file or --dir to point at legacy source.", file=sys.stderr)
        sys.exit(1)

    print(f"Running Phase 1 on {len(file_paths)} file(s):")
    for f in file_paths:
        print(f"  - {f}")

    graph = build_phase1_graph()

    try:
        result = graph.invoke({"file_paths": file_paths})
    except Exception as e:
        print(f"\n❌ Phase 1 failed: {e}", file=sys.stderr)
        raise

    chunks = result.get("chunks", [])
    docs = result.get("docs", {})
    eval_scores = result.get("eval_scores", {})
    flagged = result.get("flagged_items", [])

    print("\n" + "=" * 60)
    print("PHASE 1 COMPLETE")
    print("=" * 60)
    print(f"Chunks produced:      {len(chunks)}")
    print(f"Chunks documented:    {len(docs)}")
    print(f"Chunks evaluated:     {len(eval_scores)}")
    print(f"Flagged for review:   {len(flagged)}")

    if eval_scores:
        avg = sum(eval_scores.values()) / len(eval_scores)
        print(f"Average eval score:   {avg:.1f}")

    if flagged:
        print("\nFlagged chunks:")
        for item in flagged:
            cid = item.get("chunk_id", "?")
            score = item.get("overall_score", 0.0)
            print(f"  [FLAG] {cid}  (score: {score:.0f})")

    from src.agents.documenter import generate_master_documentation, export_flagged_json_only
    from src.schemas import Chunk, ChunkDoc

    # Convert state dictionaries back to schemas for master documentation
    chunk_objs = [Chunk.model_validate(c) for c in chunks]
    doc_objs = {k: ChunkDoc.model_validate(v) for k, v in docs.items()}

    master_md = generate_master_documentation(
        chunks=chunk_objs,
        docs=doc_objs,
        project_name="Legacy Code System",
    )

    docs_dir = "docs"
    os.makedirs(docs_dir, exist_ok=True)
    doc_path = os.path.join(docs_dir, "documentation.md")
    with open(doc_path, "w", encoding="utf-8") as f:
        f.write(master_md)
    print(f"\n Master Markdown Specification written to: {doc_path}")

    # Export structured review tickets ONLY for flagged chunks
    flagged_out = os.path.join(docs_dir, "flagged_items.json")
    export_flagged_json_only(flagged, flagged_out)

    print("\nTo review flagged items in the dashboard, run:")
    print("  streamlit run src/dashboard/app.py")


if __name__ == "__main__":
    main()