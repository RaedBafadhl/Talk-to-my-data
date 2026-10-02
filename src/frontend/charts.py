"""
Pillar 4.2 -- Dynamic Plotly Chart Visualization Engine

Renders interactive Plotly charts in Streamlit based on the chart configuration
schema returned by the backend API:
- line: Time series trends (px.line)
- bar: Category / dimension comparisons (px.bar)
- donut / pie: Proportion breakdowns (px.pie with hole)
"""

from typing import Dict, Any, List, Optional
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


def render_chart(chart_config: Optional[Dict[str, Any]], table_data: List[Dict[str, Any]]) -> None:
    """
    Renders an interactive Plotly chart in Streamlit based on chart_config and table_data.

    Args:
        chart_config (dict, optional): Chart schema specification from backend.
            Example: {"type": "line", "x_field": "month", "y_field": "revenue"}
        table_data (list of dicts): Raw tabular data rows.
    """
    if not chart_config or not table_data:
        return

    chart_type = chart_config.get("type", "").lower()
    x_field = chart_config.get("x_field")
    y_field = chart_config.get("y_field")

    if not x_field or not y_field:
        return

    df = pd.DataFrame(table_data)
    if df.empty or x_field not in df.columns or y_field not in df.columns:
        return

    # Ensure y_field is numeric
    df[y_field] = pd.to_numeric(df[y_field], errors="coerce")

    # Custom styling theme
    color_sequence = px.colors.qualitative.Bold

    fig = None

    if chart_type == "line":
        fig = px.line(
            df,
            x=x_field,
            y=y_field,
            markers=True,
            title=f"📈 Trend: {y_field.replace('_', ' ').title()} over {x_field.replace('_', ' ').title()}",
            color_discrete_sequence=["#1f77b4"]
        )
        fig.update_traces(line=dict(width=3), marker=dict(size=8))

    elif chart_type == "bar":
        fig = px.bar(
            df,
            x=x_field,
            y=y_field,
            text_auto=".2s",
            title=f"📊 Breakdown: {y_field.replace('_', ' ').title()} by {x_field.replace('_', ' ').title()}",
            color_discrete_sequence=["#2ca02c"]
        )
        fig.update_traces(textposition="outside")

    elif chart_type in ("donut", "pie"):
        fig = px.pie(
            df,
            names=x_field,
            values=y_field,
            hole=0.4 if chart_type == "donut" else 0.0,
            title=f"🍩 Share: {y_field.replace('_', ' ').title()} Breakdown by {x_field.replace('_', ' ').title()}",
            color_discrete_sequence=color_sequence
        )
        fig.update_traces(textinfo="percent+label")

    if fig:
        fig.update_layout(
            margin=dict(l=20, r=20, t=50, b=20),
            hovermode="x unified" if chart_type == "line" else "closest",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, sans-serif", size=13),
            xaxis=dict(showgrid=True, gridcolor="#e5e7eb"),
            yaxis=dict(showgrid=True, gridcolor="#e5e7eb")
        )
        st.plotly_chart(fig, use_container_width=True)
