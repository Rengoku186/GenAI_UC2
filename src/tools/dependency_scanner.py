"""Dependency Scanner & Static Analysis Tool for Legacy Codebases.

This module provides AST/regex parsing and dependency graph generation for
legacy multi-language codebases (COBOL, Visual Basic, Java). Language
detection is delegated to `src.parsing.language_detector.LanguageDetector`
(heuristic-first, LLM fallback only when genuinely ambiguous) rather than
reimplemented here - see "What changed" below for why that matters at scale.
"""
from __future__ import annotations

import os
import json
import re
import time
from typing import Dict, List, Optional, Pattern, Set, Tuple

import networkx as nx

from src.parsing.language_detector import EXTENSION_HINTS, LanguageDetector
from src.utils.ast_parsers import (
    parse_java_with_tree_sitter,
    parse_java_with_javalang,
    extract_java_calls_ast,
    parse_vb_blocks,
    parse_cobol_structural,
)
from src.utils.log_config import get_logger
from src.utils.llm import get_llm

logger = get_logger(__name__)

# --- Configuration (env-overridable) ----------------------------------------

PROGRESS_LOG_EVERY = int(os.getenv("SCANNER_PROGRESS_LOG_EVERY", "50"))
# Defensive guard for pathologically large legacy extracts - a multi-hundred
# MB single file is more likely a data dump than source code; skip it with a
# clear log rather than reading it entirely into memory unbounded.
MAX_FILE_SIZE_BYTES = int(os.getenv("SCANNER_MAX_FILE_SIZE_BYTES", str(50 * 1024 * 1024)))  # 50MB

# ============================================================================
# Parsing Regex Patterns
# ============================================================================

CALL_PATTERNS: Dict[str, Pattern] = {
    "cobol": re.compile(r"\b(?:CALL|PERFORM)\s+['\"]?([\w-]+)['\"]?", re.IGNORECASE),
    "vb": re.compile(r"\b(?:Call|GoSub)\s+([a-zA-Z_]\w*)", re.IGNORECASE),
    "java": re.compile(r"\b([a-zA-Z_]\w*)\s*\(", re.IGNORECASE),
}

DEF_PATTERNS: Dict[str, Pattern] = {
    "cobol": re.compile(
        r"^\s*([\w-]+)(?:\s+SECTION)?\.\s*$",
        re.MULTILINE | re.IGNORECASE,
    ),
    "vb": re.compile(
        r"^\s*(?:(?:Public|Private|Friend|Static|Default)\s+)*(?:Sub|Function|Property\s+(?:Get|Let|Set))\s+([a-zA-Z_]\w*)",
        re.MULTILINE | re.IGNORECASE,
    ),
    "java": re.compile(
        r"(?:(?:public|private|protected|static|final|native|synchronized|abstract|default)\s+)*(?:<[\w,\s?]+>\s+)?(?:[a-zA-Z_][\w<>\[\].]*\s+)?([a-zA-Z_]\w*)\s*\([^;{}]*\)\s*(?:throws\s+[\w,\s]+)?\s*\{",
        re.MULTILINE,
    ),
}

