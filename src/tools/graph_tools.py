"""Dependency graph analysis tools using NetworkX."""

from __future__ import annotations
from typing import Any
import networkx as nx
from src.orchestrator.state import ChunkMetadata, DependencyEdge


class GraphTools:
    """Provides topological ordering, cycle detection, and connectivity analytics."""

    @staticmethod
    def build_networkx_graph(chunks: list[ChunkMetadata], edges: list[DependencyEdge]) -> nx.DiGraph:
        """Constructs a directed NetworkX graph with chunk metadata attributes."""
        G = nx.DiGraph()
        
        # Add nodes
        for chunk in chunks:
            G.add_node(
                chunk.chunk_id,
                name=chunk.name,
                language=chunk.language,
                chunk_type=chunk.chunk_type,
                line_count=chunk.line_end - chunk.line_start + 1,
                source_file=chunk.source_file
            )

        # Add edges
        for edge in edges:
            G.add_edge(
                edge.source_chunk,
                edge.target_chunk,
                edge_type=edge.edge_type,
                symbol=edge.symbol or "",
                description=edge.description or ""
            )

        return G

    @staticmethod
    def analyze_graph(G: nx.DiGraph) -> dict[str, Any]:
        """Analyzes graph topology, cycles, in/out degrees, and migration priority levels."""
        # Find cycles
        try:
            cycles = list(nx.simple_cycles(G))
        except Exception:
            cycles = []

        # In-degree / Out-degree stats
        in_degrees = dict(G.in_degree())
        out_degrees = dict(G.out_degree())

        # Determine topological migration order (or fallback for cyclic graphs)
        if nx.is_directed_acyclic_graph(G):
            topo_order = list(nx.topological_sort(G))
        else:
            # Sort by ascending out-degree (leaf nodes / dependencies first)
            topo_order = sorted(G.nodes(), key=lambda n: (out_degrees.get(n, 0), -in_degrees.get(n, 0)))

        return {
            "node_count": G.number_of_nodes(),
            "edge_count": G.number_of_edges(),
            "is_dag": nx.is_directed_acyclic_graph(G),
            "cycles": cycles,
            "topological_order": topo_order,
            "in_degrees": in_degrees,
            "out_degrees": out_degrees,
            "density": nx.density(G)
        }

    @staticmethod
    def to_cytoscape_elements(G: nx.DiGraph) -> list[dict[str, Any]]:
        """Converts graph to standard JSON elements format for dashboard visualization."""
        elements: list[dict[str, Any]] = []

        for node, data in G.nodes(data=True):
            elements.append({
                "data": {
                    "id": str(node),
                    "label": data.get("name", str(node)),
                    "type": data.get("chunk_type", "node"),
                    "language": data.get("language", "")
                }
            })

        for u, v, data in G.edges(data=True):
            elements.append({
                "data": {
                    "source": str(u),
                    "target": str(v),
                    "label": data.get("edge_type", "depends_on"),
                    "symbol": data.get("symbol", "")
                }
            })

        return elements
