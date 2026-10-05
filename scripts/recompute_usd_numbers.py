"""
Recomputes every revenue-based number we quote, using the CORRECT USD formula:

    revenue = SUM(quantity * unit_price)       (unit_price is already in USD)
    profit  = SUM(quantity * (unit_price - unit_cost))

Run it after apply_usd_fix.py. The output feeds the benchmark's expected answers,
the golden set, and the slides.

Usage (from the project root, venv active):
    python scripts/recompute_usd_numbers.py
"""

import os
from decimal import Decimal

from dotenv import load_dotenv
from google.cloud import bigquery

load_dotenv()
PROJECT_ID = os.getenv("GCP_PROJECT_ID")
DS = "retail_dw"
client = bigquery.Client(project=PROJECT_ID)


def T(table: str) -> str:
    return f"`{PROJECT_ID}.{DS}.{table}`"


REV = "s.quantity * p.unit_price"
PROFIT = "s.quantity * (p.unit_price - p.unit_cost)"
BASE = f"FROM {T('sales')} s JOIN {T('products')} p ON s.product_key = p.product_key"
WITH_CUSTOMERS = f"{BASE} JOIN {T('customers')} c ON s.customer_key = c.customer_key"


def fmt(v):
    if isinstance(v, (Decimal, float)):
        v = float(v)
        return f"{v:.4f}" if abs(v) < 10 else f"{v:,.2f}"
    if isinstance(v, int) and not isinstance(v, bool):
        return f"{v:,}" if abs(v) >= 10000 else str(v)
    return str(v)


def run(title: str, sql: str):
    rows = [dict(r) for r in client.query(sql).result()]
    print(f"\n== {title}")
    for r in rows:
        print("   " + "  |  ".join(f"{k}={fmt(v)}" for k, v in r.items()))
    return rows


print("=" * 70)
print("USD NUMBERS (corrected formula: quantity * unit_price, no exchange rate)")
print("=" * 70)

run("Total revenue, all time", f"SELECT ROUND(SUM({REV}), 2) AS revenue {BASE}")

years = run(
    "Revenue by year",
    f"SELECT EXTRACT(YEAR FROM s.order_date) AS year, ROUND(SUM({REV}), 2) AS revenue {BASE} GROUP BY year ORDER BY year",
)
by_year = {int(r["year"]): float(r["revenue"]) for r in years}
if 2018 in by_year and 2019 in by_year:
    print(
        f"\n== Revenue growth 2018 -> 2019\n   growth={(by_year[2019] - by_year[2018]) / by_year[2018]:.4f}"
    )

run(
    "Revenue in December 2019",
    f"SELECT ROUND(SUM({REV}), 2) AS revenue {BASE} WHERE s.order_date BETWEEN '2019-12-01' AND '2019-12-31'",
)
run(
    "Revenue by calendar month (all years combined)",
    f"SELECT EXTRACT(MONTH FROM s.order_date) AS month, ROUND(SUM({REV}), 2) AS revenue {BASE} GROUP BY month ORDER BY month",
)
run(
    "Highest-revenue quarters",
    f"""SELECT EXTRACT(YEAR FROM s.order_date) AS year, EXTRACT(QUARTER FROM s.order_date) AS quarter,
               ROUND(SUM({REV}), 2) AS revenue
        {BASE} GROUP BY year, quarter ORDER BY revenue DESC LIMIT 3""",
)
run(
    "Average order value (overall)",
    f"SELECT ROUND(SUM({REV}) / COUNT(DISTINCT s.order_number), 2) AS aov {BASE}",
)
run(
    "Revenue by category",
    f"SELECT p.category, ROUND(SUM({REV}), 2) AS revenue {BASE} GROUP BY p.category ORDER BY revenue DESC",
)
run(
    "Top 5 brands by revenue",
    f"SELECT p.brand, ROUND(SUM({REV}), 2) AS revenue {BASE} GROUP BY p.brand ORDER BY revenue DESC LIMIT 5",
)
run(
    "Top 10 products by revenue",
    f"SELECT p.product_name, p.brand, ROUND(SUM({REV}), 2) AS revenue {BASE} GROUP BY p.product_name, p.brand ORDER BY revenue DESC LIMIT 10",
)
run(
    "Revenue by continent (customer's continent)",
    f"SELECT c.continent, ROUND(SUM({REV}), 2) AS revenue {WITH_CUSTOMERS} GROUP BY c.continent ORDER BY revenue DESC",
)
run(
    "Revenue by customer country",
    f"SELECT c.country, ROUND(SUM({REV}), 2) AS revenue {WITH_CUSTOMERS} GROUP BY c.country ORDER BY revenue DESC",
)
run(
    "Revenue by currency the customer paid in (all shown in USD)",
    f"SELECT s.currency_code, ROUND(SUM({REV}), 2) AS revenue {BASE} GROUP BY s.currency_code ORDER BY revenue DESC",
)
run(
    "Profit and margin, Computers",
    f"SELECT ROUND(SUM({PROFIT}), 2) AS profit, ROUND(SUM({PROFIT}) / SUM({REV}), 4) AS margin {BASE} WHERE LOWER(p.category) = 'computers'",
)
run(
    "Profit and margin, overall",
    f"SELECT ROUND(SUM({PROFIT}), 2) AS profit, ROUND(SUM({PROFIT}) / SUM({REV}), 4) AS margin {BASE}",
)
run(
    "Online vs physical: revenue, orders, average order value",
    f"""SELECT CASE WHEN s.store_key = 0 THEN 'Online' ELSE 'Physical' END AS channel,
               ROUND(SUM({REV}), 2) AS revenue,
               COUNT(DISTINCT s.order_number) AS orders,
               ROUND(SUM({REV}) / COUNT(DISTINCT s.order_number), 2) AS aov
        {BASE} GROUP BY channel ORDER BY revenue DESC""",
)
run(
    "Order value distribution",
    f"""WITH order_totals AS (
            SELECT s.order_number, SUM({REV}) AS order_value {BASE} GROUP BY s.order_number)
        SELECT CASE WHEN order_value < 100 THEN '1. Under 100'
                    WHEN order_value < 500 THEN '2. 100-500'
                    WHEN order_value < 1000 THEN '3. 500-1000'
                    WHEN order_value < 2500 THEN '4. 1000-2500'
                    WHEN order_value < 5000 THEN '5. 2500-5000'
                    ELSE '6. Over 5000' END AS value_range,
               COUNT(*) AS orders
        FROM order_totals GROUP BY value_range ORDER BY value_range""",
)
run(
    "Revenue by customer age band",
    f"""SELECT CASE WHEN DATE_DIFF(CURRENT_DATE(), c.birthday, YEAR) < 30 THEN '1. Under 30'
                    WHEN DATE_DIFF(CURRENT_DATE(), c.birthday, YEAR) < 45 THEN '2. 30-45'
                    WHEN DATE_DIFF(CURRENT_DATE(), c.birthday, YEAR) < 60 THEN '3. 45-60'
                    ELSE '4. 60+' END AS age_band,
               ROUND(SUM({REV}), 2) AS revenue
        {WITH_CUSTOMERS} GROUP BY age_band ORDER BY age_band""",
)

print("\n" + "=" * 70)
print("DONE. Send me everything above.")
print("=" * 70)
