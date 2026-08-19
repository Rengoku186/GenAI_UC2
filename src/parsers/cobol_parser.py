"""Parser for legacy COBOL source code."""

from __future__ import annotations
import re
from pathlib import Path
from src.orchestrator.state import ChunkMetadata, DependencyEdge


class CobolParser:
    """Extracts semantic paragraphs, sections, data structures, and dependency relations from COBOL files."""

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
        """Splits COBOL source into semantic chunks: Header/Data Division, and individual Paragraphs/Sections."""
        chunks: list[ChunkMetadata] = []
        if not self.lines:
            return chunks

        # Locate PROCEDURE DIVISION line
        proc_div_idx = -1
        for i, line in enumerate(self.lines):
            clean = line.strip().upper()
            if "PROCEDURE" in clean and "DIVISION" in clean:
                proc_div_idx = i
                break

        # If there is a DATA / ENVIRONMENT division before PROCEDURE DIVISION, chunk it as DATA_SCHEMA
        if proc_div_idx > 0:
            data_code = "\n".join(self.lines[:proc_div_idx])
            chunks.append(
                ChunkMetadata(
                    chunk_id=f"{self.filename}_DATA_DIV",
                    source_file=str(self.filename),
                    language="cobol",
                    line_start=1,
                    line_end=proc_div_idx,
                    name="DATA-AND-ENVIRONMENT-DIVISION",
                    chunk_type="data_division",
                    raw_code=data_code,
                    signature="DATA DIVISION / ENVIRONMENT DIVISION"
                )
            )

        start_idx = proc_div_idx if proc_div_idx >= 0 else 0
        current_chunk_name = ""
        current_start = -1
        current_lines: list[str] = []

        # Regex for paragraph or section header, e.g. "0000-MAIN-LOGIC." or "CALC-INTEREST SECTION."
        para_pattern = re.compile(r"^([0-9A-Z\-]+)(\s+SECTION)?\.\s*$", re.IGNORECASE)

        for idx in range(start_idx, len(self.lines)):
            line = self.lines[idx]
            clean_line = line.strip()

            # Skip comment lines (starts with * or /)
            if clean_line.startswith("*") or clean_line.startswith("/"):
                if current_chunk_name:
                    current_lines.append(line)
                continue

            match = para_pattern.match(clean_line)
            if match:
                # Close previous paragraph chunk if one was open
                if current_chunk_name and current_lines:
                    chunk_id = f"{self.filename}_{current_chunk_name.replace('-', '_')}"
                    chunks.append(
                        ChunkMetadata(
                            chunk_id=chunk_id,
                            source_file=str(self.filename),
                            language="cobol",
                            line_start=current_start + 1,
                            line_end=idx,
                            name=current_chunk_name,
                            chunk_type="paragraph",
                            raw_code="\n".join(current_lines),
                            signature=self.lines[current_start].strip()
                        )
                    )

                current_chunk_name = match.group(1).upper()
                current_start = idx
                current_lines = [line]
            else:
                if current_chunk_name:
                    current_lines.append(line)
                elif idx == start_idx:
                    # Procedure division header line before first paragraph
                    current_chunk_name = "PROCEDURE_HEADER"
                    current_start = idx
                    current_lines = [line]

        # Flush final chunk
        if current_chunk_name and current_lines:
            chunk_id = f"{self.filename}_{current_chunk_name.replace('-', '_')}"
            chunks.append(
                ChunkMetadata(
                    chunk_id=chunk_id,
                    source_file=str(self.filename),
                    language="cobol",
                    line_start=current_start + 1,
                    line_end=len(self.lines),
                    name=current_chunk_name,
                    chunk_type="paragraph",
                    raw_code="\n".join(current_lines),
                    signature=self.lines[current_start].strip()
                )
            )

        # Fallback if no paragraph found: treat whole file as a single chunk
        if not chunks:
            chunks.append(
                ChunkMetadata(
                    chunk_id=f"{self.filename}_MAIN",
                    source_file=str(self.filename),
                    language="cobol",
                    line_start=1,
                    line_end=len(self.lines),
                    name="MAIN",
                    chunk_type="program",
                    raw_code=self.raw_content,
                    signature="PROGRAM"
                )
            )

        return chunks

    def extract_dependencies(self, chunks: list[ChunkMetadata]) -> list[DependencyEdge]:
        """Analyzes PERFORM calls, CALL statements, COPY copybooks, and File I/O across chunks."""
        edges: list[DependencyEdge] = []
        chunk_map = {c.name.upper(): c.chunk_id for c in chunks}
        chunk_id_set = {c.chunk_id for c in chunks}

        perform_pattern = re.compile(r"\bPERFORM\s+([0-9A-Z\-]+)", re.IGNORECASE)
        call_pattern = re.compile(r"\bCALL\s+[\'\"]?([0-9A-Z\-]+)[\'\"]?", re.IGNORECASE)
        copy_pattern = re.compile(r"\bCOPY\s+([0-9A-Z\-]+)", re.IGNORECASE)
        file_io_pattern = re.compile(r"\b(OPEN|CLOSE|READ|WRITE)\s+([0-9A-Z\-]+)", re.IGNORECASE)

        for chunk in chunks:
            # Check for COPY copybooks
            for copy_match in copy_pattern.finditer(chunk.raw_code):
                copybook_name = copy_match.group(1).upper()
                edges.append(
                    DependencyEdge(
                        source_chunk=chunk.chunk_id,
                        target_chunk=f"COPYBOOK_{copybook_name}",
                        edge_type="copybook",
                        symbol=copybook_name,
                        description=f"Includes copybook {copybook_name}"
                    )
                )

            # Check for File I/O
            for io_match in file_io_pattern.finditer(chunk.raw_code):
                op, file_name = io_match.group(1).upper(), io_match.group(2).upper()
                edges.append(
                    DependencyEdge(
                        source_chunk=chunk.chunk_id,
                        target_chunk=f"FILE_{file_name}",
                        edge_type="file_io",
                        symbol=file_name,
                        description=f"{op} operation on file {file_name}"
                    )
                )

            # Check for PERFORM target paragraphs
            for perf_match in perform_pattern.finditer(chunk.raw_code):
                target_para = perf_match.group(1).upper()
                # Exclude internal loops like "UNTIL" or numbers
                if target_para in ["UNTIL", "VARYING", "TIMES", "WITH", "TEST"]:
                    continue
                target_id = chunk_map.get(target_para, f"{self.filename}_{target_para.replace('-', '_')}")
                if target_id != chunk.chunk_id:
                    edges.append(
                        DependencyEdge(
                            source_chunk=chunk.chunk_id,
                            target_chunk=target_id,
                            edge_type="calls",
                            symbol=target_para,
                            description=f"PERFORMs paragraph {target_para}"
                        )
                    )

            # Check for CALL external routines
            for call_match in call_pattern.finditer(chunk.raw_code):
                target_sub = call_match.group(1).upper()
                target_id = chunk_map.get(target_sub, f"EXTERNAL_{target_sub}")
                edges.append(
                    DependencyEdge(
                        source_chunk=chunk.chunk_id,
                        target_chunk=target_id,
                        edge_type="calls",
                        symbol=target_sub,
                        description=f"External CALL to {target_sub}"
                    )
                )

        return edges
