"""Dependency Graph visualizer using Plotly and NetworkX."""

from __future__ import annotations
import streamlit as st
import networkx as nx
import plotly.graph_objects as go
from typing import Any


def render_dependency_graph(report_data: dict[str, Any]):
    """Renders directed dependency graph showing chunks, calls, copybooks, and data relationships."""
    edges_raw = report_data.get("dependency_graph_edges", [])
    chunk_details = report_data.get("chunk_details", {})

    if not edges_raw and not chunk_details:
        st.info("No dependency data to visualize.")
        return

    G = nx.DiGraph()

    for cid, det in chunk_details.items():
        meta = det.get("metadata", {})
        G.add_node(
            cid,
            label=meta.get("name", cid),
            status=det.get("status", "unknown"),
            lang=meta.get("language", "unknown")
        )

    for edge in edges_raw:
        G.add_edge(
            edge.get("source_chunk"),
            edge.get("target_chunk"),
            edge_type=edge.get("edge_type", "depends_on"),
            symbol=edge.get("symbol", "")
        )

    # Use spring layout for node positioning
    pos = nx.spring_layout(G, k=0.8, iterations=50, seed=42)

    # Edges trace
    edge_x = []
    edge_y = []
    edge_text = []

    for edge in G.edges(data=True):
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=1.5, color='#888'),
        hoverinfo='none',
        mode='lines'
    )

    # Nodes trace
    node_x = []
    node_y = []
    node_text = []
    node_colors = []

    status_color_map = {
        "auto_passed": "#22c55e",
        "auto_passed_after_refinement": "#eab308",
        "flagged_for_human_review": "#ef4444",
        "unknown": "#3b82f6"
    }

    for node in G.nodes(data=True):
        x, y = pos[node[0]]
        node_x.append(x)
        node_y.append(y)
        data = node[1]
        label = data.get("label", node[0])
        status = data.get("status", "unknown")
        lang = data.get("lang", "")
        node_text.append(f"Node: {node[0]}<br>Symbol: {label}<br>Status: {status}<br>Lang: {lang}")
        node_colors.append(status_color_map.get(status, "#3b82f6"))

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        hoverinfo='text',
        text=[G.nodes[n].get("label", n) for n in G.nodes()],
        textposition="top center",
        hovertext=node_text,
        marker=dict(
            showscale=False,
            color=node_colors,
            size=22,
            line_width=2
        )
    )

    fig = go.Figure(
        data=[edge_trace, node_trace],
        layout=go.Layout(
            title='Cross-Chunk & Resource Dependency Topology',
            titlefont_size=16,
            showlegend=False,
            hovermode='closest',
            margin=dict(b=20, l=5, r=5, t=40),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            height=450
        )
    )

    st.plotly_chart(fig, use_container_width=True)
