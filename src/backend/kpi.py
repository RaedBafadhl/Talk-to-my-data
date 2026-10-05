"""
Pillar 3.3 -- Retail KPI Computation Engine

Two complementary tools, serving different purposes:

1. GUARANTEED KPIs (get_revenue, get_top_products, get_average_order_value,
   get_category_share): fixed, pre-written SQL for the 4 specific KPIs named
   in the brief. No AI involved -- these always return a correct, consistent
   answer, verified against real EDA results. Use these when you need the
   OFFICIAL numbers with zero variability.

2. GENERIC STATS (compute_kpis): a flexible utility that auto-detects useful
   statistics from ANY already-fetched result set (e.g. from the general
   /ask pipeline), regardless of what was actually asked. Useful for
   enriching arbitrary query results with extra context, not a source of
   the 4 official KPIs.

(Originally built independently by Raed (deterministic KPIs) and Muhammed
(generic stats) -- combined here since they serve different, non-overlapping
purposes.)

Usage:
    python src/backend/kpi.py
"""

import os
import math
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from google.cloud import bigquery

load_dotenv()
PROJECT_ID = os.getenv("GCP_PROJECT_ID")
DATASET = "retail_dw"
client = bigquery.Client(project=PROJECT_ID)


def _query(sql: str) -> list[dict]:
    return [dict(row) for row in client.query(sql).result()]


# =====================================================================
# PART 1 -- Guaranteed KPIs (fixed SQL, no AI, verified against real data)
# =====================================================================


def get_revenue(start_date: str = None, end_date: str = None) -> dict:
    """KPI 1: Revenue over time. No dates = total revenue, all time."""
    where_clause = ""
    if start_date and end_date:
        where_clause = f"WHERE s.order_date BETWEEN '{start_date}' AND '{end_date}'"

    sql = f"""
        SELECT ROUND(SUM(s.quantity * p.unit_price), 2) AS revenue
        FROM `{PROJECT_ID}.{DATASET}.sales` s
        JOIN `{PROJECT_ID}.{DATASET}.products` p ON s.product_key = p.product_key
        {where_clause}
    """
    result = _query(sql)
    return {
        "kpi": "revenue",
        "period": f"{start_date} to {end_date}" if start_date else "all time",
        "value": float(result[0]["revenue"])
        if result and result[0]["revenue"]
        else 0.0,
    }


def get_top_products(by: str = "revenue", limit: int = 5) -> dict:
    """KPI 2: Top-performing categories, by revenue or units."""
    if by == "units":
        order_expr = "SUM(s.quantity)"
        value_label = "units_sold"
    else:
        order_expr = "SUM(s.quantity * p.unit_price)"
        value_label = "revenue"

    sql = f"""
        SELECT p.category, ROUND({order_expr}, 2) AS {value_label}
        FROM `{PROJECT_ID}.{DATASET}.sales` s
        JOIN `{PROJECT_ID}.{DATASET}.products` p ON s.product_key = p.product_key
        GROUP BY p.category
        ORDER BY {value_label} DESC
        LIMIT {limit}
    """
    return {"kpi": "top_products", "ranked_by": by, "results": _query(sql)}


def get_average_order_value() -> dict:
    """KPI 3: Average Order Value (AOV), overall."""
    sql = f"""
        SELECT ROUND(SUM(s.quantity * p.unit_price) / COUNT(DISTINCT s.order_number), 2) AS aov
        FROM `{PROJECT_ID}.{DATASET}.sales` s
        JOIN `{PROJECT_ID}.{DATASET}.products` p ON s.product_key = p.product_key
    """
    result = _query(sql)
    return {
        "kpi": "average_order_value",
        "value": float(result[0]["aov"]) if result else 0.0,
    }


def get_category_share() -> dict:
    """KPI 4: Category sales share (% of total revenue by category)."""
    sql = f"""
        WITH category_revenue AS (
            SELECT p.category, SUM(s.quantity * p.unit_price) AS revenue
            FROM `{PROJECT_ID}.{DATASET}.sales` s
            JOIN `{PROJECT_ID}.{DATASET}.products` p ON s.product_key = p.product_key
            GROUP BY p.category
        )
        SELECT category, ROUND(revenue, 2) AS revenue,
               ROUND(revenue * 100.0 / SUM(revenue) OVER (), 2) AS pct_of_total
        FROM category_revenue
        ORDER BY revenue DESC
    """
    return {"kpi": "category_share", "results": _query(sql)}


