"""
Pillar 3.4 -- Multi-Modal Response Formatter

Transforms raw query results, executed SQL, and calculated KPIs into the multi-modal
response payload specified in contracts/api.md:
1. summary: Plain-English narrative summary (via LLM or smart template).
2. table: Clean array of dictionary rows formatted for UI tables.
3. chart: Plotly-compatible chart schema configuration (or None).
"""

import os
import sys
from typing import Dict, Any, List, Optional
from datetime import date, datetime
from decimal import Decimal
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.kpi import compute_kpis, is_numeric

load_dotenv()

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
REGION = os.getenv("GCP_REGION", "europe-west4")
MODEL_NAME = "gemini-2.5-flash"


def make_json_serializable(obj: Any) -> Any:
    """Recursively converts dates, decimals, and special types into JSON primitives."""
    if isinstance(obj, list):
        return [make_json_serializable(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, Decimal):
        return float(obj)
    return obj


def detect_chart_config(data: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Auto-detects appropriate chart visualization schema (line, bar, pie/donut)
    based on result columns and data shapes.
    """
    if not data or len(data) == 0:
        return None

    columns = list(data[0].keys())
    if len(columns) < 2:
        return None  # Scalar single value, no multi-dimensional chart needed

    # Identify candidate column types
    time_keywords = ["date", "month", "year", "quarter", "day", "week", "order_date"]
    cat_keywords = ["category", "subcategory", "product_name", "brand", "country", "city", "store_name", "gender"]

    time_col = next((c for c in columns if any(tk in c.lower() for tk in time_keywords)), None)
    cat_col = next((c for c in columns if any(ck in c.lower() for ck in cat_keywords)), None)
    num_col = next((c for c in columns if is_numeric(data[0].get(c))), None)

    if not num_col:
        return None

    # Time series -> Line Chart
    if time_col:
        return {
            "type": "line",
            "x_field": time_col,
            "y_field": num_col
        }

    # Categorical breakdown -> Bar or Pie Chart
    if cat_col:
        chart_type = "donut" if len(data) <= 6 else "bar"
        return {
            "type": chart_type,
            "x_field": cat_col,
            "y_field": num_col
        }

    # Fallback to first non-numeric for X and numeric for Y
    non_num_col = next((c for c in columns if not is_numeric(data[0].get(c))), None)
    if non_num_col:
        return {
            "type": "bar",
            "x_field": non_num_col,
            "y_field": num_col
        }

    return None


def generate_narrative_summary(question: str, data: List[Dict[str, Any]], kpis: Dict[str, Any]) -> str:
    """
    Generates a executive narrative summary in plain English using Gemini GenAI,
    with a robust fallback if cloud LLM is unreachable.
    """
    if not data:
        return "No data found matching your query criteria."

    # Try LLM Summary Generation
    try:
        from google import genai
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            client = genai.Client(api_key=api_key)
        else:
            client = genai.Client(vertexai=True, project=PROJECT_ID, location=REGION)

        data_sample = data[:10]  # Limit context length
        prompt = f"""
Given the user's business question: "{question}"
And the retrieved database result (first 10 rows): {data_sample}
Calculated KPIs: {kpis}

Write a concise, professional 1-2 sentence executive business summary answering the user's question directly.
Include relevant numbers, metrics, or currencies. Do not mention SQL or technical database terms.
"""
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
        )
        if response.text and response.text.strip():
            return response.text.strip()
    except Exception as e:
        print(f"[Formatter Warning] GenAI summary call skipped/failed: {e}")

    # Fallback Template-based Summary Generator
    if kpis.get("total_revenue", 0) > 0:
        rev_formatted = f"${kpis['total_revenue']:,.2f}"
        if kpis.get("top_performer"):
            top_name = kpis['top_performer']['name']
            top_val = f"${kpis['top_performer']['value']:,.2f}"
            return f"Total calculated revenue is {rev_formatted} across {kpis['row_count']} records, with {top_name} leading at {top_val}."
        return f"Query returned {kpis['row_count']} records with a total revenue of {rev_formatted}."

    if kpis.get("total_units", 0) > 0:
        return f"Query returned a total of {kpis['total_units']:,} units sold across {kpis['row_count']} result rows."

    first_row = data[0]
    summary_parts = [f"{k}: {v}" for k, v in list(first_row.items())[:3]]
    return f"Query retrieved {len(data)} rows. Primary result: " + ", ".join(summary_parts) + "."


def format_response(sql: str, data: List[Dict[str, Any]], question: str) -> Dict[str, Any]:
    """
    Assembles the final API response matching contracts/api.md.
    """
    clean_data = make_json_serializable(data)
    kpis = compute_kpis(clean_data)
    summary = generate_narrative_summary(question, clean_data, kpis)
    chart = detect_chart_config(clean_data)

    return {
        "status": "ok",
        "sql": sql,
        "summary": summary,
        "table": clean_data,
        "chart": chart
    }


if __name__ == "__main__":
    sample_sql = "SELECT category, SUM(sales) as revenue FROM sales GROUP BY category"
    sample_data = [
        {"category": "Audio", "revenue": 142300.50},
        {"category": "Computers", "revenue": 210450.00},
        {"category": "Cameras", "revenue": 89200.00}
    ]
    res = format_response(sample_sql, sample_data, "What are our sales by category?")
    print("Formatted Response Output:")
    print(res)
