"""
Pillar 3.3 -- Retail KPI Computation Engine

Extracts and calculates key retail business metrics from database query results:
1. Total Revenue / Total Sales Amount
2. Total Units Sold / Volume
3. Average Order Value (AOV = Total Revenue / Total Orders)
4. Top Performing Categories / Products
5. Growth Rate (% change over time periods if applicable)
"""

from typing import Dict, Any, List, Optional
import math


def is_numeric(val: Any) -> bool:
    """Checks if a value can be converted to float."""
    if val is None:
        return False
    try:
        float(val)
        return True
    except (ValueError, TypeError):
        return False


def compute_kpis(data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Computes retail KPIs from tabular BigQuery result rows.

    Args:
        data (List[Dict[str, Any]]): Result dataset rows as a list of dicts.

    Returns:
        Dict[str, Any]: Dictionary containing calculated KPI metrics.
    """
    if not data:
        return {
            "row_count": 0,
            "total_revenue": 0.0,
            "total_units": 0,
            "aov": None,
            "top_performer": None,
            "summary_stats": {}
        }

    kpis: Dict[str, Any] = {
        "row_count": len(data),
        "total_revenue": 0.0,
        "total_units": 0,
        "aov": None,
        "top_performer": None,
        "summary_stats": {}
    }

    # Inspect column keys
    columns = list(data[0].keys())

    # Find candidate columns for metrics
    rev_col = next((c for c in columns if any(k in c.lower() for k in ["revenue", "sales", "total_price", "total_sales", "amount", "euro"])), None)
    unit_col = next((c for c in columns if any(k in c.lower() for k in ["quantity", "units", "items", "units_sold", "order_qty"])), None)
    order_col = next((c for c in columns if any(k in c.lower() for k in ["order_number", "order_key", "order_id", "orders"])), None)
    name_col = next((c for c in columns if any(k in c.lower() for k in ["product_name", "category", "subcategory", "brand", "country", "store_name"])), None)

    # 1. Total Revenue calculation
    if rev_col:
        total_rev = sum(float(row[rev_col]) for row in data if is_numeric(row.get(rev_col)))
        kpis["total_revenue"] = round(total_rev, 2)

    # 2. Total Units calculation
    if unit_col:
        total_u = sum(int(float(row[unit_col])) for row in data if is_numeric(row.get(unit_col)))
        kpis["total_units"] = total_u

    # 3. Average Order Value (AOV) calculation
    if rev_col and order_col:
        unique_orders = set(row[order_col] for row in data if row.get(order_col) is not None)
        num_orders = len(unique_orders)
        if num_orders > 0 and kpis["total_revenue"] > 0:
            kpis["aov"] = round(kpis["total_revenue"] / num_orders, 2)

    # 4. Top Performer Identification
    if name_col and (rev_col or unit_col):
        metric_col = rev_col or unit_col
        sorted_rows = sorted(
            [r for r in data if is_numeric(r.get(metric_col))],
            key=lambda x: float(x[metric_col]),
            reverse=True
        )
        if sorted_rows:
            top_item = sorted_rows[0]
            kpis["top_performer"] = {
                "name": str(top_item[name_col]),
                "metric_column": metric_col,
                "value": round(float(top_item[metric_col]), 2)
            }

    # 5. Generic Summary Stats for Numeric Columns
    for col in columns:
        numeric_vals = [float(row[col]) for row in data if is_numeric(row.get(col))]
        if len(numeric_vals) == len(data) and len(numeric_vals) > 0:
            kpis["summary_stats"][col] = {
                "sum": round(sum(numeric_vals), 2),
                "avg": round(sum(numeric_vals) / len(numeric_vals), 2),
                "min": round(min(numeric_vals), 2),
                "max": round(max(numeric_vals), 2)
            }

    return kpis


if __name__ == "__main__":
    # Test suite for KPI Computation Engine
    sample_data = [
        {"product_name": "Headphones", "category": "Audio", "sales": 45200.0, "quantity": 300, "order_number": "ORD-1"},
        {"product_name": "Headphones", "category": "Audio", "sales": 48900.0, "quantity": 320, "order_number": "ORD-2"},
        {"product_name": "Wireless Mouse", "category": "Accessories", "sales": 12000.0, "quantity": 500, "order_number": "ORD-3"}
    ]
    res = compute_kpis(sample_data)
    print("KPI Computation Result:")
    print(res)
