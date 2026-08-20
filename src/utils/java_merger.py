"""Java structural merger: extracts members from per-chunk generated Java code and assembles
a single unified, compilable Modern Java 17+ class file.

No external Java parser required — uses balanced-brace scanning to extract members.
"""

from __future__ import annotations
import re
from typing import NamedTuple
from src.orchestrator.state import ChunkMetadata, GeneratedCode


# ── Data containers ───────────────────────────────────────────────────────────

class JavaMembers(NamedTuple):
    package: str
    imports: list[str]
    constants: list[str]          # static final fields
    enums: list[str]              # enum { } blocks
    records: list[str]            # record declarations
    inner_classes: list[str]      # static class { } blocks
    methods: list[str]            # method bodies
    chunk_id: str
    line_start: int


# ── Balanced brace extractor ──────────────────────────────────────────────────

def _extract_brace_block(text: str, start_pos: int) -> str:
    """Extracts a complete { ... } block starting at `start_pos` (which must be '{')."""
    depth = 0
    i = start_pos
    while i < len(text):
        c = text[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return text[start_pos: i + 1]
        i += 1
    return text[start_pos:]


def _find_open_brace(text: str, from_pos: int) -> int:
    """Returns index of the next '{' starting from from_pos, or -1."""
    idx = text.find('{', from_pos)
    return idx


# ── Per-chunk extraction ──────────────────────────────────────────────────────

_PACKAGE_RE   = re.compile(r'^\s*package\s+([\w.]+)\s*;', re.MULTILINE)
_IMPORT_RE    = re.compile(r'^\s*import\s+[\w.*]+\s*;', re.MULTILINE)
_CONST_RE     = re.compile(
    r'^\s*(private|public|protected)?\s*static\s+final\s+\w[\w<>\[\]]*\s+\w+\s*=\s*[^;]+;',
    re.MULTILINE
)
# Matches enum/record/static-class opening signatures
_ENUM_OPEN_RE  = re.compile(r'((?:public\s+|private\s+|protected\s+)?enum\s+\w+)', re.MULTILINE)
_RECORD_RE     = re.compile(
    r'((?:public\s+|private\s+)?record\s+\w+\s*\([^)]*\)(?:\s+implements\s+[\w,\s]+)?)',
    re.MULTILINE
)
_INNER_CLS_RE  = re.compile(
    r'((?:public\s+|private\s+|protected\s+|static\s+)+class\s+\w+(?:\s+extends\s+\w+)?(?:\s+implements\s+[\w,\s]+)?)',
    re.MULTILINE
)
_METHOD_RE = re.compile(
    r'((?:(?:public|private|protected|static|final|synchronized|abstract|default)\s+)*'
    r'(?!class\b|enum\b|record\b|interface\b)'
    r'[\w<>\[\]]+\s+\w+\s*\([^)]*\)(?:\s+throws\s+[\w,\s]+)?)',
    re.MULTILINE
)


def _strip_package_imports(text: str) -> str:
    """Removes package declaration and all import lines from a Java text."""
    text = _PACKAGE_RE.sub('', text)
    text = _IMPORT_RE.sub('', text)
    return text


def _extract_top_class_body(text: str) -> str:
    """Strips the outermost class declaration and returns its body content."""
    # Find the first top-level class { and extract its body
    # Look for: public class Foo { ... }
    cls_match = re.search(
        r'(?:public\s+|abstract\s+|final\s+)*class\s+\w+[^{]*\{',
        text
    )
    if not cls_match:
        return text

    open_brace_pos = text.rfind('{', cls_match.start(), cls_match.end())
    if open_brace_pos == -1:
        return text

    body_block = _extract_brace_block(text, open_brace_pos)
    # Return content between first { and last }
    return body_block[1:-1]


def _extract_constants(body: str) -> list[str]:
    """Extracts static final field declarations."""
    seen: set[str] = set()
    results: list[str] = []
    for m in _CONST_RE.finditer(body):
        line = m.group(0).strip()
        # Derive field name to deduplicate
        name_match = re.search(r'final\s+\w[\w<>\[\]]*\s+(\w+)', line)
        name = name_match.group(1) if name_match else line[:30]
        if name not in seen:
            seen.add(name)
            results.append(line)
    return results


def _extract_block_items(body: str, pattern: re.Pattern) -> tuple[list[str], str]:
    """Finds items matching `pattern` in `body`, extracts their full {} blocks,
    returns (list_of_blocks, body_with_blocks_removed)."""
    items: list[str] = []
    seen_names: set[str] = set()
    remaining = body

    for m in pattern.finditer(body):
        open_brace_pos = _find_open_brace(body, m.end())
        if open_brace_pos == -1:
            continue
        full_block = m.group(0) + body[m.end(): open_brace_pos] + _extract_brace_block(body, open_brace_pos)

        # Extract name for deduplication
        name_match = re.search(r'\b(\w+)\s*(?:\(|{)', m.group(0))
        name = name_match.group(1) if name_match else full_block[:20]
        if name in seen_names:
            continue
        seen_names.add(name)
        items.append(full_block.strip())
        remaining = remaining.replace(full_block, '', 1)

    return items, remaining


def _extract_methods(body: str) -> list[str]:
    """Extracts all method bodies from a class body."""
    methods: list[str] = []
    seen_sigs: set[str] = set()

    for m in _METHOD_RE.finditer(body):
        sig = m.group(0).strip()
        # Skip constructors of inner classes we've already handled
        if any(kw in sig for kw in ('class ', 'enum ', 'record ', 'interface ')):
            continue
        open_brace_pos = _find_open_brace(body, m.end())
        if open_brace_pos == -1:
            continue
        # Skip if there's a semicolon before the brace (abstract / interface method)
        interim = body[m.end():open_brace_pos]
        if ';' in interim:
            continue
        full_method = sig + interim + _extract_brace_block(body, open_brace_pos)
        key = re.sub(r'\s+', ' ', sig)
        if key in seen_sigs:
            continue
        seen_sigs.add(key)
        methods.append(full_method.strip())

    return methods


def parse_chunk_java(java_text: str, chunk_id: str, line_start: int) -> JavaMembers:
    """Parses a single chunk's java string into structural members."""
    if not java_text or not java_text.strip():
        return JavaMembers('', [], [], [], [], [], [], chunk_id, line_start)

    # Package
    pkg_match = _PACKAGE_RE.search(java_text)
    package = pkg_match.group(1) if pkg_match else 'com.modern.services'

    # Imports
    imports = [m.group(0).strip() for m in _IMPORT_RE.finditer(java_text)]

    # Extract top-level class body
    body = _extract_top_class_body(java_text)

    # Constants
    constants = _extract_constants(body)
    # Remove constant lines from body so methods don't pick them up
    for c in constants:
        body = body.replace(c, '', 1)

    # Enums
    enums, body = _extract_block_items(body, _ENUM_OPEN_RE)

    # Records (extract before inner classes)
    records, body = _extract_block_items(body, _RECORD_RE)

    # Inner static classes
    inner_classes, body = _extract_block_items(body, _INNER_CLS_RE)

    # Methods (what's left)
    methods = _extract_methods(body)

    return JavaMembers(
        package=package,
        imports=imports,
        constants=constants,
        enums=enums,
        records=records,
        inner_classes=inner_classes,
        methods=methods,
        chunk_id=chunk_id,
        line_start=line_start,
    )


# ── Assembler ─────────────────────────────────────────────────────────────────

class JavaMerger:
    """Merges per-chunk GeneratedCode objects into one unified Java class file."""

    @staticmethod
    def merge(
        class_name: str,
        chunks: list[ChunkMetadata],
        generated_code: dict[str, GeneratedCode],
        package: str = "com.modern.services",
        class_javadoc: str = "",
    ) -> str:
        """Assembles all per-chunk Java code into a single unified class.

        Args:
            class_name:    Java class name (e.g. 'AccountProcessor').
            chunks:        Ordered list of ChunkMetadata (provides line_start for sorting).
            generated_code: Dict of chunk_id → GeneratedCode from the pipeline.
            package:       Java package declaration.
            class_javadoc: Optional class-level Javadoc comment.

        Returns:
            Complete Java source string for the unified class.
        """
        # Sort chunks by source line order
        chunk_map = {c.chunk_id: c for c in chunks}
        ordered_ids = sorted(
            generated_code.keys(),
            key=lambda cid: chunk_map[cid].line_start if cid in chunk_map else 9999
        )

        # Parse each chunk
        parsed: list[JavaMembers] = []
        for cid in ordered_ids:
            gc = generated_code[cid]
            chunk = chunk_map.get(cid)
            line_start = chunk.line_start if chunk else 9999
            parsed.append(parse_chunk_java(gc.target_java_code, cid, line_start))

        if not parsed:
            return f"package {package};\n\npublic class {class_name} {{\n}}\n"

        # Determine package (use first non-empty)
        final_package = next((p.package for p in parsed if p.package), package)

        # Merge imports: deduplicated + sorted
        all_imports: set[str] = set()
        for p in parsed:
            all_imports.update(p.imports)
        sorted_imports = sorted(all_imports)

        # Merge constants: deduplicated by field name
        seen_const_names: set[str] = set()
        merged_constants: list[str] = []
        for p in parsed:
            for c in p.constants:
                nm = re.search(r'final\s+\w[\w<>\[\]]*\s+(\w+)', c)
                key = nm.group(1) if nm else c[:30]
                if key not in seen_const_names:
                    seen_const_names.add(key)
                    merged_constants.append(c)

        # Merge enums: deduplicated by name
        seen_enum_names: set[str] = set()
        merged_enums: list[str] = []
        for p in parsed:
            for e in p.enums:
                nm = re.search(r'enum\s+(\w+)', e)
                key = nm.group(1) if nm else e[:20]
                if key not in seen_enum_names:
                    seen_enum_names.add(key)
                    merged_enums.append(e)

        # Merge records: deduplicated by name
        seen_record_names: set[str] = set()
        merged_records: list[str] = []
        for p in parsed:
            for r in p.records:
                nm = re.search(r'record\s+(\w+)', r)
                key = nm.group(1) if nm else r[:20]
                if key not in seen_record_names:
                    seen_record_names.add(key)
                    merged_records.append(r)

        # Merge inner classes: deduplicated by name
        seen_class_names: set[str] = set()
        merged_inner: list[str] = []
        for p in parsed:
            for ic in p.inner_classes:
                nm = re.search(r'class\s+(\w+)', ic)
                key = nm.group(1) if nm else ic[:20]
                if key not in seen_class_names:
                    seen_class_names.add(key)
                    merged_inner.append(ic)

        # Merge methods: deduplicated by signature key, keep source order
        seen_method_sigs: set[str] = set()
        merged_methods: list[str] = []
        for p in sorted(parsed, key=lambda x: x.line_start):
            for meth in p.methods:
                # Key = first line of method (the signature)
                first_line = meth.splitlines()[0].strip() if meth else ''
                key = re.sub(r'\s+', ' ', first_line)
                if key not in seen_method_sigs:
                    seen_method_sigs.add(key)
                    merged_methods.append(meth)

        # ── Assemble ─────────────────────────────────────────────────────────
        lines: list[str] = []

        lines.append(f"package {final_package};")
        lines.append("")

        for imp in sorted_imports:
            lines.append(imp)
        lines.append("")

        if class_javadoc:
            lines.append(f"/**")
            for jl in class_javadoc.splitlines():
                lines.append(f" * {jl}")
            lines.append(" */")

        lines.append(f"public class {class_name} {{")
        lines.append("")

        if merged_constants:
            lines.append("    // ── Constants ─────────────────────────────────────────────────────────")
            for c in merged_constants:
                lines.append(f"    {c}")
            lines.append("")

        if merged_enums:
            lines.append("    // ── Enums ─────────────────────────────────────────────────────────────")
            for e in merged_enums:
                for el in e.splitlines():
                    lines.append(f"    {el}")
                lines.append("")

        if merged_records:
            lines.append("    // ── Records ───────────────────────────────────────────────────────────")
            for r in merged_records:
                for rl in r.splitlines():
                    lines.append(f"    {rl}")
                lines.append("")

        if merged_inner:
            lines.append("    // ── Inner Classes ─────────────────────────────────────────────────────")
            for ic in merged_inner:
                for il in ic.splitlines():
                    lines.append(f"    {il}")
                lines.append("")

        if merged_methods:
            lines.append("    // ── Methods ───────────────────────────────────────────────────────────")
            for meth in merged_methods:
                for ml in meth.splitlines():
                    lines.append(f"    {ml}")
                lines.append("")

        lines.append("}")
        return "\n".join(lines) + "\n"

    @staticmethod
    def merge_tests(
        class_name: str,
        chunks: list[ChunkMetadata],
        generated_code: dict[str, GeneratedCode],
        package: str = "com.modern.services",
    ) -> str:
        """Assembles per-chunk JUnit 5 test suites into one unified test class.

        Each chunk's tests become a @Nested inner class inside the main test class.
        """
        from src.orchestrator.state import TestResult  # lazy import to avoid cycles
        # NOTE: tests come from the state `tests` dict, not GeneratedCode
        # This method is called with the tests dict passed in as generated_code param
        # for compatibility — it reads java_test_code from each value

        chunk_map = {c.chunk_id: c for c in chunks}
        ordered_ids = sorted(
            generated_code.keys(),
            key=lambda cid: chunk_map[cid].line_start if cid in chunk_map else 9999
        )

        lines: list[str] = [
            f"package {package};",
            "",
            "import org.junit.jupiter.api.Test;",
            "import org.junit.jupiter.api.Nested;",
            "import org.junit.jupiter.api.BeforeEach;",
            "import org.junit.jupiter.api.DisplayName;",
            "import java.math.BigDecimal;",
            "import java.time.LocalDateTime;",
            "import static org.junit.jupiter.api.Assertions.*;",
            "",
            f"@DisplayName(\"{class_name} — Unified JUnit 5 Suite\")",
            f"class {class_name}Test {{",
            "",
        ]

        for cid in ordered_ids:
            gc = generated_code[cid]
            # java_test_code is stored on TestResult; here we reuse target_java_code
            # as a placeholder — actual test merging uses the tests dict
            test_code = getattr(gc, 'java_test_code', '') or gc.target_java_code
            if not test_code.strip():
                continue

            chunk = chunk_map.get(cid)
            nested_name = "".join(w.capitalize() for w in re.split(r'[_.\-]', cid.split('_', 1)[-1] if '_' in cid else cid)) + "Tests"

            lines.append(f"    @Nested")
            lines.append(f"    @DisplayName(\"{cid}\")")
            lines.append(f"    class {nested_name} {{")

            # Extract only @Test methods from the test_code
            test_body = _extract_top_class_body(test_code)
            test_methods = _extract_methods(test_body)
            for tm in test_methods:
                for tl in tm.splitlines():
                    lines.append(f"        {tl}")
                lines.append("")

            lines.append("    }")
            lines.append("")

        lines.append("}")
        return "\n".join(lines) + "\n"
