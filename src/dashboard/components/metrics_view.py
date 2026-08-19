"""KPI overview and summary metrics — light theme, polished cards."""

from __future__ import annotations
import streamlit as st
import plotly.graph_objects as go
from typing import Any


def render_kpi_cards(report_data: dict[str, Any]):
    """Renders executive KPI cards with coloured accent borders."""
    status_summary  = report_data.get("status_summary", {})
    total_chunks    = report_data.get("total_chunks", 0)
    avg_confidence  = report_data.get("overall_average_confidence", 0.0)
    flagged_count   = status_summary.get("flagged_for_human_review", 0)
    auto_passed     = status_summary.get("auto_passed", 0)
    refined_passed  = status_summary.get("auto_passed_after_refinement", 0)

    pass_pct    = (auto_passed    / max(1, total_chunks)) * 100
    refine_pct  = (refined_passed / max(1, total_chunks)) * 100
    flagged_pct = (flagged_count  / max(1, total_chunks)) * 100

    st.markdown("""
    <style>
    .kpi-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 14px;
        margin-bottom: 22px;
    }
    .kpi-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 2px 8px rgba(15,23,42,0.05);
        transition: box-shadow 0.2s;
    }
    .kpi-card:hover { box-shadow: 0 4px 16px rgba(15,23,42,0.10); }
    .kpi-card-passed  { border-top: 4px solid #059669; }
    .kpi-card-refined { border-top: 4px solid #d97706; }
    .kpi-card-flagged { border-top: 4px solid #dc2626; }
    .kpi-card-total   { border-top: 4px solid #4f46e5; }

    .kpi-label {
        font-size: 0.72rem; font-weight: 700; color: #64748b;
        text-transform: uppercase; letter-spacing: 0.07em;
        margin-bottom: 8px;
    }
    .kpi-value {
        font-size: 2rem; font-weight: 800; color: #0f172a;
        line-height: 1.1; margin-bottom: 4px;
    }
    .kpi-sub { font-size: 0.78rem; color: #94a3b8; }
    .kpi-pct {
        display: inline-block;
        font-size: 0.78rem; font-weight: 600;
        padding: 2px 8px; border-radius: 99px;
        margin-top: 4px;
    }
    .kpi-pct-green  { background:#d1fae5; color:#065f46; }
    .kpi-pct-amber  { background:#fef3c7; color:#92400e; }
    .kpi-pct-red    { background:#fee2e2; color:#991b1b; }
    .kpi-pct-indigo { background:#ede9fe; color:#3730a3; }
    </style>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(f"""
        <div class="kpi-card kpi-card-total">
            <div class="kpi-label">Total Chunks</div>
            <div class="kpi-value">{total_chunks}</div>
            <div class="kpi-sub">Avg confidence</div>
            <span class="kpi-pct kpi-pct-indigo">{avg_confidence:.1%}</span>
        </div>""", unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div class="kpi-card kpi-card-passed">
            <div class="kpi-label">Auto-Passed</div>
            <div class="kpi-value">{auto_passed}</div>
            <div class="kpi-sub">Direct pass rate</div>
            <span class="kpi-pct kpi-pct-green">{pass_pct:.0f}%</span>
        </div>""", unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="kpi-card kpi-card-refined">
            <div class="kpi-label">Refined</div>
            <div class="kpi-value">{refined_passed}</div>
            <div class="kpi-sub">After auto-refine</div>
            <span class="kpi-pct kpi-pct-amber">{refine_pct:.0f}%</span>
        </div>""", unsafe_allow_html=True)

    with c4:
        st.markdown(f"""
        <div class="kpi-card kpi-card-flagged">
            <div class="kpi-label">Needs Review</div>
            <div class="kpi-value">{flagged_count}</div>
            <div class="kpi-sub">Flagged for human</div>
            <span class="kpi-pct kpi-pct-red">{flagged_pct:.0f}%</span>
        </div>""", unsafe_allow_html=True)


def render_distribution_charts(report_data: dict[str, Any]):
    """Renders a clean donut chart on a white background."""
    status_summary = report_data.get("status_summary", {})

    labels = ["Auto-Passed", "Refined", "Needs Review"]
    values = [
        status_summary.get("auto_passed", 0),
        status_summary.get("auto_passed_after_refinement", 0),
        status_summary.get("flagged_for_human_review", 0),
    ]
    colors = ["#059669", "#d97706", "#dc2626"]

    fig = go.Figure(data=[
        go.Pie(
            labels=labels,
            values=values,
            hole=0.62,
            marker=dict(colors=colors, line=dict(color="#ffffff", width=2)),
            textinfo="percent",
            textfont=dict(size=11, color="#ffffff"),
            textposition="inside",
            insidetextorientation="radial",
            hovertemplate="%{label}: %{value} (%{percent})<extra></extra>",
        )
    ])

    fig.update_layout(
        showlegend=True,
        legend=dict(
            orientation="v",
            font=dict(size=11, color="#334155"),
            bgcolor="rgba(0,0,0,0)",
        ),
        margin=dict(t=10, b=10, l=10, r=10),
        height=200,
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(family="Inter, sans-serif"),
    )

    st.plotly_chart(fig, use_container_width=True)

    # Confidence summary
    total = report_data.get("total_chunks", 0)
    avg   = report_data.get("overall_average_confidence", 0.0)
    if total:
        pct = int(avg * 100)
        bar_color = "#059669" if pct >= 85 else ("#d97706" if pct >= 70 else "#dc2626")
        st.markdown(f"""
        <div style="margin-top:8px;">
            <div style="font-size:0.72rem;font-weight:700;color:#64748b;text-transform:uppercase;
                        letter-spacing:0.06em;margin-bottom:6px;">Avg Confidence</div>
            <div style="background:#f1f5f9;border-radius:99px;height:8px;overflow:hidden;">
                <div style="width:{pct}%;height:100%;background:{bar_color};
                            border-radius:99px;transition:width 0.5s;"></div>
            </div>
            <div style="font-size:0.85rem;font-weight:700;color:#0f172a;margin-top:4px;">{avg:.1%}</div>
        </div>
        """, unsafe_allow_html=True)
