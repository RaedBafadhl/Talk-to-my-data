"""
Pillar 4.2 -- Dynamic Data Visualizations

Renders the chart specification returned by the backend (type, x_field,
y_field) using Plotly, styled with the project's official brand color.
"""

import plotly.graph_objects as go
import streamlit as st

BRAND_BLUE = "#2E6FF2"
BRAND_NAVY = "#12173B"
GRID_COLOR = "#E2E8F7"


def render_chart(chart_config: dict, table_data: list[dict]):
    """
    chart_config: {"type": "bar" | "line", "x_field": str, "y_field": str}
    table_data: the raw result rows
    """
    if not chart_config or not table_data:
        return

    x_field = chart_config.get("x_field")
    y_field = chart_config.get("y_field")
    chart_type = chart_config.get("type", "bar")

    x_values = [row.get(x_field) for row in table_data]
    y_values = [float(row.get(y_field, 0)) for row in table_data]

    fig = go.Figure()

    if chart_type == "line":
        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=y_values,
                mode="lines+markers",
                line=dict(color=BRAND_BLUE, width=3),
                marker=dict(color=BRAND_BLUE, size=7),
            )
        )
    else:
        fig.add_trace(
            go.Bar(
                x=x_values,
                y=y_values,
                marker=dict(color=BRAND_BLUE),
            )
        )

    fig.update_layout(
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        font=dict(family="Inter, sans-serif", color=BRAND_NAVY),
        margin=dict(l=40, r=20, t=20, b=40),
        height=380,
        xaxis=dict(showgrid=False, linecolor=GRID_COLOR),
        yaxis=dict(showgrid=True, gridcolor=GRID_COLOR, zeroline=False),
    )

    st.plotly_chart(fig, use_container_width=True)