KEYWORDS_IGNORE: Set[str] = {
    # COBOL keywords & verbs
    "IF", "THEN", "ELSE", "END-IF", "STOP", "RUN", "MOVE", "TO", "COMPUTE",
    "DISPLAY", "ADD", "SUBTRACT", "MULTIPLY", "DIVIDE", "INITIALIZE",
    "SET", "GO", "GOTO", "CONTINUE", "NEXT", "SENTENCE", "SECTION",
    "DIVISION", "PROCEDURE", "DATA", "WORKING-STORAGE", "IDENTIFICATION",
    "ENVIRONMENT", "PROGRAM-ID", "EXIT", "GOBACK", "ACCEPT", "OPEN", "CLOSE",
    "READ", "WRITE", "REWRITE", "DELETE", "EVALUATE", "WHEN", "END-EVALUATE",
    "END-PERFORM", "END-CALL", "STRING", "UNSTRING", "INSPECT", "SEARCH",
    # VB / VBA keywords
    "SUB", "FUNCTION", "END", "DIM", "LET", "GET", "CONST",
    "PUBLIC", "PRIVATE", "FRIEND", "STATIC", "OPTION", "EXPLICIT", "AS",
    "INTEGER", "BOOLEAN", "DOUBLE", "LONG", "VARIANT", "OBJECT",
    "FOR", "EACH", "IN", "WHILE", "WEND", "DO", "LOOP", "UNTIL",
    "SELECT", "CASE", "ON", "ERROR", "RESUME", "MSGBOX", "INPUTBOX",
    "NOT", "AND", "OR", "XOR", "EQV", "IMP", "TRUE", "FALSE", "NOTHING",
    "NULL", "EMPTY", "ME", "NEW", "TYPEOF", "IS", "WITH",
    # Java keywords & common primitives / flow control
    "PROTECTED", "FINAL", "VOID", "RETURN",
    "CLASS", "INTERFACE", "ENUM", "RECORD", "PACKAGE", "IMPORT", "EXTENDS",
    "IMPLEMENTS", "THROWS", "THROW", "TRY", "CATCH", "FINALLY",
    "THIS", "SUPER", "INSTANCEOF", "SYNCHRONIZED",
    "VOLATILE", "TRANSIENT", "NATIVE", "ABSTRACT", "STRICTFP", "DEFAULT",
    "SWITCH", "BREAK",
    "SYSTEM", "OUT", "ERR", "PRINTLN", "PRINT", "PRINTF", "EQUALS", "TOSTRING",
    "HASHCODE", "GETCLASS", "CLONE", "NOTIFY", "NOTIFYALL", "WAIT",
}

# Module-level shared detector instance - has its own content-hash cache, so
# identical file content across a large scan is never re-classified twice.
_default_detector = LanguageDetector()
# Legacy callers historically imported this cache directly.  Keep the public
# name while the production scanner uses ``LanguageDetector``'s content-hash
# cache internally.
_LANGUAGE_DETECTION_CACHE: Dict[str, str] = {}


# ============================================================================
# Safe File IO
# ============================================================================

def _read_file_safe(file_path: str) -> Optional[str]:
    """Reads a file with multi-encoding fallback, and a size guard against
    pathologically large files that are more likely data dumps than source."""
    if not os.path.exists(file_path):
        logger.warning("File not found: %s", file_path)
        return None
    if os.path.isdir(file_path):
        logger.warning("Path is a directory, not a file: %s", file_path)
        return None

    try:
        size = os.path.getsize(file_path)
        if size > MAX_FILE_SIZE_BYTES:
            logger.warning(
                "File exceeds size guard (%d bytes > %d), skipping: %s",
                size, MAX_FILE_SIZE_BYTES, file_path,
            )
            return None
    except OSError as exc:
        logger.warning("Could not stat file %s: %s", file_path, exc)

    encodings = ["utf-8", "latin-1", "cp1252"]
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, LookupError):
            continue
        except OSError as exc:
            logger.error("Failed to read file %s with %s: %s", file_path, enc, exc)
            break

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except OSError as exc:
        logger.error("Critical error reading file %s: %s", file_path, exc)
        return None


def detect_language_by_extension(file_path: str) -> str:
    """Return the supported-language hint implied by ``file_path``'s suffix."""
    return EXTENSION_HINTS.get(os.path.splitext(file_path)[1].lower(), "unknown")


def detect_language_with_ai(code_content: str, file_path: str = "") -> Optional[str]:
    """Compatibility helper for callers that explicitly request LLM detection.

    The normal scanner deliberately does not call this per file: it uses
    deterministic content classification first and only falls back to an LLM
    when confidence is low.  This helper remains available for integrations
    that need an explicit model-only classification attempt.
    """
    prompt = (
        "Classify this source as exactly one of cobol, vb, java, mixed, or unknown. "
        "Return only JSON with a language field.\n"
        f"FILE: {file_path}\nCODE:\n{code_content[:6000]}"
    )
    try:
        response = get_llm(temperature=0.0).invoke([("human", prompt)])
        raw = response.content if hasattr(response, "content") else str(response)
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.IGNORECASE)
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        data = json.loads(match.group(0) if match else cleaned)
    except Exception as exc:  # noqa: BLE001 - explicit AI detection is best effort
        logger.warning("LLM language detection failed for %s: %s", file_path, exc)
        return None

    aliases = {
        "visual basic": "vb", "visualbasic": "vb", "vba": "vb", "vb6": "vb",
        "cobol": "cobol", "java": "java", "mixed": "mixed", "unknown": "unknown",
    }
    return aliases.get(str(data.get("language", "")).strip().lower())


