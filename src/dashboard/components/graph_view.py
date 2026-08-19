"""Dependency Graph visualizer using Plotly and NetworkX — light theme with visible edges."""

from __future__ import annotations
import math
import streamlit as st
import networkx as nx
import plotly.graph_objects as go
from typing import Any


# ── Status colour palette (dark enough on white) ─────────────────────────────
STATUS_COLORS = {
    "auto_passed":                    "#059669",   # emerald-600
    "auto_passed_after_refinement":   "#d97706",   # amber-600
    "flagged_for_human_review":       "#dc2626",   # red-600
    "unknown":                        "#4f46e5",   # indigo-600
}
STATUS_FILL = {
    "auto_passed":                    "#d1fae5",
    "auto_passed_after_refinement":   "#fef3c7",
    "flagged_for_human_review":       "#fee2e2",
    "unknown":                        "#ede9fe",
}
STATUS_LABELS = {
    "auto_passed":                    "Auto-Passed",
    "auto_passed_after_refinement":   "Refined",
    "flagged_for_human_review":       "Needs Review",
    "unknown":                        "Unknown",
}

EDGE_COLOR  = "#475569"   # slate-600 — clearly visible on white
EDGE_WIDTH  = 1.8
ARROW_SIZE  = 12          # pixels
NODE_SIZE   = 34
TEXT_COLOR  = "#1e293b"   # slate-900


def _arrow_annotation(x0, y0, x1, y1, color: str) -> dict:
    """Build a Plotly annotation that draws an arrowhead at (x1, y1)."""
    return dict(
        ax=x0, ay=y0,
        x=x1,  y=y1,
        xref="x", yref="y",
        axref="x", ayref="y",
        showarrow=True,
        arrowhead=3,
        arrowsize=1.4,
        arrowwidth=EDGE_WIDTH,
        arrowcolor=color,
        opacity=0.85,
    )


