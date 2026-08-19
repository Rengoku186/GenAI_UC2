"""Agent 1: Ingestion & Chunker Agent."""

from __future__ import annotations
from pathlib import Path
from src.agents.base_agent import BaseAgent
from src.orchestrator.state import PipelineState, ChunkMetadata
from src.parsers.cobol_parser import CobolParser
from src.parsers.vb_parser import VBParser
from src.parsers.java_parser import JavaParser
from src.tools.ast_tools import ASTTools


class IngestionChunkerAgent(BaseAgent):
    """Parses legacy source files into semantic, language-aware chunks."""

    def __init__(self, config_dir: str = "configs"):
        super().__init__("ingestion_chunker", config_dir=config_dir)

    def execute(self, state: PipelineState) -> dict:
        """Parses all source files specified in the pipeline state into semantic chunks."""
        all_chunks: list[ChunkMetadata] = []
        source_files = state.get("source_files", [])

        for file_path_str in source_files:
            file_path = Path(file_path_str)
            if not file_path.exists():
                continue

            content = file_path.read_text(encoding="utf-8", errors="ignore")
            lang = ASTTools.detect_language(file_path)

            if lang == "cobol":
                parser = CobolParser(str(file_path), content=content)
                chunks = parser.parse_chunks()
            elif lang == "vb":
                parser = VBParser(str(file_path), content=content)
                chunks = parser.parse_chunks()
            elif lang == "java":
                parser = JavaParser(str(file_path), content=content)
                chunks = parser.parse_chunks()
            else:
                # Generic single chunk fallback
                lines = content.splitlines()
                chunks = [
                    ChunkMetadata(
                        chunk_id=f"{file_path.name}_ROOT",
                        source_file=file_path.name,
                        language=lang,
                        line_start=1,
                        line_end=len(lines),
                        name=file_path.stem,
                        chunk_type="module",
                        raw_code=content,
                        signature=file_path.stem
                    )
                ]

            all_chunks.extend(chunks)

        return {
            "chunks": all_chunks,
            "stage": "chunking"
        }