def detect_language(file_path: str, code_content: Optional[str] = None, use_ai: bool = True) -> str:
    """Thin delegator to the shared, heuristic-first LanguageDetector.

    NOTE: this used to be a bespoke implementation that called an LLM on
    EVERY file when use_ai=True, with no heuristic pre-check. That's a
    significant cost/latency regression at scale - most files' languages are
    obvious from content alone. Delegating here restores the two-tier
    strategy: cheap regex signature scoring first, LLM only when genuinely
    ambiguous (see language_detector.py for the confidence threshold).
    """
    detector = _default_detector if use_ai else LanguageDetector(use_llm_fallback=False)
    content = code_content if code_content is not None else _read_file_safe(file_path)
    if content is None:
        return "unknown"
    return detector.detect(file_path, content).language


# ============================================================================
# File Chunk Parsing
# ============================================================================

def parse_file_chunks(
    file_path: str,
    code_content: Optional[str] = None,
    language: Optional[str] = None,
    use_ai: bool = True,
) -> List[Tuple[str, str, str, str, int, int]]:
    """Parse a source file into functional units (paragraphs, subroutines, methods).

    Returns list of tuples: (qualified_id, scope, name, code_snippet, start_line, end_line)
    """
    content = code_content if code_content is not None else _read_file_safe(file_path)
    if content is None:
        logger.error("Cannot parse chunks: file unreadable %s", file_path)
        return []

    lines = content.splitlines()
    total_lines = max(1, len(lines))
    lang = language or detect_language(file_path, code_content=content, use_ai=use_ai)
    file_basename = os.path.basename(file_path)
    chunks: List[Tuple[str, str, str, str, int, int]] = []

    # ------------------------------------------------------------------------
    # 1. COBOL Parsing (Structural Parser -> Regex Fallback)
    # ------------------------------------------------------------------------
    if lang == "cobol":
        cobol_chunks = parse_cobol_structural(file_path, content)
        if cobol_chunks:
            chunks.extend(cobol_chunks)
        else:
            program_match = re.search(r"PROGRAM-ID\.\s*([\w-]+)", content, re.IGNORECASE)
            scope = program_match.group(1).upper() if program_match else os.path.splitext(file_basename)[0]

            proc_div_idx = -1
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith("*") or (len(line) > 6 and line[6] == "*"):
                    continue
                if re.search(r"\bPROCEDURE\s+DIVISION\b", line, re.IGNORECASE):
                    proc_div_idx = i
                    break

            if proc_div_idx != -1:
                para_matches: List[Tuple[str, int]] = []
                for i in range(proc_div_idx + 1, len(lines)):
                    line = lines[i]
                    stripped = line.strip()
                    if stripped.startswith("*") or (len(line) > 6 and line[6] == "*"):
                        continue
                    m = re.match(r"^\s*([\w-]+)(?:\s+SECTION)?\.\s*$", line, re.IGNORECASE)
                    if m:
                        pname = m.group(1).upper()
                        if pname not in KEYWORDS_IGNORE and pname not in {
                            "PROCEDURE", "DIVISION", "DATA", "WORKING-STORAGE",
                            "IDENTIFICATION", "ENVIRONMENT", "CONFIGURATION",
                            "INPUT-OUTPUT", "FILE", "LOCAL-STORAGE", "LINKAGE", "SECTION"
                        }:
                            para_matches.append((pname, i + 1))

                for idx, (pname, start_l) in enumerate(para_matches):
                    end_l = para_matches[idx + 1][1] - 1 if idx + 1 < len(para_matches) else total_lines
                    chunk_code = "\n".join(lines[start_l - 1:end_l])
                    qid = f"{file_path}::{scope}::{pname}"
                    chunks.append((qid, scope, pname, chunk_code, start_l, end_l))

    # ------------------------------------------------------------------------
    # 2. Visual Basic Parsing (Block Parser -> Regex Fallback)
    # ------------------------------------------------------------------------
    elif lang == "vb":
        vb_chunks = parse_vb_blocks(file_path, content)
        if vb_chunks:
            chunks.extend(vb_chunks)
        else:
            attr_match = re.search(r'Attribute\s+VB_Name\s*=\s*"([^"]+)"', content, re.IGNORECASE)
            scope = attr_match.group(1) if attr_match else os.path.splitext(file_basename)[0]
            pattern = DEF_PATTERNS["vb"]
            matches = list(pattern.finditer(content))
            for idx, m in enumerate(matches):
                fname = m.group(1)
                start_l = content[:m.start()].count("\n") + 1
                end_l = content[:matches[idx + 1].start()].count("\n") if idx + 1 < len(matches) else total_lines
                chunk_code = "\n".join(lines[start_l - 1:end_l])
                qid = f"{file_path}::{scope}::{fname}"
                chunks.append((qid, scope, fname, chunk_code, start_l, end_l))

    # ------------------------------------------------------------------------
    # 3. Java Parsing (Tree-sitter AST -> Javalang -> Regex Fallback)
    # ------------------------------------------------------------------------
    elif lang == "java":
        java_chunks = parse_java_with_tree_sitter(file_path, content)
        if not java_chunks:
            java_chunks = parse_java_with_javalang(file_path, content)

        if java_chunks:
            chunks.extend(java_chunks)
        else:
            pkg_match = re.search(r"package\s+([\w\.]+);", content)
            class_match = re.search(r"(?:public\s+|private\s+|protected\s+|abstract\s+|final\s+)*(?:class|interface|enum|record)\s+(\w+)", content)
            class_name = class_match.group(1) if class_match else os.path.splitext(file_basename)[0]
            scope = f"{pkg_match.group(1)}.{class_name}" if pkg_match else class_name
            pattern = DEF_PATTERNS["java"]
            matches = list(pattern.finditer(content))
            for idx, m in enumerate(matches):
                mname = m.group(1)
                if mname in {"if", "while", "for", "switch", "catch", "synchronized", "try", "finally"}:
                    continue
                start_l = content[:m.start()].count("\n") + 1
                end_l = content[:matches[idx + 1].start()].count("\n") if idx + 1 < len(matches) else total_lines
                chunk_code = "\n".join(lines[start_l - 1:end_l])
                qid = f"{file_path}::{scope}::{mname}"
                chunks.append((qid, scope, mname, chunk_code, start_l, end_l))

    # ------------------------------------------------------------------------
    # Fallback: Whole-file MAIN chunk (also covers "mixed"/"unknown" languages)
    # ------------------------------------------------------------------------
    if not chunks:
        scope = os.path.splitext(file_basename)[0]
        qid = f"{file_path}::{scope}::MAIN"
        chunks.append((qid, scope, "MAIN", content, 1, total_lines))

    return chunks


