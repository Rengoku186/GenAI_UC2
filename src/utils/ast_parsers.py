"""AST and Structural Parsers for Multi-Language Legacy Codebases.

Provides production-grade AST parsers and syntax extractors for:
- Java: Tree-sitter AST (with javalang & regex fallback) for precise method boundaries,
  nested/inner classes, annotations, and explicit method invocations.
- Visual Basic (VB6 / VBA / VBScript): State-machine block parser tracking Sub/Function/Property
  definitions up to matching End statements and extracting call instructions.
- COBOL: Section and paragraph structural parser handling division boundaries,
  comment indicators, and PERFORM/CALL invocations.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Dict, List, Optional, Pattern, Set, Tuple

logger = logging.getLogger(__name__)

# ============================================================================
# Tree-sitter Setup for Java
# ============================================================================

_TREE_SITTER_AVAILABLE = False
_JAVA_PARSER = None
# The installed tree-sitter Java binding can fault on very large source files
# on Windows. Route those files through the pure-Python fallback instead.
TREE_SITTER_MAX_SOURCE_CHARS = int(
    os.getenv("TREE_SITTER_MAX_SOURCE_CHARS", str(128 * 1024))
)

try:
    import tree_sitter
    import tree_sitter_java

    _java_language = tree_sitter.Language(tree_sitter_java.language())
    _JAVA_PARSER = tree_sitter.Parser(_java_language)
    _TREE_SITTER_AVAILABLE = True
    logger.debug("Tree-sitter Java parser initialized successfully.")
except Exception as exc:
    logger.info("Tree-sitter Java parser not available (%s), will use javalang/regex.", exc)

# ============================================================================
# Javalang Setup
# ============================================================================

_JAVALANG_AVAILABLE = False
try:
    import javalang
    _JAVALANG_AVAILABLE = True
except ImportError:
    pass

# ============================================================================
# 1. Java AST Parser
# ============================================================================

def parse_java_with_tree_sitter(
    file_path: str,
    content: str,
) -> Optional[List[Tuple[str, str, str, str, int, int]]]:
    """Parse Java code using Tree-sitter AST.

    Extracts methods, constructors, nested/inner class scopes, line ranges,
    and code bodies.

    Returns:
        List of (qualified_id, scope, name, code_snippet, start_line, end_line)
    """
    if (
        not _TREE_SITTER_AVAILABLE
        or _JAVA_PARSER is None
        or len(content) > TREE_SITTER_MAX_SOURCE_CHARS
    ):
        return None

    try:
        source_bytes = content.encode("utf-8")
        tree = _JAVA_PARSER.parse(source_bytes)
        lines = content.splitlines()
        total_lines = max(1, len(lines))
        file_basename = os.path.splitext(os.path.basename(file_path))[0]

        # 1. Extract package name
        package_name = ""
        for child in tree.root_node.children:
            if child.type == "package_declaration":
                for sub in child.children:
                    if sub.type in ("scoped_identifier", "identifier"):
                        package_name = sub.text.decode("utf-8")
                        break
                break

        base_scope = package_name if package_name else ""

        chunks: List[Tuple[str, str, str, str, int, int]] = []

        # Use an explicit stack rather than recursive descent. Large generated
        # Java sources can contain enough syntax nodes to overflow the Python
        # or native tree-sitter call stack during a recursive traversal.
        pending = [(tree.root_node, base_scope)]
        class_types = {
            "class_declaration", "interface_declaration",
            "enum_declaration", "record_declaration",
        }

        while pending:
            node, current_scope = pending.pop()

            if node.type in class_types:
                name_node = node.child_by_field_name("name")
                cname = name_node.text.decode("utf-8") if name_node else file_basename
                next_scope = f"{current_scope}.{cname}" if current_scope else cname
                pending.extend((child, next_scope) for child in reversed(node.children))
                continue

            if node.type in ("method_declaration", "constructor_declaration"):
                name_node = node.child_by_field_name("name")
                mname = name_node.text.decode("utf-8") if name_node else "unknown"
                start_l = max(1, min(node.start_point.row + 1, total_lines))
                end_l = max(start_l, min(node.end_point.row + 1, total_lines))
                chunk_code = "\n".join(lines[start_l - 1:end_l])
                final_scope = current_scope if current_scope else file_basename
                qid = f"{file_path}::{final_scope}::{mname}"
                chunks.append((qid, final_scope, mname, chunk_code, start_l, end_l))
                continue

            pending.extend((child, current_scope) for child in reversed(node.children))

        return chunks if chunks else None

    except Exception as exc:
        logger.warning("Tree-sitter Java parse failed on %s: %s", file_path, exc)
        return None


def parse_java_with_javalang(
    file_path: str,
    content: str,
) -> Optional[List[Tuple[str, str, str, str, int, int]]]:
    """Parse Java code using javalang AST as a secondary fallback."""
    if not _JAVALANG_AVAILABLE:
        return None

    try:
        tree = javalang.parse.parse(content)
        lines = content.splitlines()
        total_lines = max(1, len(lines))
        file_basename = os.path.splitext(os.path.basename(file_path))[0]
        pkg_prefix = f"{tree.package.name}." if tree.package else ""

        chunks: List[Tuple[str, str, str, str, int, int]] = []

        type_nodes = (
            javalang.tree.ClassDeclaration,
            javalang.tree.InterfaceDeclaration,
            javalang.tree.EnumDeclaration,
            javalang.tree.AnnotationDeclaration,
        )
        method_nodes = (
            javalang.tree.MethodDeclaration,
            javalang.tree.ConstructorDeclaration,
        )

        # ``tree.types`` exposes only top-level declarations. Iterating the
        # AST retains the parent path, allowing large legacy files with many
        # nested service classes to be represented completely.
        for path, node in tree:
            if not isinstance(node, method_nodes):
                continue

            enclosing_types = [
                ancestor.name
                for ancestor in path
                if isinstance(ancestor, type_nodes) and getattr(ancestor, "name", None)
            ]
            class_scope = ".".join(enclosing_types) or file_basename
            scope = f"{pkg_prefix}{class_scope}"
            mname = node.name
            start_l = node.position.line if node.position else 1

            # Approximate the method end with balanced braces. This is safe
            # for well-formed Java and keeps line spans usable if tree-sitter
            # is unavailable or intentionally bypassed for a large file.
            end_l = total_lines
            brace_count = 0
            started = False
            for idx, line in enumerate(lines[start_l - 1:]):
                brace_count += line.count("{") - line.count("}")
                if "{" in line:
                    started = True
                if started and brace_count <= 0:
                    end_l = start_l + idx
                    break

            chunk_code = "\n".join(lines[start_l - 1:end_l])
            qid = f"{file_path}::{scope}::{mname}"
            chunks.append((qid, scope, mname, chunk_code, start_l, end_l))

        # Java overloads share a method name and scope. Keep normal qualified
        # IDs stable, but make only colliding IDs line-qualified so graph nodes
        # cannot silently overwrite each other.
        qid_counts: Dict[str, int] = {}
        for qid, *_ in chunks:
            qid_counts[qid] = qid_counts.get(qid, 0) + 1
        chunks = [
            (
                f"{qid}::line{start_l}" if qid_counts[qid] > 1 else qid,
                scope,
                name,
                code,
                start_l,
                end_l,
            )
            for qid, scope, name, code, start_l, end_l in chunks
        ]

        return chunks if chunks else None
    except Exception as exc:
        logger.debug("javalang parsing skipped on %s: %s", file_path, exc)
        return None


def extract_java_calls_ast(code_snippet: str) -> Optional[List[str]]:
    """Extract invoked method names from a Java method snippet using Tree-sitter AST."""
    if not _TREE_SITTER_AVAILABLE or _JAVA_PARSER is None:
        return None

    try:
        # Wrap snippet in dummy class if needed to make it valid AST
        wrapped = f"public class _Wrapper_ {{ {code_snippet} }}"
        tree = _JAVA_PARSER.parse(wrapped.encode("utf-8"))

        calls: List[str] = []

        def find_invocations(node):
            if node.type == "method_invocation":
                name_node = node.child_by_field_name("name")
                if name_node:
                    calls.append(name_node.text.decode("utf-8"))
            for child in node.children:
                find_invocations(child)

        find_invocations(tree.root_node)
        return calls
    except Exception:
        return None


# ============================================================================
# 2. Visual Basic State-Machine Block Parser
# ============================================================================

VB_BLOCK_START = re.compile(
    r"^\s*(?:(?:Public|Private|Friend|Static|Default)\s+)*(Sub|Function|Property\s+(?:Get|Let|Set))\s+([a-zA-Z_]\w*)",
    re.IGNORECASE,
)

VB_BLOCK_END = re.compile(
    r"^\s*End\s+(?:Sub|Function|Property)\b",
    re.IGNORECASE,
)


def parse_vb_blocks(
    file_path: str,
    content: str,
) -> List[Tuple[str, str, str, str, int, int]]:
    """Parse Visual Basic (VB6 / VBA / VBScript) files by tracking Sub/Function/Property blocks.

    Accurately handles End Sub, End Function, End Property, and module names.
    """
    lines = content.splitlines()
    total_lines = max(1, len(lines))
    file_basename = os.path.splitext(os.path.basename(file_path))[0]

    attr_match = re.search(r'Attribute\s+VB_Name\s*=\s*"([^"]+)"', content, re.IGNORECASE)
    scope = attr_match.group(1) if attr_match else file_basename

    chunks: List[Tuple[str, str, str, str, int, int]] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        # Ignore comments
        stripped = line.strip()
        if stripped.startswith("'") or stripped.lower().startswith("rem "):
            i += 1
            continue

        match = VB_BLOCK_START.match(line)
        if match:
            routine_type = match.group(1)
            routine_name = match.group(2)
            start_line = i + 1

            # Seek matching End statement
            end_line = total_lines
            j = i + 1
            while j < len(lines):
                sub_line = lines[j]
                if VB_BLOCK_END.search(sub_line):
                    end_line = j + 1
                    i = j
                    break
                j += 1

            chunk_code = "\n".join(lines[start_line - 1:end_line])
            qid = f"{file_path}::{scope}::{routine_name}"
            chunks.append((qid, scope, routine_name, chunk_code, start_line, end_line))

        i += 1

    return chunks


# ============================================================================
# 3. COBOL Structural Section/Paragraph Parser
# ============================================================================

COBOL_RESERVED_HEADERS: Set[str] = {
    "PROCEDURE", "DIVISION", "DATA", "WORKING-STORAGE", "IDENTIFICATION",
    "ENVIRONMENT", "CONFIGURATION", "INPUT-OUTPUT", "FILE", "LOCAL-STORAGE",
    "LINKAGE", "SECTION", "END-IF", "END-PERFORM", "END-EVALUATE", "END-READ",
    "END-WRITE", "END-SEARCH", "END-STRING", "END-UNSTRING", "END-CALL",
    "END-COMPUTE", "END-ADD", "END-SUBTRACT", "END-MULTIPLY", "END-DIVIDE",
    "EXIT", "GOBACK", "STOP", "CONTINUE", "NEXT",
}


def parse_cobol_structural(
    file_path: str,
    content: str,
) -> List[Tuple[str, str, str, str, int, int]]:
    """Parse COBOL files into functional units (paragraphs and sections).

    Handles COBOL column formats (skipping column 7 indicators and comments),
    extracts PROGRAM-ID, identifies PROCEDURE DIVISION boundaries, and maps
    distinct paragraph units.
    """
    lines = content.splitlines()
    total_lines = max(1, len(lines))
    file_basename = os.path.splitext(os.path.basename(file_path))[0]

    program_match = re.search(r"PROGRAM-ID\.\s*([\w-]+)", content, re.IGNORECASE)
    scope = program_match.group(1).upper() if program_match else file_basename

    proc_div_idx = -1
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("*") or (len(line) > 6 and line[6] == "*"):
            continue
        if re.search(r"\bPROCEDURE\s+DIVISION\b", line, re.IGNORECASE):
            proc_div_idx = i
            break

    if proc_div_idx == -1:
        return []

    para_headers: List[Tuple[str, int]] = []
    for i in range(proc_div_idx + 1, len(lines)):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("*") or (len(line) > 6 and line[6] == "*"):
            continue

        m = re.match(r"^\s*([\w-]+)(?:\s+SECTION)?\.\s*$", line, re.IGNORECASE)
        if m:
            pname = m.group(1).upper()
            if pname not in COBOL_RESERVED_HEADERS:
                para_headers.append((pname, i + 1))

    chunks: List[Tuple[str, str, str, str, int, int]] = []
    for idx, (pname, start_l) in enumerate(para_headers):
        end_l = para_headers[idx + 1][1] - 1 if idx + 1 < len(para_headers) else total_lines
        chunk_code = "\n".join(lines[start_l - 1:end_l])
        qid = f"{file_path}::{scope}::{pname}"
        chunks.append((qid, scope, pname, chunk_code, start_l, end_l))

    return chunks
