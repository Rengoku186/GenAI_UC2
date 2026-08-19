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
        self.logger.info("Ingesting and chunking %d source files: %s", len(source_files), source_files)

        for file_path_str in source_files:
            file_path = Path(file_path_str)
            if not file_path.exists():
                self.logger.warning("Source file not found: %s", file_path)
                continue

            content = file_path.read_text(encoding="utf-8", errors="ignore")
            lang = ASTTools.detect_language(file_path)
            self.logger.debug("Detected language '%s' for file '%s'", lang, file_path.name)

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

            self.logger.info("Extracted %d chunks from %s (%s)", len(chunks), file_path.name, lang)
            all_chunks.extend(chunks)

        self.logger.info("Ingestion complete. Total chunks extracted: %d", len(all_chunks))
        return {
            "chunks": all_chunks,
            "stage": "chunking"
        }
