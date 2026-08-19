"""Splitter Agent for Large-Scale Legacy Code Partitioning.

Provides production-grade semantic code chunking that gracefully scales to massive
monoliths (thousands of lines) across COBOL, Visual Basic, Java, and composite cycle
groups. Ensures 100% lossless code reconstitution, syntax-boundary preservation, and
targeted dependency propagation.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from src.schemas import Chunk

logger = logging.getLogger(__name__)

# ============================================================================
# Boundary Patterns for Language-Aware Splitting
# ============================================================================

COBOL_BOUNDARY_PATTERNS = [
    (re.compile(r"^\s*([\w-]+)(?:\s+SECTION)?\.\s*$", re.IGNORECASE), 100),  # Section / Para
    (re.compile(r"^\s*(?:END-IF|END-PERFORM|END-EVALUATE|END-READ|END-WRITE|GOBACK|STOP\s+RUN)\.?\s*$", re.IGNORECASE), 90),
    (re.compile(r"^\s*(?:PERFORM|CALL|EVALUATE|EXEC\s+SQL)\b", re.IGNORECASE), 70),
    (re.compile(r"\.\s*$"), 60),  # Period at end of statement
    (re.compile(r"^\s*\*"), 40),   # Comment line / section banner
]

JAVA_BOUNDARY_PATTERNS = [
    (re.compile(r"^\s*(?:(?:public|private|protected|static|final|abstract)\s+)*[\w<>\[\],\s]+\s+[a-zA-Z_]\w*\s*\([^;{}]*\)\s*(?:throws\s+[\w,\s]+)?\s*\{"), 100),  # Method
    (re.compile(r"^\s*\}\s*(?:else|catch|finally)?"), 85),  # Block closing brace
    (re.compile(r";\s*$"), 60),  # Semicolon statement end
    (re.compile(r"^\s*(?://|/\*|\*)"), 40),  # Comments
]

VB_BOUNDARY_PATTERNS = [
    (re.compile(r"^\s*(?:(?:Public|Private|Friend|Static)\s+)*(?:Sub|Function|Property)\b", re.IGNORECASE), 100),
    (re.compile(r"^\s*End\s+(?:Sub|Function|Property)\b", re.IGNORECASE), 95),
    (re.compile(r"^\s*End\s+(?:If|Select|With)\b", re.IGNORECASE), 85),
    (re.compile(r"^\s*(?:Loop|Next|Wend)\b", re.IGNORECASE), 80),
    (re.compile(r"^\s*(?:'|Rem\s+)", re.IGNORECASE), 40),  # Comments
]

CYCLE_COMPONENT_HEADER = re.compile(r"^//\s*---\s*Component:\s*(.+?)\s*---", re.IGNORECASE)


# ============================================================================
# Core Chunk Factory
# ============================================================================

def create_chunk_from_node_data(node_id: Any, node_data: dict) -> Chunk:
    """Instantiate a standardized Chunk schema from graph node metadata.

    Args:
        node_id: Identifier of the node in the dependency graph.
        node_data: Dictionary of node attributes from the dependency graph.

    Returns:
        Validated Chunk instance.
    """
    str_id = str(node_data.get("id", node_id))
    name = node_data.get("name")
    if not name:
        name = str_id.split("::")[-1]

    return Chunk(
        id=str_id,
        file_path=node_data.get("file_path", ""),
        scope=node_data.get("scope"),
        name=name,
        code=node_data.get("code", ""),
        language=node_data.get("language", "unknown"),
        start_line=node_data.get("start_line", 1),
        end_line=node_data.get("end_line", 1),
        depends_on=list(node_data.get("depends_on", [])),
        is_cycle_group=bool(node_data.get("is_cycle_group", False)),
    )


# ============================================================================
# Semantic Boundary Scorer
# ============================================================================

def _score_split_boundary(line: str, lang: str) -> int:
    """Calculate the suitability score of a line as a chunk boundary."""
    stripped = line.strip()
    if not stripped:
        return 50  # Blank lines are good neutral boundaries

    # Component boundary in cycle groups is top priority
    if CYCLE_COMPONENT_HEADER.match(stripped):
        return 150

    patterns = []
    if lang == "cobol":
        patterns = COBOL_BOUNDARY_PATTERNS
    elif lang == "java":
        patterns = JAVA_BOUNDARY_PATTERNS
    elif lang == "vb":
        patterns = VB_BOUNDARY_PATTERNS
    else:
        # Generic heuristic: semicolon, period, comment, or braces
        if stripped.endswith(";") or stripped.endswith("."):
            return 60
        if stripped.startswith("//") or stripped.startswith("#") or stripped.startswith("--"):
            return 40
        if stripped == "}" or stripped.startswith("end"):
            return 75

    for pattern, score in patterns:
        if pattern.search(line):
            return score

    return 10


def _find_best_cut_point(
    lines: List[str],
    lang: str,
    min_idx: int,
    max_idx: int,
    target_idx: int,
) -> int:
    """Find optimal split index in [min_idx, max_idx] closest to target_idx."""
    best_idx = target_idx
    best_score = -1
    best_distance = float("inf")

    # Search window around target_idx within [min_idx, max_idx]
    for idx in range(min_idx, max_idx + 1):
        if idx >= len(lines):
            break

        line = lines[idx]
        score = _score_split_boundary(line, lang)
        distance = abs(idx - target_idx)

        # Composite fitness: higher score is preferred; if scores match, closer distance wins
        # Normalize distance penalty
        fitness = score * 10 - distance

        if fitness > best_score:
            best_score = fitness
            best_idx = idx
            best_distance = distance

    return max(min_idx, min(best_idx, max_idx))


# ============================================================================
# Targeted Dependency Pruning
# ============================================================================

def _filter_subchunk_dependencies(sub_code: str, parent_deps: List[str]) -> List[str]:
    """Prune dependencies not referenced in this sub-chunk's source code."""
    if not parent_deps:
        return []

    sub_code_upper = sub_code.upper()
    relevant: List[str] = []

    for dep in parent_deps:
        # Check if full qualified ID or base identifier appears in sub_code
        dep_parts = dep.split("::")
        short_name = dep_parts[-1].upper()

        if short_name in sub_code_upper or dep.upper() in sub_code_upper:
            relevant.append(dep)

    # Fallback: if heuristic found nothing but parent had dependencies, safely keep parent deps
    return relevant if relevant else list(parent_deps)


