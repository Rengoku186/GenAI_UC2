'''Cycle detection and processing graph preparation utilities.

This module provides a single public function ``prepare_processing_graph`` that
takes a raw ``networkx.DiGraph`` representing code components and their
dependencies and returns a *condensed* DAG where strongly‑connected components
(cycles) are collapsed into a single super‑node.  The function is used by the
Phase‑1 orchestrator to establish a safe topological processing order.

Production enhancements over the original implementation:
  * Structured ``logging`` with ``DEBUG``/``INFO``/``ERROR`` levels.
  * Input validation and graceful degradation – if the graph cannot be
    condensed the function returns an empty graph and an empty order rather than
    raising an uncaught exception.
  * Deterministic attribute population – node attributes are normalised and
    ``id`` values are always strings, ensuring consistent downstream usage.
  * Optional handling of self‑loops via ``include_self_loops``.
  * Comprehensive docstring and type annotations.
  * Helper ``_populate_condensed_node`` factored out for readability and testability.
'''  # noqa: D400

import logging
from typing import Any, Dict, List, Tuple

import networkx as nx

logger = logging.getLogger(__name__)

__all__ = ["prepare_processing_graph"]


def _populate_condensed_node(
    condensed: nx.DiGraph,
    scc_node: Any,
    members: List[Any],
    raw_graph: nx.DiGraph,
    is_cycle: bool,
) -> None:
    """Populate attributes for a single condensed node.

    Args:
        condensed: The condensation graph being built.
        scc_node: The identifier of the SCC node inside ``condensed``.
        members: List of raw‑graph node IDs belonging to this SCC.
        raw_graph: The original ``DiGraph`` containing the full component metadata.
        is_cycle: ``True`` when the SCC contains more than one node or a
            self‑loop (when ``include_self_loops`` is ``True``).
    """
    combined_code_parts: List[str] = []
    combined_depends_on: set = set()
    file_path = ""
    scope = "SCC"
    name = f"SCC_{scc_node}"
    min_start_line = 10**9
    max_end_line = 0
    languages: set = set()

    for raw_id in sorted(members):
        attrs = raw_graph.nodes[raw_id]
        code = attrs.get("code", "")
        combined_code_parts.append(f"// --- Component: {raw_id} ---\n{code}")
        if not file_path:
            file_path = attrs.get("file_path", "")
        languages.add(attrs.get("language", "unknown"))
        min_start_line = min(min_start_line, attrs.get("start_line", 1))
        max_end_line = max(max_end_line, attrs.get("end_line", 1))
        for neighbor in raw_graph.successors(raw_id):
            if neighbor not in members:
                combined_depends_on.add(neighbor)

    combined_language = languages.pop() if len(languages) == 1 else "mixed"

    if not is_cycle and len(members) == 1:
        raw_id = members[0]
        raw_attrs = raw_graph.nodes[raw_id]
        condensed.nodes[scc_node]["id"] = raw_id
        condensed.nodes[scc_node]["name"] = raw_attrs.get("name", "")
        condensed.nodes[scc_node]["scope"] = raw_attrs.get("scope", "")
        condensed.nodes[scc_node]["file_path"] = raw_attrs.get("file_path", "")
        condensed.nodes[scc_node]["code"] = raw_attrs.get("code", "")
        condensed.nodes[scc_node]["language"] = raw_attrs.get("language", "unknown")
        condensed.nodes[scc_node]["start_line"] = raw_attrs.get("start_line", 1)
        condensed.nodes[scc_node]["end_line"] = raw_attrs.get("end_line", 1)
        condensed.nodes[scc_node]["depends_on"] = list(combined_depends_on)
        condensed.nodes[scc_node]["is_cycle_group"] = False
    else:
        condensed.nodes[scc_node]["id"] = name
        condensed.nodes[scc_node]["name"] = name
        condensed.nodes[scc_node]["scope"] = scope
        condensed.nodes[scc_node]["file_path"] = file_path
        condensed.nodes[scc_node]["code"] = "\n\n".join(combined_code_parts)
        condensed.nodes[scc_node]["language"] = combined_language
        condensed.nodes[scc_node]["start_line"] = (
            min_start_line if min_start_line != 10**9 else 1
        )
        condensed.nodes[scc_node]["end_line"] = max_end_line
        condensed.nodes[scc_node]["depends_on"] = list(combined_depends_on)
        condensed.nodes[scc_node]["is_cycle_group"] = True


def prepare_processing_graph(
    raw_graph: nx.DiGraph,
    *,
    include_self_loops: bool = True,
) -> Tuple[nx.DiGraph, List[str]]:
    """Condense ``raw_graph`` into a DAG suitable for Phase‑1 processing.

    The function performs three logical steps:

    1. **Condensation** – ``networkx.condensation`` collapses strongly‑connected
       components (SCCs) into super‑nodes, producing a directed acyclic graph.
    2. **Attribute synthesis** – each super‑node is enriched with aggregated
       metadata (combined source code, language, line ranges, etc.) while
       preserving original attributes for singleton nodes.
    3. **Dependency translation** – raw‑node dependency edges are rewritten to
       reference the owning condensed node IDs, yielding a clean ``depends_on``
       list per super‑node.

    Args:
        raw_graph: A ``networkx.DiGraph`` where each node follows the schema
            defined in :class:`src.schemas.Chunk` (code, file_path, language,
            start_line, end_line, etc.).
        include_self_loops: If ``True`` a node with a self‑edge is treated as a
            cycle and will be collapsed into a super‑node.  This mirrors the
            behaviour of the original implementation.

    Returns:
        A tuple ``(condensed_dag, processing_order)`` where ``condensed_dag`` is
        the DAG of SCCs and ``processing_order`` is a list of node ``id`` strings
        in topological order.
    """
    if not isinstance(raw_graph, nx.DiGraph):
        raise TypeError("raw_graph must be a networkx.DiGraph instance")

    try:
        condensed = nx.condensation(raw_graph)
    except Exception as exc:
        logger.error("Failed to condense dependency graph: %s", exc)
        return nx.DiGraph(), []

    node_to_scc: Dict[Any, int] = condensed.graph.get("mapping", {})
    if not node_to_scc:
        logger.warning("Condensation mapping missing; proceeding with empty mapping")

    for scc_node in condensed.nodes:
        members = list(condensed.nodes[scc_node].get("members", set()))
        is_cycle = len(members) > 1 or (
            include_self_loops
            and len(members) == 1
            and raw_graph.has_edge(members[0], members[0])
        )
        _populate_condensed_node(condensed, scc_node, members, raw_graph, is_cycle)

    for scc_node in condensed.nodes:
        raw_deps = condensed.nodes[scc_node].get("depends_on", [])
        translated: set = set()
        for dep in raw_deps:
            target_scc = node_to_scc.get(dep)
            if target_scc is None:
                logger.debug(
                    "Dependency %s of condensed node %s has no SCC mapping; skipping",
                    dep,
                    scc_node,
                )
                continue
            translated_id = condensed.nodes[target_scc]["id"]
            if translated_id != condensed.nodes[scc_node]["id"]:
                translated.add(translated_id)
        condensed.nodes[scc_node]["depends_on"] = list(translated)

    try:
        top_order = list(nx.topological_sort(condensed))
    except nx.NetworkXUnfeasible as exc:
        logger.error("Condensed graph is unexpectedly cyclic: %s", exc)
        top_order = []

    processing_order = [str(condensed.nodes[n]["id"]) for n in top_order]
    logger.info(
        "Prepared processing graph: %d condensed nodes, %d‑node order",
        condensed.number_of_nodes(),
        len(processing_order),
    )
    return condensed, processing_order