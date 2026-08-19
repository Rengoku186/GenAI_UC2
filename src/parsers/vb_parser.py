"""Parser for legacy Visual Basic (VB6 and VB.NET) source code."""

from __future__ import annotations
import re
from pathlib import Path
from src.orchestrator.state import ChunkMetadata, DependencyEdge


class VBParser:
    """Extracts Classes, Modules, Subs, Functions, Structures, and Dependencies from VB code."""

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
        """Splits VB code into semantic chunks (Classes, Structures, Functions, Subs)."""
        chunks: list[ChunkMetadata] = []
        if not self.lines:
            return chunks

        # Method / Function / Sub pattern
        proc_start_pattern = re.compile(
            r"^\s*(Public|Private|Protected|Friend|Static|\s)*(Async\s+)?(Function|Sub|Property)\s+([A-Za-z0-9_]+)",
            re.IGNORECASE
        )
        proc_end_pattern = re.compile(
            r"^\s*End\s+(Function|Sub|Property)",
            re.IGNORECASE
        )

        # Container pattern
        container_pattern = re.compile(
            r"^\s*(Public|Private|Protected|Friend|\s)*(Class|Structure|Module|Namespace)\s+([A-Za-z0-9_]+)",
            re.IGNORECASE
        )

        header_lines: list[str] = []
        in_proc = False
        proc_name = ""
        proc_type = ""
        proc_start = -1
        proc_sig = ""
        proc_lines: list[str] = []

        for idx, line in enumerate(self.lines):
            clean = line.strip()

            if not in_proc:
                m_proc = proc_start_pattern.match(clean)
                if m_proc:
                    in_proc = True
                    proc_type = m_proc.group(3).lower()
                    proc_name = m_proc.group(4)
                    proc_start = idx
                    proc_sig = clean
                    proc_lines = [line]
                    continue
                else:
                    if not chunks:
                        header_lines.append(line)
            else:
                proc_lines.append(line)
                if proc_end_pattern.match(clean):
                    chunks.append(
                        ChunkMetadata(
                            chunk_id=f"{self.filename}_{proc_name}",
                            source_file=str(self.filename),
                            language="vb",
                            line_start=proc_start + 1,
                            line_end=idx + 1,
                            name=proc_name,
                            chunk_type=proc_type,
                            raw_code="\n".join(proc_lines),
                            signature=proc_sig
                        )
                    )
                    in_proc = False
                    proc_name = ""
                    proc_lines = []

        # If header contains declarations, add as header chunk
        if header_lines and any(l.strip() and not l.strip().startswith("'") for l in header_lines):
            chunks.insert(
                0,
                ChunkMetadata(
                    chunk_id=f"{self.filename}_HEADER",
                    source_file=str(self.filename),
                    language="vb",
                    line_start=1,
                    line_end=len(header_lines),
                    name="IMPORTS_AND_DECLARATIONS",
                    chunk_type="header",
                    raw_code="\n".join(header_lines),
                    signature="Imports & Module Declarations"
                )
            )

        # Fallback if no procedures parsed
        if not [c for c in chunks if c.chunk_type in ["function", "sub", "property"]]:
            chunks = [
                ChunkMetadata(
                    chunk_id=f"{self.filename}_MAIN",
                    source_file=str(self.filename),
                    language="vb",
                    line_start=1,
                    line_end=len(self.lines),
                    name="MAIN",
                    chunk_type="module",
                    raw_code=self.raw_content,
                    signature="Module"
                )
            ]

        return chunks

    def extract_dependencies(self, chunks: list[ChunkMetadata]) -> list[DependencyEdge]:
        """Extracts function calls, imports, and shared references in VB."""
        edges: list[DependencyEdge] = []
        import_pattern = re.compile(r"^\s*Imports\s+([A-Za-z0-9_\.]+)", re.IGNORECASE)

        for chunk in chunks:
            for imp_match in import_pattern.finditer(chunk.raw_code):
                pkg = imp_match.group(1)
                edges.append(
                    DependencyEdge(
                        source_chunk=chunk.chunk_id,
                        target_chunk=f"IMPORT_{pkg}",
                        edge_type="import",
                        symbol=pkg,
                        description=f"Imports namespace {pkg}"
                    )
                )

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
                            description=f"Calls {other_chunk.name}()"
                        )
                    )

        return edges
