import networkx as nx
from typing import Tuple, List, Dict, Any

def prepare_processing_graph(raw_graph: nx.DiGraph) -> Tuple[nx.DiGraph, List[str]]:
    """
    Collapses strongly connected components (cycles) in raw_graph into super-nodes
    using networkx.condensation() (Tarjan's SCC algorithm).
    Returns (condensed_dag, processing_order).
    """
    condensed = nx.condensation(raw_graph)
    node_to_scc = condensed.graph['mapping']  # raw_node -> scc_node index

    for scc_node in condensed.nodes:
        members = condensed.nodes[scc_node]['members']
        is_cycle = len(members) > 1

        if not is_cycle and len(members) == 1:
            m = list(members)[0]
            if raw_graph.has_edge(m, m):
                is_cycle = True

        combined_code_parts = []
        combined_depends_on = set()
        file_path = ""
        scope = "SCC"
        name = f"SCC_{scc_node}"
        min_start_line = 999999
        max_end_line = 0
        languages = set()

        for m in sorted(list(members)):
            node_attrs = raw_graph.nodes[m]
            code = node_attrs.get('code', '')
            combined_code_parts.append(f"// --- Component: {m} ---\n{code}")

            if not file_path:
                file_path = node_attrs.get('file_path', '')
            languages.add(node_attrs.get('language', 'unknown'))
            min_start_line = min(min_start_line, node_attrs.get('start_line', 1))
            max_end_line = max(max_end_line, node_attrs.get('end_line', 1))

            for neighbor in raw_graph.successors(m):
                if neighbor not in members:
                    combined_depends_on.add(neighbor)

        combined_language = languages.pop() if len(languages) == 1 else "mixed"

        if not is_cycle and len(members) == 1:
            single_member = list(members)[0]
            node_attrs = raw_graph.nodes[single_member]
            condensed.nodes[scc_node]['id'] = single_member
            condensed.nodes[scc_node]['name'] = node_attrs.get('name', '')
            condensed.nodes[scc_node]['scope'] = node_attrs.get('scope', '')
            condensed.nodes[scc_node]['file_path'] = node_attrs.get('file_path', '')
            condensed.nodes[scc_node]['code'] = node_attrs.get('code', '')
            condensed.nodes[scc_node]['language'] = node_attrs.get('language', 'unknown')
            condensed.nodes[scc_node]['start_line'] = node_attrs.get('start_line', 1)
            condensed.nodes[scc_node]['end_line'] = node_attrs.get('end_line', 1)
            condensed.nodes[scc_node]['depends_on'] = list(combined_depends_on)
            condensed.nodes[scc_node]['is_cycle_group'] = False
        else:
            condensed.nodes[scc_node]['id'] = f"SCC_{scc_node}"
            condensed.nodes[scc_node]['name'] = name
            condensed.nodes[scc_node]['scope'] = scope
            condensed.nodes[scc_node]['file_path'] = file_path
            condensed.nodes[scc_node]['code'] = "\n\n".join(combined_code_parts)
            condensed.nodes[scc_node]['language'] = combined_language
            condensed.nodes[scc_node]['start_line'] = min_start_line if min_start_line != 999999 else 1
            condensed.nodes[scc_node]['end_line'] = max_end_line
            condensed.nodes[scc_node]['depends_on'] = list(combined_depends_on)
            condensed.nodes[scc_node]['is_cycle_group'] = True

    # Second pass: translate raw-id dependencies into owning condensed-node ids
    for scc_node in condensed.nodes:
        raw_deps = condensed.nodes[scc_node].get('depends_on', [])
        translated = {condensed.nodes[node_to_scc[d]]['id'] for d in raw_deps}
        translated.discard(condensed.nodes[scc_node]['id'])
        condensed.nodes[scc_node]['depends_on'] = list(translated)

    top_order = list(nx.topological_sort(condensed))
    string_order = [str(condensed.nodes[node]['id']) for node in top_order]
    return condensed, string_order