# ============================================================================
# Dependency Graph Builder
# ============================================================================

def scan_project(file_paths: List[str], use_ai: bool = True) -> nx.DiGraph:
    """Analyze source files and generate a directed dependency graph.

    Performs a 2-pass static analysis:
    - Pass 1: registers all functional units into a symbol registry.
    - Pass 2: resolves call references to qualified IDs and builds edges.

    One bad file can't abort the whole scan - read/parse failures are caught,
    logged, and skipped, with a summary of failures logged at the end.
    """
    graph = nx.DiGraph()
    exact_registry: Dict[str, str] = {}
    name_to_qids: Dict[str, List[str]] = {}
    all_chunks_info: List[Tuple[str, str, str, str, str]] = []
    failed_files: List[Tuple[str, str]] = []

    total_files = len(file_paths)
    scan_start = time.perf_counter()
    logger.info("Starting static dependency scan for %d file(s)", total_files)

    # ------------------------------------------------------------------------
    # PASS 1: Node Registration & Registry Construction
    # ------------------------------------------------------------------------
    for i, path in enumerate(file_paths, start=1):
        if not os.path.exists(path):
            logger.warning("Skipping missing path during scan: %s", path)
            failed_files.append((path, "path does not exist"))
            continue

        try:
            content = _read_file_safe(path)
            if content is None:
                failed_files.append((path, "unreadable or exceeds size guard"))
                continue

            lang = detect_language(path, code_content=content, use_ai=use_ai)
            parsed_chunks = parse_file_chunks(path, code_content=content, language=lang, use_ai=use_ai)

            for qid, scope, name, code, s_line, e_line in parsed_chunks:
                graph.add_node(
                    qid, file_path=path, scope=scope, name=name, code=code,
                    language=lang, start_line=s_line, end_line=e_line,
                    depends_on=[], unresolved=[],
                )
                name_upper = name.upper()
                exact_registry[qid.upper()] = qid
                exact_registry[f"{scope}::{name}".upper()] = qid
                exact_registry[f"{path}::{name}".upper()] = qid
                name_to_qids.setdefault(name_upper, []).append(qid)
                all_chunks_info.append((qid, path, lang, code, name))

        except Exception as exc:  # noqa: BLE001 - isolate one bad file
            logger.error("Failed to scan file, skipping: %s (%s)", path, exc, exc_info=True)
            failed_files.append((path, str(exc)))
            continue

        if PROGRESS_LOG_EVERY and i % PROGRESS_LOG_EVERY == 0:
            logger.info("Scan progress: %d/%d files processed", i, total_files)

    logger.debug("Pass 1 completed: registered %d chunk nodes", len(graph.nodes))

    # ------------------------------------------------------------------------
    # PASS 2: Call Analysis & Edge Construction
    # ------------------------------------------------------------------------
    for qid, path, lang, code, current_name in all_chunks_info:
        raw_called_names: List[str] = []

        if lang == "java":
            try:
                ast_calls = extract_java_calls_ast(code)
            except Exception as exc:  # noqa: BLE001
                logger.debug("AST call extraction failed for %s: %s", qid, exc)
                ast_calls = None
            if ast_calls is not None:
                raw_called_names = ast_calls

        if not raw_called_names:
            pattern = CALL_PATTERNS.get(lang)
            if pattern:
                matches = pattern.findall(code)
                raw_called_names = [m[1] if isinstance(m, tuple) else m for m in matches]

        unresolved_list: List[str] = []
        depends_on_set: Set[str] = set()
        same_file_key = f"{path}::"

        for called_name in raw_called_names:
            called_name = called_name.strip()
            called_upper = called_name.upper()
            if not called_name or called_upper in KEYWORDS_IGNORE or called_upper == current_name.upper():
                continue

            target_qid: Optional[str] = None

            # Disambiguation hierarchy, cheapest/most-specific first - each
            # of these is now an O(1) dict lookup. The original implementation
            # scanned the ENTIRE exact_registry with .endswith() string
            # comparisons for step 1 on every single call reference, which is
            # O(chunks x registry size) - a serious bottleneck at scale, and
            # unnecessary since Pass 1 already registers the exact key this
            # step needs.
            # 1. Exact same-file match (the key Pass 1 already registers).
            target_qid = exact_registry.get(f"{same_file_key}{called_name}".upper())

            # 2. Exact scope::name match.
            if not target_qid:
                target_qid = exact_registry.get(called_upper)

            # 3. Any-file name match, preferring same-file if ambiguous.
            if not target_qid and called_upper in name_to_qids:
                matching_qids = name_to_qids[called_upper]
                same_file_qids = [q for q in matching_qids if q.startswith(same_file_key)]
                if same_file_qids:
                    target_qid = same_file_qids[0]
                elif len(matching_qids) == 1:
                    target_qid = matching_qids[0]

            if target_qid and target_qid != qid:
                graph.add_edge(qid, target_qid)
                depends_on_set.add(target_qid)
            elif called_upper not in KEYWORDS_IGNORE and len(called_name) > 1:
                unresolved_list.append(called_name)

        graph.nodes[qid]["depends_on"] = sorted(depends_on_set)
        graph.nodes[qid]["unresolved"] = sorted(set(unresolved_list))

    elapsed_s = round(time.perf_counter() - scan_start, 2)
    logger.info(
        "Scan complete: %d nodes, %d edges, %d file(s) failed, in %ss",
        graph.number_of_nodes(), graph.number_of_edges(), len(failed_files), elapsed_s,
    )
    if failed_files:
        logger.warning("%d file(s) could not be scanned: %s", len(failed_files), [p for p, _ in failed_files])

    return graph
