import os
import sys
import argparse
from typing import List

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath("."))

from src.tools.dependency_scanner import detect_language, parse_file_chunks
from src.schemas import Chunk
from src.agents.splitter import split_chunk_if_oversized

SUPPORTED_EXTENSIONS = ('.cbl', '.cob', '.cobol', '.bas', '.cls', '.vb', '.vbs', '.java')

def find_source_files(target_paths: List[str]) -> List[str]:
    discovered = []
    for path in target_paths:
        if os.path.isfile(path):
            discovered.append(path)
        elif os.path.isdir(path):
            for root, _, files in os.walk(path):
                for f in files:
                    if f.lower().endswith(SUPPORTED_EXTENSIONS):
                        discovered.append(os.path.join(root, f))
    return sorted(discovered)

def run_demo(paths: List[str] = None, max_lines: int = 400):
    if not paths:
        search_dir = "samples" if os.path.exists("samples") else "."
        paths = [search_dir]

    sample_files = find_source_files(paths)

    print("=" * 60)
    print(" 1. DEMONSTRATING DYNAMIC CODE LANGUAGE DETECTION")
    print("=" * 60)

    if not sample_files:
        print(f"No supported source files found in target path(s): {paths}")
        return

    all_parsed_chunks: List[Chunk] = []

    for file_path in sample_files:
        lang = detect_language(file_path)
        print(f"\nFile: {file_path}")
        print(f" -> Detected Language: {lang.upper()}")
        
        raw_chunks = parse_file_chunks(file_path)
        print(f" -> Parsed Chunks ({len(raw_chunks)}):")
        for qid, scope, name, code, start_l, end_l in raw_chunks:
            print(f"    - [{name}] Lines {start_l}-{end_l}")
            all_parsed_chunks.append(Chunk(
                id=qid,
                file_path=file_path,
                scope=scope,
                name=name,
                code=code,
                start_line=start_l,
                end_line=end_l
            ))

    print("\n" + "=" * 60)
    print(" 2. DEMONSTRATING THE SPLITTER AGENT")
    print("=" * 60)

    if not all_parsed_chunks:
        print("No chunks extracted from input files.")
        return

    print(f"\nEvaluating {len(all_parsed_chunks)} parsed chunk(s)...")

    split_occurred = False
    for chunk in all_parsed_chunks:
        line_count = chunk.end_line - chunk.start_line + 1
        if line_count > max_lines:
            split_occurred = True
            print(f"\nOversized Chunk Detected: '{chunk.name}' in {chunk.file_path} ({line_count} lines)")
            split_results = split_chunk_if_oversized(chunk, max_lines=max_lines)
            print(f"Splitter Output: Divided into {len(split_results)} sub-chunks:")
            for idx, sub in enumerate(split_results, 1):
                sub_lines = len(sub.code.splitlines())
                print(f"  Sub-chunk {idx}: ID='{sub.id}' | Lines: {sub.start_line}-{sub.end_line} ({sub_lines} lines)")
            
            reconstituted = "\n".join([sc.code for sc in split_results])
            print(f"Lossless Verification Passed? {reconstituted.strip() == chunk.code.strip()}")

    if not split_occurred:
        # Dynamically select the largest chunk and demonstrate splitting with a lower threshold
        largest_chunk = max(all_parsed_chunks, key=lambda c: c.end_line - c.start_line + 1)
        line_count = largest_chunk.end_line - largest_chunk.start_line + 1
        demo_max = max(2, line_count // 2)
        print(f"\nNo single chunk exceeded {max_lines} lines.")
        print(f"Demonstrating Splitter Agent on largest chunk '{largest_chunk.name}' ({line_count} lines) using threshold max_lines={demo_max}:")
        
        split_results = split_chunk_if_oversized(largest_chunk, max_lines=demo_max)
        print(f"Splitter Output: Divided into {len(split_results)} sub-chunks:")
        for idx, sub in enumerate(split_results, 1):
            sub_lines = len(sub.code.splitlines())
            print(f"  Sub-chunk {idx}: ID='{sub.id}' | Lines: {sub.start_line}-{sub.end_line} ({sub_lines} lines)")
        
        reconstituted = "\n".join([sc.code for sc in split_results])
        print(f"Lossless Verification Passed? {reconstituted.strip() == largest_chunk.code.strip()}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dynamic Code Language Detection & Splitter Agent Demo")
    parser.add_argument(
        "paths",
        nargs="*",
        help="File(s) or directory path(s) to dynamically scan and process (default: samples/)"
    )
    parser.add_argument(
        "--max-lines",
        type=int,
        default=400,
        help="Maximum lines per chunk before splitting (default: 400)"
    )
    args = parser.parse_args()
    run_demo(paths=args.paths, max_lines=args.max_lines)