def render_dependency_graph(report_data: dict[str, Any]):
    """Renders directed dependency graph with clearly visible edges & arrowheads."""
    edges_raw    = report_data.get("dependency_graph_edges", [])
    chunk_details = report_data.get("chunk_details", {})

    if not edges_raw and not chunk_details:
        st.info("No dependency data to visualize.")
        return

    # ── Build graph ──────────────────────────────────────────────────────────
    G = nx.DiGraph()

    for cid, det in chunk_details.items():
        meta = det.get("metadata", {})
        G.add_node(
            cid,
            label=meta.get("name", cid.split("_")[-1]),
            status=det.get("status", "unknown"),
            lang=meta.get("language", "?"),
            source=meta.get("source_file", ""),
            lines=f"{meta.get('line_start','?')}–{meta.get('line_end','?')}",
        )

    for edge in edges_raw:
        src = edge.get("source_chunk")
        tgt = edge.get("target_chunk")
        if src and tgt:
            G.add_edge(src, tgt,
                       edge_type=edge.get("edge_type", "depends_on"),
                       symbol=edge.get("symbol", ""))

    # ── Layout ───────────────────────────────────────────────────────────────
    n = G.number_of_nodes()
    if n == 0:
        st.info("Dependency graph is empty.")
        return

    k_spread = max(1.5, 3.0 / max(1, math.sqrt(n)))
    pos = nx.spring_layout(G, k=k_spread, iterations=60, seed=42)

    # ── Legend boxes (left panel) ─────────────────────────────────────────────
    has_edges = G.number_of_edges() > 0

    # ── Edge traces (lines only — arrowheads via annotations) ────────────────
    edge_traces = []
    arrow_annotations = []

    for src, tgt, edata in G.edges(data=True):
        if src not in pos or tgt not in pos:
            continue
        x0, y0 = pos[src]
        x1, y1 = pos[tgt]

        # Slightly shorten the line so arrowhead is fully visible
        dx, dy = x1 - x0, y1 - y0
        length  = math.hypot(dx, dy) or 1e-9
        shrink  = 0.12  # fraction to pull endpoint back
        xs, ys  = x1 - dx * shrink, y1 - dy * shrink

        edge_traces.append(
            go.Scatter(
                x=[x0, xs, None],
                y=[y0, ys, None],
                mode="lines",
                line=dict(width=EDGE_WIDTH, color=EDGE_COLOR),
                hoverinfo="text",
                hovertext=f"{edata.get('edge_type','depends_on')}: {edata.get('symbol','')}",
                opacity=0.8,
                showlegend=False,
            )
        )
        arrow_annotations.append(_arrow_annotation(x0, y0, xs, ys, EDGE_COLOR))

    # ── Node trace ───────────────────────────────────────────────────────────
    node_x, node_y = [], []
    node_colors, node_border_colors = [], []
    hover_texts, node_labels = [], []

    for nid, ndata in G.nodes(data=True):
        if nid not in pos:
            continue
        x, y = pos[nid]
        node_x.append(x)
        node_y.append(y)

        status = ndata.get("status", "unknown")
        node_colors.append(STATUS_FILL.get(status, "#ede9fe"))
        node_border_colors.append(STATUS_COLORS.get(status, "#4f46e5"))
        node_labels.append(ndata.get("label", nid))

        hover_texts.append(
            f"<b>{ndata.get('label', nid)}</b><br>"
            f"Status: {STATUS_LABELS.get(status, status)}<br>"
            f"Lang: {ndata.get('lang','?').upper()}<br>"
            f"Source: {ndata.get('source','')}<br>"
            f"Lines: {ndata.get('lines','')}"
        )

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode="markers+text",
        marker=dict(
            color=node_colors,
            size=NODE_SIZE,
            line=dict(width=2.5, color=node_border_colors),
            symbol="circle",
        ),
        text=node_labels,
        textposition="top center",
        textfont=dict(size=11, color=TEXT_COLOR, family="Inter, sans-serif"),
        hoverinfo="text",
        hovertext=hover_texts,
        showlegend=False,
    )

    # ── Legend ────────────────────────────────────────────────────────────────
    legend_traces = []
    for status, label in STATUS_LABELS.items():
        legend_traces.append(
            go.Scatter(
                x=[None], y=[None],
                mode="markers",
                marker=dict(size=12, color=STATUS_FILL[status],
                            line=dict(width=2, color=STATUS_COLORS[status])),
                name=label,
                showlegend=True,
            )
        )

    # ── Figure ────────────────────────────────────────────────────────────────
    fig = go.Figure(data=[*edge_traces, node_trace, *legend_traces])

    fig.update_layout(
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.01,
            xanchor="left",   x=0,
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="#e2e8f0", borderwidth=1,
            font=dict(size=11, color="#1e293b"),
        ),
        hovermode="closest",
        annotations=arrow_annotations,
        margin=dict(b=20, l=20, r=20, t=50),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False,
                   range=[min(v[0] for v in pos.values()) - 0.35,
                          max(v[0] for v in pos.values()) + 0.35]),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False,
                   range=[min(v[1] for v in pos.values()) - 0.35,
                          max(v[1] for v in pos.values()) + 0.35]),
        height=440,
        paper_bgcolor="#ffffff",
        plot_bgcolor="#f8fafc",
        font=dict(family="Inter, sans-serif"),
    )

    # Gridline-style subtle background dots
    fig.update_xaxes(showgrid=True, gridcolor="#e2e8f0", gridwidth=1)
    fig.update_yaxes(showgrid=True, gridcolor="#e2e8f0", gridwidth=1)

    st.plotly_chart(fig, use_container_width=True)

    # ── Edge detail table ────────────────────────────────────────────────────
    if has_edges:
        with st.expander(f"🔗 Edge Details ({G.number_of_edges()} dependencies)", expanded=False):
            import pandas as pd
            rows = []
            for s, t, ed in G.edges(data=True):
                rows.append({
                    "From": G.nodes[s].get("label", s),
                    "→ To": G.nodes[t].get("label", t),
                    "Type": ed.get("edge_type", "depends_on"),
                    "Symbol": ed.get("symbol", "—"),
                })
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    else:
        st.caption("ℹ️ No inter-chunk dependencies detected for this run — each chunk is self-contained.")