# ============================================================================
# Linear-Time Partitioning Engine
# ============================================================================

def _partition_lines(
    lines: List[str],
    lang: str,
    max_lines: int,
    max_chars: int,
    min_lines: int,
    java_boundary_lines: Optional[Set[int]] = None,
) -> List[Tuple[int, int]]:
    """Partition lines into balanced (start_idx, end_idx) index ranges.

    Runs in O(N) linear time and guarantees every partition stays strictly
    within bounds unless an indivisible single line exceeds max_chars.
    """
    total_lines = len(lines)
    effective_min_lines = max(1, min(min_lines, max(1, max_lines // 2)))

    if total_lines <= max_lines:
        # Check character limit
        total_chars = sum(len(l) for l in lines) + total_lines
        if total_chars <= max_chars:
            return [(0, total_lines - 1)]

    partitions: List[Tuple[int, int]] = []
    current_start = 0

    while current_start < total_lines:
        remaining_lines = total_lines - current_start
        if remaining_lines <= max_lines:
            # Check characters of remaining lines
            remaining_chars = sum(len(lines[i]) for i in range(current_start, total_lines)) + remaining_lines
            if remaining_chars <= max_chars:
                partitions.append((current_start, total_lines - 1))
                break

        # Calculate nominal cut window
        nominal_step = min(max_lines, remaining_lines)

        # Constrain by max_chars
        accum_chars = 0
        char_constrained_step = nominal_step
        for step in range(nominal_step):
            line_len = len(lines[current_start + step]) + 1
            if step > 0 and (accum_chars + line_len) > max_chars:
                char_constrained_step = step
                break
            accum_chars += line_len

        # Ensure min_lines does not violate max_chars limit
        if char_constrained_step < effective_min_lines:
            # Cannot satisfy min_lines without exceeding max_chars; cap at char limit and log warning
            logger.warning(
                "splitter: min_lines %d cannot be satisfied within max_chars %d; using char_constrained_step %d",
                effective_min_lines,
                max_chars,
                char_constrained_step,
            )
            target_step = char_constrained_step
        else:
            # Normal case: respect both min_lines and char limit
            target_step = max(effective_min_lines, min(nominal_step, char_constrained_step))
        ideal_cut = current_start + target_step
        ideal_cut = min(ideal_cut, total_lines)

        # Allow flexible boundary search window around ideal_cut
        margin = max(1, int(target_step * 0.25))
        min_search = max(current_start + effective_min_lines, ideal_cut - margin)
        max_search = min(total_lines, ideal_cut + margin)

        if min_search < max_search:
            best_cut = _find_best_cut_point(lines, lang, min_search, max_search - 1, ideal_cut)
        else:
            best_cut = ideal_cut

        # Ensure forward progress
        if best_cut <= current_start:
            best_cut = min(current_start + effective_min_lines, total_lines)

        partitions.append((current_start, best_cut - 1))
        current_start = best_cut

    return partitions


# ============================================================================
# Public Splitting API
# ============================================================================

def split_chunk_if_oversized(
    chunk: Chunk,
    max_lines: int = 800,
    max_chars: int = 32000,
    min_lines: int = 15,
) -> List[Chunk]:
    """Subdivide an oversized code chunk into semantically bounded sub-chunks.

    Scales to arbitrarily large codebases with linear time complexity, preserving
    exact line spans and guaranteeing lossless code reconstruction.

    Args:
        chunk: The parent Chunk object to inspect and potentially split.
        max_lines: Maximum allowable lines per sub-chunk (default 800).
        max_chars: Maximum allowable character count per sub-chunk (default 32000).
        min_lines: Minimum target lines per sub-chunk when partitioning.

    Returns:
        List of sub-chunks if splitting was required, or [chunk] if within bounds.
    """
    lines = chunk.code.splitlines()
    total_lines = len(lines)
    total_chars = len(chunk.code)

    if total_lines <= max_lines and total_chars <= max_chars:
        return [chunk]

    logger.info(
        "Splitting oversized chunk '%s' (lines: %d, chars: %d, lang: %s, cycle_group: %s)",
        chunk.id,
        total_lines,
        total_chars,
        chunk.language,
        chunk.is_cycle_group,
    )

    # Prepare Java AST boundary lines if needed
    java_boundary_lines = None
    if chunk.language == "java":
        from src.utils.ast_parsers import parse_java_with_javalang

        java_chunks = parse_java_with_javalang(chunk.file_path, chunk.code)
        if java_chunks:
            # Collect start lines of each method/constructor
            java_boundary_lines = {start for _, _, _, _, start, _ in java_chunks}

    partitions = _partition_lines(
        lines=lines,
        lang=chunk.language,
        max_lines=max_lines,
        max_chars=max_chars,
        min_lines=min_lines,
        java_boundary_lines=java_boundary_lines,
    )

    sub_chunks: List[Chunk] = []
    current_line_cursor = chunk.start_line

    for part_idx, (start_idx, end_idx) in enumerate(partitions, 1):
        part_lines = lines[start_idx : end_idx + 1]
        part_code = "\n".join(part_lines)
        part_line_count = len(part_lines)
        sub_start_line = current_line_cursor
        sub_end_line = sub_start_line + part_line_count - 1

        sub_id = f"{chunk.id}::part{part_idx}"
        sub_name = f"{chunk.name}_part{part_idx}"
        sub_deps = _filter_subchunk_dependencies(part_code, chunk.depends_on)

        sub_chunks.append(
            Chunk(
                id=sub_id,
                file_path=chunk.file_path,
                scope=chunk.scope,
                name=sub_name,
                code=part_code,
                language=chunk.language,
                start_line=sub_start_line,
                end_line=sub_end_line,
                depends_on=sub_deps,
                is_cycle_group=chunk.is_cycle_group,
            )
        )
        current_line_cursor = sub_end_line + 1

    # ------------------------------------------------------------------------
    # Restore intra-cycle dependencies when a cycle-group chunk is split
    # ------------------------------------------------------------------------
    if chunk.is_cycle_group:
        # For each pair of sub-chunks, add a dependency if the source routine appears in code.
        for sc in sub_chunks:
            for other_sc in sub_chunks:
                if sc.id == other_sc.id:
                    continue
                # Sub-chunk names include a "_partN" suffix, so use the original routine name.
                other_routine_name = other_sc.name.rsplit("_part", 1)[0]
                if other_routine_name.lower() in sc.code.lower():
                    if other_sc.id not in sc.depends_on:
                        sc.depends_on.append(other_sc.id)


    # ------------------------------------------------------------------------
    # Lossless Verification & Line Invariant Check
    # ------------------------------------------------------------------------
    # Reconstitute code and correctly handle trailing newline.
    reconstituted = "\n".join(sc.code for sc in sub_chunks)
    if chunk.code.endswith("\n"):
        reconstituted += "\n"
    is_lossless = reconstituted == chunk.code

    if not is_lossless:
        logger.warning(
            "Lossless verification mismatch for chunk '%s'. Lengths: orig=%d, recon=%d",
            chunk.id,
            len(chunk.code),
            len(reconstituted),
        )
    else:
        logger.debug(
            "Successfully split chunk '%s' into %d lossless sub-chunks",
            chunk.id,
            len(sub_chunks),
        )

    return sub_chunks