# =====================================================================
# PART 2 -- Generic stats (Muhammed's original design, unchanged)
# Works on ANY already-fetched result set, auto-detecting useful columns.
# =====================================================================


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
    Computes generic retail KPIs from ANY tabular result rows -- useful for
    enriching arbitrary /ask query results, regardless of what was asked.
    """
    if not data:
        return {
            "row_count": 0,
            "total_revenue": 0.0,
            "total_units": 0,
            "aov": None,
            "top_performer": None,
            "summary_stats": {},
        }

    kpis: Dict[str, Any] = {
        "row_count": len(data),
        "total_revenue": 0.0,
        "total_units": 0,
        "aov": None,
        "top_performer": None,
        "summary_stats": {},
    }

    columns = list(data[0].keys())

    rev_col = next(
        (
            c
            for c in columns
            if any(
                k in c.lower()
                for k in [
                    "revenue",
                    "sales",
                    "total_price",
                    "total_sales",
                    "amount",
                    "euro",
                ]
            )
        ),
        None,
    )
    unit_col = next(
        (
            c
            for c in columns
            if any(
                k in c.lower()
                for k in ["quantity", "units", "items", "units_sold", "order_qty"]
            )
        ),
        None,
    )
    order_col = next(
        (
            c
            for c in columns
            if any(
                k in c.lower()
                for k in ["order_number", "order_key", "order_id", "orders"]
            )
        ),
        None,
    )
    name_col = next(
        (
            c
            for c in columns
            if any(
                k in c.lower()
                for k in [
                    "product_name",
                    "category",
                    "subcategory",
                    "brand",
                    "country",
                    "store_name",
                ]
            )
        ),
        None,
    )

    if rev_col:
        total_rev = sum(
            float(row[rev_col]) for row in data if is_numeric(row.get(rev_col))
        )
        kpis["total_revenue"] = round(total_rev, 2)

    if unit_col:
        total_u = sum(
            int(float(row[unit_col])) for row in data if is_numeric(row.get(unit_col))
        )
        kpis["total_units"] = total_u

    if rev_col and order_col:
        unique_orders = set(
            row[order_col] for row in data if row.get(order_col) is not None
        )
        num_orders = len(unique_orders)
        if num_orders > 0 and kpis["total_revenue"] > 0:
            kpis["aov"] = round(kpis["total_revenue"] / num_orders, 2)

    if name_col and (rev_col or unit_col):
        metric_col = rev_col or unit_col
        sorted_rows = sorted(
            [r for r in data if is_numeric(r.get(metric_col))],
            key=lambda x: float(x[metric_col]),
            reverse=True,
        )
        if sorted_rows:
            top_item = sorted_rows[0]
            kpis["top_performer"] = {
                "name": str(top_item[name_col]),
                "metric_column": metric_col,
                "value": round(float(top_item[metric_col]), 2),
            }

    for col in columns:
        numeric_vals = [float(row[col]) for row in data if is_numeric(row.get(col))]
        if len(numeric_vals) == len(data) and len(numeric_vals) > 0:
            kpis["summary_stats"][col] = {
                "sum": round(sum(numeric_vals), 2),
                "avg": round(sum(numeric_vals) / len(numeric_vals), 2),
                "min": round(min(numeric_vals), 2),
                "max": round(max(numeric_vals), 2),
            }

    return kpis


if __name__ == "__main__":
    print("=" * 70)
    print("PART 1: GUARANTEED KPIs -- verified against real EDA values")
    print("=" * 70)

    print("\n1. Revenue (December 2019) -- expect 2477295.85:")
    print(get_revenue("2019-12-01", "2019-12-31"))

    print("\n2. Top products by revenue -- expect Computers first:")
    print(get_top_products(by="revenue", limit=5))

    print("\n3. Average Order Value -- expect 2117.89:")
    print(get_average_order_value())

    print("\n4. Category share:")
    print(get_category_share())

    print("\n" + "=" * 70)
    print("PART 2: GENERIC STATS -- works on any result set (demo data)")
    print("=" * 70)
    sample_data = [
        {
            "product_name": "Headphones",
            "category": "Audio",
            "sales": 45200.0,
            "quantity": 300,
            "order_number": "ORD-1",
        },
        {
            "product_name": "Headphones",
            "category": "Audio",
            "sales": 48900.0,
            "quantity": 320,
            "order_number": "ORD-2",
        },
        {
            "product_name": "Wireless Mouse",
            "category": "Accessories",
            "sales": 12000.0,
            "quantity": 500,
            "order_number": "ORD-3",
        },
    ]
    print(compute_kpis(sample_data))
