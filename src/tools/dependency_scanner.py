"""Dependency Scanner & Static Analysis Tool for Legacy Codebases.

This module provides production-grade AST/regex parsing and dynamic dependency
graph generation for legacy multi-language codebases (COBOL, Visual Basic, Java).
It supports AI-powered language detection with resilient fallback to extension-based
heuristics, robust file handling across varied encodings, and intelligent symbol
disambiguation for cross-file and intra-file call references.
"""

from __future__ import annotations

import functools
import hashlib
import json
import logging
import os
import re
from typing import Dict, List, Optional, Pattern, Set, Tuple, Union

import networkx as nx

from src.utils.llm import get_llm
from src.utils.ast_parsers import (
    parse_java_with_tree_sitter,
    parse_java_with_javalang,
    extract_java_calls_ast,
    parse_vb_blocks,
    parse_cobol_structural,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Supported Languages & Canonical Mappings
# ============================================================================

SUPPORTED_LANGUAGES: Set[str] = {"cobol", "vb", "java"}

EXTENSION_LANGUAGE_MAP: Dict[str, str] = {
    # COBOL
    ".cbl": "cobol",
    ".cob": "cobol",
    ".cobol": "cobol",
    ".cpy": "cobol",
    ".pco": "cobol",
    # Visual Basic / VBA / VBScript
    ".bas": "vb",
    ".cls": "vb",
    ".vb": "vb",
    ".vbs": "vb",
    ".frm": "vb",
    ".ctl": "vb",
    ".vba": "vb",
    # Java
    ".java": "java",
    ".jav": "java",
}

LANGUAGE_ALIASES: Dict[str, str] = {
    "cobol": "cobol",
    "cbl": "cobol",
    "cob": "cobol",
    "open-cobol": "cobol",
    "gnu-cobol": "cobol",
    "mainframe cobol": "cobol",
    "micro focus cobol": "cobol",
    "vb": "vb",
    "visual basic": "vb",
    "visualbasic": "vb",
    "vb6": "vb",
    "vba": "vb",
    "vb.net": "vb",
    "vbscript": "vb",
    "vbs": "vb",
    "java": "java",
    "javac": "java",
}

# ============================================================================
# Parsing Regex Patterns
# ============================================================================

CALL_PATTERNS: Dict[str, Pattern] = {
    "cobol": re.compile(
        r"\b(?:CALL|PERFORM)\s+['\"]?([\w-]+)['\"]?",
        re.IGNORECASE,
    ),
    "vb": re.compile(
        r"\b(?:Call|GoSub)\s+([a-zA-Z_]\w*)",
        re.IGNORECASE,
    ),
    "java": re.compile(
        r"\b([a-zA-Z_]\w*)\s*\(",
        re.IGNORECASE,
    ),
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
    "SUB", "FUNCTION", "END", "EXIT", "DIM", "SET", "LET", "GET", "CONST",
    "PUBLIC", "PRIVATE", "FRIEND", "STATIC", "OPTION", "EXPLICIT", "AS",
    "INTEGER", "STRING", "BOOLEAN", "DOUBLE", "LONG", "VARIANT", "OBJECT",
    "FOR", "EACH", "IN", "NEXT", "WHILE", "WEND", "DO", "LOOP", "UNTIL",
    "SELECT", "CASE", "ON", "ERROR", "GOTO", "RESUME", "MSGBOX", "INPUTBOX",
    "NOT", "AND", "OR", "XOR", "EQV", "IMP", "TRUE", "FALSE", "NOTHING",
    "NULL", "EMPTY", "ME", "NEW", "TYPEOF", "IS", "WITH",
    # Java keywords & common primitives / flow control
    "PUBLIC", "PRIVATE", "PROTECTED", "STATIC", "FINAL", "VOID", "RETURN",
    "CLASS", "INTERFACE", "ENUM", "RECORD", "PACKAGE", "IMPORT", "EXTENDS",
    "IMPLEMENTS", "THROWS", "THROW", "TRY", "CATCH", "FINALLY", "NEW",
    "THIS", "SUPER", "NULL", "TRUE", "FALSE", "INSTANCEOF", "SYNCHRONIZED",
    "VOLATILE", "TRANSIENT", "NATIVE", "ABSTRACT", "STRICTFP", "DEFAULT",
    "IF", "ELSE", "SWITCH", "CASE", "BREAK", "CONTINUE", "WHILE", "FOR", "DO",
    "SYSTEM", "OUT", "ERR", "PRINTLN", "PRINT", "PRINTF", "EQUALS", "TOSTRING",
    "HASHCODE", "GETCLASS", "CLONE", "NOTIFY", "NOTIFYALL", "WAIT",
}

# Cache for AI language detection results to avoid redundant model invocations
_LANGUAGE_DETECTION_CACHE: Dict[str, str] = {}


# ============================================================================
# Safe File IO & Utility Helpers
# ============================================================================

def _read_file_safe(file_path: str) -> Optional[str]:
    """Safely read a file with multi-encoding fallback.

    Tries UTF-8 first, followed by Latin-1 and CP1252, falling back to lossy
    character replacement before failing.

    Args:
        file_path: Path to the target file.

    Returns:
        The content of the file as string, or None if the file cannot be read.
    """
    if not os.path.exists(file_path):
        logger.warning("File not found: %s", file_path)
        return None

    if os.path.isdir(file_path):
        logger.warning("Path is a directory, not a file: %s", file_path)
        return None

    encodings = ["utf-8", "latin-1", "cp1252"]
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, LookupError):
            continue
        except Exception as exc:
            logger.error("Failed to read file %s with %s: %s", file_path, enc, exc)
            break

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as exc:
        logger.error("Critical error reading file %s: %s", file_path, exc)
        return None


