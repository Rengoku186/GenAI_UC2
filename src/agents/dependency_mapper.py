"""Agent 2: Dependency Mapper Agent."""

from __future__ import annotations
from src.agents.base_agent import BaseAgent
from src.orchestrator.state import PipelineState, DependencyEdge
from src.parsers.cobol_parser import CobolParser
from src.parsers.vb_parser import VBParser
from src.parsers.java_parser import JavaParser


class DependencyMapperAgent(BaseAgent):
    """Maps inter-chunk and external dependencies across the legacy codebase."""

    def __init__(self, config_dir: str = "configs"):
        super().__init__("dependency_mapper", config_dir=config_dir)

    def execute(self, state: PipelineState) -> dict:
        """Constructs the full cross-chunk dependency graph edges."""
        chunks = state.get("chunks", [])
        all_edges: list[DependencyEdge] = []
        self.logger.info("Building cross-chunk dependency graph across %d chunks", len(chunks))

        file_chunks: dict[str, list] = {}
        for c in chunks:
            file_chunks.setdefault(c.source_file, []).append(c)

        for source_file, file_chunk_list in file_chunks.items():
            if not file_chunk_list:
                continue
            lang = file_chunk_list[0].language

            if lang == "cobol":
                parser = CobolParser(source_file)
                edges = parser.extract_dependencies(file_chunk_list)
            elif lang == "vb":
                parser = VBParser(source_file)
                edges = parser.extract_dependencies(file_chunk_list)
            elif lang == "java":
                parser = JavaParser(source_file)
                edges = parser.extract_dependencies(file_chunk_list)
            else:
                edges = []

            self.logger.debug("Mapped %d dependency edges for file %s", len(edges), source_file)
            all_edges.extend(edges)

        self.logger.info("Dependency mapping complete. Total edges found: %d", len(all_edges))
        return {
            "dependency_graph": all_edges,
            "stage": "dependency_mapping"
        }
