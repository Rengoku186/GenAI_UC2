from typing import Dict, Any

from langgraph.graph import StateGraph, START, END

from src.state import PipelineState
from src.schemas import Chunk

from src.tools.dependency_scanner import (
    scan_project,
    detect_language,
)

from src.agents.splitter import (
    create_chunk_from_node_data,
    split_chunk_if_oversized,
)


# ============================================================
# SCANNER NODE
# ============================================================
#
# Demo flow:
#
#   File
#     ↓
#   Language Detection
#     ↓
#   Legacy Code Scanner
#     ↓
#   Logical Chunks
#     ↓
#   Oversized Chunk Splitting
#     ↓
#   Final Chunks
# ============================================================

def scanner_node(state: PipelineState) -> Dict[str, Any]:

    file_paths = state.get("file_paths", [])

    if not file_paths:
        return {
            "chunks": [],
            "processing_order": [],
            "current_chunk": None,
            "docs": {},
            "eval_scores": {},
            "refine_count": {},
            "flagged_items": [],
        }

    print()
    print("=" * 70)
    print("LEGACY CODE LANGUAGE DETECTION AND CHUNKING DEMO")
    print("=" * 70)

    # --------------------------------------------------------
    # STEP 1: LANGUAGE DETECTION
    # --------------------------------------------------------

    print()
    print("[1] LANGUAGE DETECTION")
    print("-" * 70)

    for file_path in file_paths:

        language = detect_language(file_path)

        print(
            f"File     : {file_path}"
        )

        print(
            f"Language : {language.upper()}"
        )

        print()

    # --------------------------------------------------------
    # STEP 2: SCAN PROJECT
    # --------------------------------------------------------
    #
    # scan_project() uses parse_file_chunks() internally.
    #
    # It creates one graph node for every logical chunk.
    #
    # Example COBOL:
    #
    # MAIN-PARA
    # VALIDATE-INPUT
    # CALC-INTEREST
    # RAISE-ERROR
    #
    # --------------------------------------------------------

    print("[2] LOGICAL CHUNK DETECTION")
    print("-" * 70)

    raw_graph = scan_project(file_paths)

    chunks_list = []

    # --------------------------------------------------------
    # STEP 3: CONVERT GRAPH NODES TO CHUNKS
    # --------------------------------------------------------

    for node_id in raw_graph.nodes:

        node_data = raw_graph.nodes[node_id]

        real_id = str(
            node_data.get(
                "id",
                node_id
            )
        )

        chunk = create_chunk_from_node_data(
            real_id,
            node_data
        )

        # ----------------------------------------------------
        # Display logical chunk information
        # ----------------------------------------------------

        print(
            f"Chunk Name : {chunk.name}"
        )

        print(
            f"Chunk ID   : {chunk.id}"
        )

        print(
            f"File       : {chunk.file_path}"
        )

        print(
            f"Lines      : "
            f"{chunk.start_line}-{chunk.end_line}"
        )

        print(
            f"Dependencies: "
            f"{len(chunk.depends_on)}"
        )

        print()

        # ----------------------------------------------------
        # STEP 4: SPLIT OVERSIZED CHUNK
        # ----------------------------------------------------

        split_chunks = split_chunk_if_oversized(
            chunk,
            max_lines=800
        )

        # ----------------------------------------------------
        # Add final chunks
        # ----------------------------------------------------

        for split_chunk in split_chunks:

            chunks_list.append(
                split_chunk.model_dump()
            )

    # --------------------------------------------------------
    # STEP 5: FINAL CHUNK SUMMARY
    # --------------------------------------------------------

    print()
    print("[3] FINAL CHUNKS AFTER SIZE SPLITTING")
    print("-" * 70)

    for index, chunk_data in enumerate(
        chunks_list,
        start=1
    ):

        chunk = Chunk.model_validate(
            chunk_data
        )

        line_count = (
            chunk.end_line
            - chunk.start_line
            + 1
        )

        print(
            f"{index}. "
            f"{chunk.name} "
            f"[Lines "
            f"{chunk.start_line}-"
            f"{chunk.end_line}] "
            f"({line_count} lines)"
        )

    # --------------------------------------------------------
    # STEP 6: SIZE VALIDATION
    # --------------------------------------------------------

    oversized_chunks = []

    for chunk_data in chunks_list:

        chunk = Chunk.model_validate(
            chunk_data
        )

        line_count = (
            chunk.end_line
            - chunk.start_line
            + 1
        )

        if line_count > 800:

            oversized_chunks.append(
                chunk.id
            )

    print()
    print("[4] SIZE VALIDATION")
    print("-" * 70)

    if oversized_chunks:

        print(
            "FAILED"
        )

        print(
            f"{len(oversized_chunks)} "
            f"chunk(s) are above 800 lines."
        )

    else:

        print(
            "PASSED"
        )

        print(
            "All chunks are <= 800 lines."
        )

    # --------------------------------------------------------
    # STEP 7: PROCESSING ORDER
    # --------------------------------------------------------
    #
    # For this demo we simply process the final chunks in the
    # order in which they were generated.
    #
    # The production version can continue to use the dependency
    # graph / cycle detector for dependency-aware processing.
    # --------------------------------------------------------

    processing_order = [
        chunk["id"]
        for chunk in chunks_list
    ]

    current_chunk = (
        processing_order[0]
        if processing_order
        else None
    )

    # --------------------------------------------------------
    # FINAL SUMMARY
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("DEMO COMPLETED")
    print("=" * 70)

    print(
        f"Files Processed : {len(file_paths)}"
    )

    print(
        f"Final Chunks     : {len(chunks_list)}"
    )

    print("=" * 70)

    # --------------------------------------------------------
    # Return PipelineState-compatible data
    # --------------------------------------------------------

    return {
        "chunks": chunks_list,
        "processing_order": processing_order,
        "current_chunk": current_chunk,

        # These are retained because PipelineState may contain
        # these fields, but they are not used in this demo.
        "docs": {},
        "eval_scores": {},
        "refine_count": {},
        "flagged_items": [],
    }


# ============================================================
# BUILD PHASE 1 DEMO GRAPH
# ============================================================

def build_phase1_graph():

    builder = StateGraph(
        PipelineState
    )


    builder.add_node(
        "scanner",
        scanner_node
    )


    builder.add_edge(
        START,
        "scanner"
    )

    builder.add_edge(
        "scanner",
        END
    )

    return builder.compile()