def _get_content_sample(content: str, max_lines: int = 80, max_chars: int = 2500) -> str:
    """Extract a representative snippet from the beginning of a source file."""
    lines = content.splitlines()[:max_lines]
    sample = "\n".join(lines)
    if len(sample) > max_chars:
        sample = sample[:max_chars]
    return sample


def _canonicalize_language(raw_lang: Optional[str]) -> str:
    """Map raw language string / model output to canonical language name."""
    if not raw_lang:
        return "unknown"
    normalized = raw_lang.strip().lower().replace("_", " ").replace("-", " ")
    for alias, canonical in LANGUAGE_ALIASES.items():
        if alias == normalized or alias in normalized.split():
            return canonical
    return "unknown"


# ============================================================================
# Language Detection (AI + Extension Fallback)
# ============================================================================

def detect_language_by_extension(file_path: str) -> str:
    """Detect language purely based on file extension.

    Args:
        file_path: The file path to inspect.

    Returns:
        One of 'cobol', 'vb', 'java', or 'unknown'.
    """
    ext = os.path.splitext(file_path)[1].lower()
    return EXTENSION_LANGUAGE_MAP.get(ext, "unknown")


def detect_language_with_ai(
    code_snippet: str,
    file_path: Optional[str] = None,
) -> Optional[str]:
    """Detect programming language of a source snippet using LLM analysis.

    Args:
        code_snippet: Source code snippet or header lines.
        file_path: Optional file path or filename to provide additional context.

    Returns:
        Canonical language string ('cobol', 'vb', 'java') or None if detection fails.
    """
    if not code_snippet or not code_snippet.strip():
        return None

    filename_hint = os.path.basename(file_path) if file_path else "unknown_file"

    system_prompt = (
        "You are an expert legacy code analyzer. Analyze the given code snippet "
        "and determine whether it is written in 'cobol', 'vb' (Visual Basic/VBA/VBScript), "
        "or 'java'. If it is none of these, classify it as 'unknown'.\n\n"
        "You MUST respond with ONLY a single JSON object matching this schema:\n"
        '{"language": "cobol" | "vb" | "java" | "unknown", "confidence": float}'
    )

    user_prompt = (
        f"File name hint: {filename_hint}\n\n"
        f"CODE SNIPPET:\n```\n{code_snippet}\n```\n\n"
        "Identify the programming language. Respond strictly with the required JSON object."
    )

    try:
        llm = get_llm(temperature=0.0)
        messages = [
            ("system", system_prompt),
            ("human", user_prompt),
        ]
        response = llm.invoke(messages)
        raw_text = response.content if hasattr(response, "content") else str(response)

        # Clean markdown code fences if present
        clean_text = raw_text.strip()
        clean_text = re.sub(r"^```(?:json)?\s*", "", clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r"\s*```$", "", clean_text)

        parsed: Dict[str, Union[str, float]] = {}
        try:
            parsed = json.loads(clean_text)
        except json.JSONDecodeError:
            json_match = re.search(r"\{.*\}", clean_text, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(0))

        detected = parsed.get("language")
        if detected:
            canonical = _canonicalize_language(str(detected))
            if canonical in SUPPORTED_LANGUAGES:
                return canonical

        # Fallback regex search on raw output if JSON extraction failed
        for lang_option in ("cobol", "java", "vb"):
            if re.search(r"\b" + lang_option + r"\b", raw_text, re.IGNORECASE):
                return lang_option

        return None

    except Exception as exc:
        logger.warning(
            "AI language detection encountered an error for %s: %s. Falling back to extension.",
            filename_hint,
            exc,
        )
        return None


