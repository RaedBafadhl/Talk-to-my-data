"""
Pillar 4.2 -- Dynamic Data Visualizations
 
Renders the chart specification returned by the backend (type, x_field,
y_field) using Plotly, in the project's brand blue.
"""
 
import plotly.graph_objects as go
import streamlit as st
 
BRAND_BLUE = "#2E6FF2"
BRAND_NAVY = "#12173B"
GRID_COLOR = "#E2E8F7"
MONEY_WORDS = ("revenue", "profit", "price", "cost", "value", "aov")
RATIO_WORDS = ("margin", "growth", "rate", "share", "ratio", "retention")
PCT_WORDS = ("pct", "percent")
 
 
def _y_kind(name: str, values: list) -> str:
    """How the y values should be displayed (matches the backend formatter)."""
    n = str(name).lower()
    if any(w in n for w in PCT_WORDS):
        return "percent_points"
    if any(w in n for w in RATIO_WORDS) and "exchange" not in n:
        if max(abs(v) for v in values) <= 5:
            return "percent_fraction"
        if "margin" in n:
            return "money"
        return "percent_points"
    if any(w in n for w in MONEY_WORDS):
        return "money"
    return "number"
 
 
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
 
    # Categories as text, so years show as 2016, 2017 (not 2016.5 ticks)
    x_values = [str(row.get(x_field)) for row in table_data]
    y_values = [float(row.get(y_field, 0) or 0) for row in table_data]
 
    kind = _y_kind(y_field, y_values)
    yaxis = dict(showgrid=True, gridcolor=GRID_COLOR, zeroline=False)
 
    if kind == "money":
        hover = "%{x}<br>$%{y:,.2f}<extra></extra>"
        yaxis.update(tickprefix="$", tickformat=".3~s")  # e.g. $19.1M
    elif kind == "percent_fraction":
        hover = "%{x}<br>%{y:.2%}<extra></extra>"
        yaxis.update(tickformat=".0%")
    elif kind == "percent_points":
        hover = "%{x}<br>%{y:,.2f}%<extra></extra>"
        yaxis.update(ticksuffix="%")
    else:
        whole = all(v == int(v) for v in y_values)
        hover = "%{x}<br>%{y:,.0f}<extra></extra>" if whole else "%{x}<br>%{y:,.2f}<extra></extra>"
        if max(y_values) >= 1000:
            yaxis.update(tickformat=",.0f")
 
    fig = go.Figure()
    if chart_type == "line":
        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=y_values,
                mode="lines+markers",
                line=dict(color=BRAND_BLUE, width=3),
                marker=dict(color=BRAND_BLUE, size=7),
                hovertemplate=hover,
            )
        )
    else:
        fig.add_trace(
            go.Bar(
                x=x_values,
                y=y_values,
                marker=dict(color=BRAND_BLUE),
                hovertemplate=hover,
            )
        )
 
    fig.update_layout(
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        font=dict(family="Inter, sans-serif", color=BRAND_NAVY),
        margin=dict(l=40, r=20, t=20, b=40),
        height=380,
        xaxis=dict(showgrid=False, linecolor=GRID_COLOR, type="category"),
        yaxis=yaxis,
    )
 
    st.plotly_chart(fig, use_container_width=True)
 