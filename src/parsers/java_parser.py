"""Parser for legacy Java source code."""

from __future__ import annotations
import re
from pathlib import Path
from src.orchestrator.state import ChunkMetadata, DependencyEdge


class JavaParser:
    """Extracts Classes, Interfaces, Enums, Methods, and Method Invocations from Java source."""

    def __init__(self, filename_or_path: str, content: str | None = None):
        self.path = Path(filename_or_path)
        self.filename = self.path.name
        if content is not None:
            self.raw_content = content
        elif self.path.exists():
            self.raw_content = self.path.read_text(encoding="utf-8", errors="ignore")
        else:
            self.raw_content = ""
        self.lines = self.raw_content.splitlines()

    def parse_chunks(self) -> list[ChunkMetadata]:
        """Splits Java code into Package/Imports, Class structures, and individual Methods."""
        chunks: list[ChunkMetadata] = []
        if not self.lines:
            return chunks

        # Locate first class declaration
        class_pattern = re.compile(
            r"^\s*(public|protected|private|abstract|static|final|\s)*\s*(class|interface|enum)\s+([A-Za-z0-9_]+)",
            re.IGNORECASE
        )
        
        # Method header pattern
        method_pattern = re.compile(
            r"^\s*(public|protected|private|static|final|synchronized|abstract|\s)*\s*([A-Za-z0-9_<>\[\]]+)\s+([A-Za-z0-9_]+)\s*\(([^)]*)\)\s*(\{|throws\s+[A-Za-z0-9_,\s]+\{?)$"
        )

        header_lines: list[str] = []
        first_class_line = len(self.lines)
        for i, line in enumerate(self.lines):
            if class_pattern.match(line):
                first_class_line = i
                break
            header_lines.append(line)

        if header_lines and any(l.strip() and not l.strip().startswith("//") for l in header_lines):
            chunks.append(
                ChunkMetadata(
                    chunk_id=f"{self.filename}_HEADER",
                    source_file=str(self.filename),
                    language="java",
                    line_start=1,
                    line_end=first_class_line,
                    name="PACKAGE_AND_IMPORTS",
                    chunk_type="header",
                    raw_code="\n".join(header_lines),
                    signature="Package & Imports"
                )
            )

        # Parse methods and nested classes with brace counting
        in_method = False
        method_name = ""
        method_start = -1
        method_sig = ""
        method_lines: list[str] = []
        brace_depth = 0

        for idx in range(first_class_line, len(self.lines)):
            line = self.lines[idx]
            clean = line.strip()

            # Skip pure comment lines when searching for method header
            if not in_method and (clean.startswith("//") or clean.startswith("/*") or clean.startswith("*")):
                continue

            if not in_method:
                m_match = method_pattern.match(clean)
                # Ensure it's not a control structure like if/for/while/switch
                if m_match and m_match.group(3) not in ["if", "for", "while", "switch", "catch"]:
                    in_method = True
                    method_name = m_match.group(3)
                    method_start = idx
                    method_sig = clean
                    method_lines = [line]
                    brace_depth = line.count("{") - line.count("}")
                    if brace_depth == 0 and "{" in line:
                        # One-line method
                        chunks.append(
                            ChunkMetadata(
                                chunk_id=f"{self.filename}_{method_name}",
                                source_file=str(self.filename),
                                language="java",
                                line_start=method_start + 1,
                                line_end=idx + 1,
                                name=method_name,
                                chunk_type="method",
                                raw_code="\n".join(method_lines),
                                signature=method_sig
                            )
                        )
                        in_method = False
                    continue

            if in_method:
                method_lines.append(line)
                brace_depth += line.count("{") - line.count("}")
                if brace_depth <= 0:
                    chunks.append(
                        ChunkMetadata(
                            chunk_id=f"{self.filename}_{method_name}",
                            source_file=str(self.filename),
                            language="java",
                            line_start=method_start + 1,
                            line_end=idx + 1,
                            name=method_name,
                            chunk_type="method",
                            raw_code="\n".join(method_lines),
                            signature=method_sig
                        )
                    )
                    in_method = False
                    method_name = ""

        # Fallback if no methods extracted
        if not [c for c in chunks if c.chunk_type == "method"]:
            chunks.append(
                ChunkMetadata(
                    chunk_id=f"{self.filename}_MAIN",
                    source_file=str(self.filename),
                    language="java",
                    line_start=1,
                    line_end=len(self.lines),
                    name="CLASS_ROOT",
                    chunk_type="class",
                    raw_code=self.raw_content,
                    signature="Java Class"
                )
            )

        return chunks

    def extract_dependencies(self, chunks: list[ChunkMetadata]) -> list[DependencyEdge]:
        """Extracts imports, method calls, and inner-class dependencies in Java."""
        edges: list[DependencyEdge] = []
        import_pattern = re.compile(r"^\s*import\s+([A-Za-z0-9_\.]+);", re.MULTILINE)

        for imp_match in import_pattern.finditer(self.raw_content):
            pkg = imp_match.group(1)
            edges.append(
                DependencyEdge(
                    source_chunk=f"{self.filename}_HEADER",
                    target_chunk=f"IMPORT_{pkg}",
                    edge_type="import",
                    symbol=pkg,
                    description=f"Imports {pkg}"
                )
            )

        for chunk in chunks:
            for other_chunk in chunks:
                if other_chunk.chunk_id == chunk.chunk_id or other_chunk.chunk_type == "header":
                    continue
                call_regex = re.compile(rf"\b{re.escape(other_chunk.name)}\s*\(", re.IGNORECASE)
                if call_regex.search(chunk.raw_code):
                    edges.append(
                        DependencyEdge(
                            source_chunk=chunk.chunk_id,
                            target_chunk=other_chunk.chunk_id,
                            edge_type="calls",
                            symbol=other_chunk.name,
                            description=f"Invokes method {other_chunk.name}()"
                        )
                    )

        return edges