def detect_language(
    file_path: str,
    code_content: Optional[str] = None,
    use_ai: bool = True,
) -> str:
    """Detect language of a file using AI with fallback to file extension.

    Args:
        file_path: Path to the source file.
        code_content: Optional in-memory file content. If None, reads from file_path.
        use_ai: Whether to use LLM-based detection before extension fallback.

    Returns:
        Detected canonical language ('cobol', 'vb', 'java', or 'unknown').
    """
    # Check cache first
    cache_key = file_path
    if code_content is not None:
        content_hash = hashlib.md5(code_content.encode("utf-8", errors="ignore")).hexdigest()
        cache_key = f"{file_path}::{content_hash}"

    if cache_key in _LANGUAGE_DETECTION_CACHE:
        return _LANGUAGE_DETECTION_CACHE[cache_key]

    ext_fallback = detect_language_by_extension(file_path)

    if not use_ai:
        _LANGUAGE_DETECTION_CACHE[cache_key] = ext_fallback
        return ext_fallback

    # Prepare code sample for AI
    content = code_content
    if content is None and os.path.isfile(file_path):
        content = _read_file_safe(file_path)

    if content and content.strip():
        sample = _get_content_sample(content)
        ai_lang = detect_language_with_ai(sample, file_path=file_path)
        if ai_lang and ai_lang in SUPPORTED_LANGUAGES:
            logger.info("AI detected language '%s' for file: %s", ai_lang, file_path)
            _LANGUAGE_DETECTION_CACHE[cache_key] = ai_lang
            return ai_lang

    logger.debug(
        "Using extension fallback '%s' for file: %s",
        ext_fallback,
        file_path,
    )
    _LANGUAGE_DETECTION_CACHE[cache_key] = ext_fallback
    return ext_fallback


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

    Args:
        file_path: Path to the target file.
        code_content: Optional content if already loaded in memory.
        language: Optional language override. If None, automatically detected.
        use_ai: Whether to use AI for language detection if language not supplied.

    Returns:
        List of tuples: (qualified_id, scope, name, code_snippet, start_line, end_line)
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
    # Fallback: Whole-file MAIN chunk
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
    """Analyze source files and generate a comprehensive directed dependency graph.

    Performs a 2-pass static analysis:
    - Pass 1: Registers all functional units across files into a multi-indexed
      symbol registry.
    - Pass 2: Scans invocation patterns, resolves target qualified IDs with
      local-first disambiguation, and establishes directed dependency edges.

    Args:
        file_paths: List of absolute or relative file paths to scan.
        use_ai: Whether to use AI for language detection.

    Returns:
        networkx.DiGraph representing the dependency graph. Each node contains
        'file_path', 'scope', 'name', 'code', 'language', 'start_line', 'end_line',
        'depends_on', and 'unresolved' attributes.
    """
    graph = nx.DiGraph()

    # Symbol Registries for disambiguation
    exact_registry: Dict[str, str] = {}
    name_to_qids: Dict[str, List[str]] = {}
    all_chunks_info: List[Tuple[str, str, str, str, str]] = []

    logger.info("Starting static dependency scan for %d file(s)", len(file_paths))

    # ------------------------------------------------------------------------
    # PASS 1: Node Registration & Registry Construction
    # ------------------------------------------------------------------------
    for path in file_paths:
        if not os.path.exists(path):
            logger.warning("Skipping missing path during scan: %s", path)
            continue

        lang = detect_language(path, use_ai=use_ai)
        parsed_chunks = parse_file_chunks(path, language=lang, use_ai=use_ai)

        for qid, scope, name, code, s_line, e_line in parsed_chunks:
            graph.add_node(
                qid,
                file_path=path,
                scope=scope,
                name=name,
                code=code,
                language=lang,
                start_line=s_line,
                end_line=e_line,
                depends_on=[],
                unresolved=[],
            )

            name_upper = name.upper()
            scope_name_upper = f"{scope}::{name}".upper()
            qid_upper = qid.upper()

            exact_registry[qid_upper] = qid
            exact_registry[scope_name_upper] = qid
            exact_registry[f"{path}::{name}".upper()] = qid

            if name_upper not in name_to_qids:
                name_to_qids[name_upper] = []
            name_to_qids[name_upper].append(qid)

            all_chunks_info.append((qid, path, lang, code, name))

    logger.debug("Pass 1 completed: Registered %d chunk nodes", len(graph.nodes))

    # ------------------------------------------------------------------------
    # PASS 2: Call Analysis & Edge Construction
    # ------------------------------------------------------------------------
    for qid, path, lang, code, current_name in all_chunks_info:
        raw_called_names: List[str] = []

        if lang == "java":
            ast_calls = extract_java_calls_ast(code)
            if ast_calls is not None:
                raw_called_names = ast_calls

        if not raw_called_names:
            pattern = CALL_PATTERNS.get(lang)
            if pattern:
                matches = pattern.findall(code)
                raw_called_names = [m[1] if isinstance(m, tuple) else m for m in matches]

        unresolved_list: List[str] = []
        depends_on_set: Set[str] = set()

        for called_name in raw_called_names:
            called_name = called_name.strip()
            called_upper = called_name.upper()

            if not called_name or called_upper in KEYWORDS_IGNORE or called_upper == current_name.upper():
                continue

            target_qid: Optional[str] = None

            # Disambiguation Hierarchy:
            # 1. Look for same-file match
            same_file_prefix = f"{path}::{called_name}".upper()
            for key in exact_registry:
                if key.endswith(same_file_prefix) or same_file_prefix.endswith(key):
                    target_qid = exact_registry[key]
                    break

            # 2. Look for exact scope::name match
            if not target_qid and called_upper in exact_registry:
                target_qid = exact_registry[called_upper]

            # 3. Check name_to_qids registry
            if not target_qid and called_upper in name_to_qids:
                matching_qids = name_to_qids[called_upper]
                # Prefer chunk in the same file if multiple exist
                same_file_qids = [q for q in matching_qids if path in q]
                if same_file_qids:
                    target_qid = same_file_qids[0]
                elif len(matching_qids) == 1:
                    target_qid = matching_qids[0]

            # Edge resolution
            if target_qid and target_qid != qid:
                graph.add_edge(qid, target_qid)
                depends_on_set.add(target_qid)
            elif called_upper not in KEYWORDS_IGNORE and len(called_name) > 1:
                unresolved_list.append(called_name)

        graph.nodes[qid]["depends_on"] = sorted(list(depends_on_set))
        graph.nodes[qid]["unresolved"] = sorted(list(set(unresolved_list)))

    logger.info(
        "Scan complete: %d nodes, %d edges created across %d files",
        len(graph.nodes),
        len(graph.edges),
        len(file_paths),
    )

    return graph