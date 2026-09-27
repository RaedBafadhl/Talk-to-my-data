"""
Data Quality Checks -- BigQuery warehouse (post-load)

Systematic checks that health_check.py couldn't do (that one checked the raw
CSVs before loading; this checks the real, live warehouse):

1. Missing values across ALL important columns in ALL 5 tables
2. Duplicate checks on primary keys
3. Referential integrity -- do foreign keys actually match a real record?
   (Important: your revenue calculations use INNER JOINs -- if any sales
   row references a product/customer/store that doesn't exist, it's been
   silently excluded from every number you've calculated so far.)
4. Revenue sanity checks -- negative/zero values, extreme outliers

Usage:
    python scripts/data_quality_checks.py
"""

import os
from dotenv import load_dotenv
from google.cloud import bigquery

load_dotenv()
PROJECT_ID = os.getenv("GCP_PROJECT_ID")
DATASET = "retail_dw"
client = bigquery.Client(project=PROJECT_ID)


def q(sql):
    return [dict(row) for row in client.query(sql).result()]


def section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


# =====================================================================
# 1. MISSING VALUES across all tables
# =====================================================================
section("1. MISSING VALUES CHECK")

tables_columns = {
    "sales": [
        "order_date",
        "order_number",
        "line_item",
        "product_key",
        "quantity",
        "customer_key",
        "store_key",
        "currency_code",
        "delivery_date",
    ],
    "products": [
        "product_key",
        "product_name",
        "brand",
        "color",
        "unit_cost",
        "unit_price",
        "category",
        "subcategory",
    ],
    "customers": [
        "customer_key",
        "name",
        "gender",
        "city",
        "state",
        "zip_code",
        "country",
        "continent",
        "birthday",
    ],
    "stores": ["store_key", "country", "state", "square_meters", "open_date"],
    "exchange_rates": ["date", "currency", "exchange_rate"],
}

for table, columns in tables_columns.items():
    print(f"\n  {table}:")
    null_checks = ", ".join([f"COUNTIF({c} IS NULL) as {c}_nulls" for c in columns])
    result = q(f"SELECT {null_checks} FROM `{PROJECT_ID}.{DATASET}.{table}`")[0]
    any_missing = False
    for col in columns:
        n = result[f"{col}_nulls"]
        if n > 0:
            any_missing = True
            note = (
                " (expected -- undelivered orders)"
                if col == "delivery_date"
                else " -- CHECK THIS"
            )
            print(f"    {col}: {n:,} missing{note}")
    if not any_missing:
        print("    No missing values in any column")


# =====================================================================
# 2. DUPLICATE CHECKS on primary keys
# =====================================================================
section("2. DUPLICATE KEY CHECK")

dup_checks = {
    "customers.customer_key": f"SELECT customer_key, COUNT(*) as n FROM `{PROJECT_ID}.{DATASET}.customers` GROUP BY customer_key HAVING COUNT(*) > 1",
    "products.product_key": f"SELECT product_key, COUNT(*) as n FROM `{PROJECT_ID}.{DATASET}.products` GROUP BY product_key HAVING COUNT(*) > 1",
    "stores.store_key": f"SELECT store_key, COUNT(*) as n FROM `{PROJECT_ID}.{DATASET}.stores` GROUP BY store_key HAVING COUNT(*) > 1",
    "sales.order_number+line_item": f"SELECT order_number, line_item, COUNT(*) as n FROM `{PROJECT_ID}.{DATASET}.sales` GROUP BY order_number, line_item HAVING COUNT(*) > 1",
    "exchange_rates (currency,date)": f"SELECT currency, date, COUNT(*) as n FROM `{PROJECT_ID}.{DATASET}.exchange_rates` GROUP BY currency, date HAVING COUNT(*) > 1",
}

for name, sql in dup_checks.items():
    dupes = q(sql)
    if dupes:
        print(f"  {name}: {len(dupes)} duplicate key(s) found -- CHECK THIS")
    else:
        print(f"  {name}: no duplicates")


# =====================================================================
# 3. REFERENTIAL INTEGRITY -- orphaned foreign keys
# =====================================================================
section("3. REFERENTIAL INTEGRITY CHECK")

orphan_checks = {
    "sales.product_key -> products": f"""
        SELECT COUNT(*) as n FROM `{PROJECT_ID}.{DATASET}.sales` s
        LEFT JOIN `{PROJECT_ID}.{DATASET}.products` p ON s.product_key = p.product_key
        WHERE p.product_key IS NULL
    """,
    "sales.customer_key -> customers": f"""
        SELECT COUNT(*) as n FROM `{PROJECT_ID}.{DATASET}.sales` s
        LEFT JOIN `{PROJECT_ID}.{DATASET}.customers` c ON s.customer_key = c.customer_key
        WHERE c.customer_key IS NULL
    """,
    "sales.store_key -> stores": f"""
        SELECT COUNT(*) as n FROM `{PROJECT_ID}.{DATASET}.sales` s
        LEFT JOIN `{PROJECT_ID}.{DATASET}.stores` st ON s.store_key = st.store_key
        WHERE st.store_key IS NULL
    """,
    "sales (currency+date) -> exchange_rates": f"""
        SELECT COUNT(*) as n FROM `{PROJECT_ID}.{DATASET}.sales` s
        LEFT JOIN `{PROJECT_ID}.{DATASET}.exchange_rates` e
            ON s.currency_code = e.currency AND s.order_date = e.date
        WHERE e.currency IS NULL
    """,
}

total_sales = q(f"SELECT COUNT(*) as n FROM `{PROJECT_ID}.{DATASET}.sales`")[0]["n"]
print(f"  (out of {total_sales:,} total sales rows)\n")
for name, sql in orphan_checks.items():
    n = q(sql)[0]["n"]
    if n > 0:
        pct = round(n / total_sales * 100, 2)
        print(
            f"  {name}: {n:,} orphaned rows ({pct}%) -- these are SILENTLY EXCLUDED from every INNER JOIN revenue calculation so far"
        )
    else:
        print(f"  {name}: no orphaned rows -- all foreign keys match")


# =====================================================================
# 4. REVENUE SANITY CHECKS -- bad values and outliers
# =====================================================================
section("4. REVENUE SANITY CHECKS")

bad_values = q(f"""
    SELECT
        COUNTIF(s.quantity <= 0) as bad_quantity,
        COUNTIF(p.unit_price <= 0) as bad_price,
        COUNTIF(e.exchange_rate <= 0) as bad_exchange_rate
    FROM `{PROJECT_ID}.{DATASET}.sales` s
    JOIN `{PROJECT_ID}.{DATASET}.products` p ON s.product_key = p.product_key
    JOIN `{PROJECT_ID}.{DATASET}.exchange_rates` e ON s.currency_code = e.currency AND s.order_date = e.date
""")[0]
print(f"  Sales with quantity <= 0: {bad_values['bad_quantity']:,}")
print(f"  Products with unit_price <= 0: {bad_values['bad_price']:,}")
print(f"  Exchange rates <= 0: {bad_values['bad_exchange_rate']:,}")

outliers = q(f"""
    SELECT
        MAX(s.quantity) as max_quantity,
        ROUND(MAX(s.quantity * p.unit_price * e.exchange_rate), 2) as max_line_value
    FROM `{PROJECT_ID}.{DATASET}.sales` s
    JOIN `{PROJECT_ID}.{DATASET}.products` p ON s.product_key = p.product_key
    JOIN `{PROJECT_ID}.{DATASET}.exchange_rates` e ON s.currency_code = e.currency AND s.order_date = e.date
""")[0]
print(f"\n  Largest single line item quantity: {outliers['max_quantity']:,}")
print(f"  Largest single line item value: EUR {outliers['max_line_value']:,.2f}")
print(
    "  (eyeball these -- if either looks absurd, e.g. thousands of units in one line, worth investigating)"
)


print("\n" + "=" * 70)
print("DONE. Review any 'CHECK THIS' or orphaned-row lines above with the team.")
print("=" * 70)
