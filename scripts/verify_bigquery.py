"""
Pillar 1.2 -- BigQuery verification
 
Run this after Fares finishes loading the tables, to confirm the warehouse
is set up correctly before Pillar 2 starts building on top of it.
 
Usage:
    python scripts/verify_bigquery.py
"""
 
import os
from dotenv import load_dotenv
from google.cloud import bigquery
 
load_dotenv()
project_id = os.getenv("GCP_PROJECT_ID")
client = bigquery.Client(project=project_id)
 
# Update this if your team used a different dataset name
DATASET = "retail_dw"
 
EXPECTED_TABLES = {
    "sales": {
        "columns": ["order_date", "order_number", "line_item", "product_key", "quantity",
                    "customer_key", "store_key", "currency_code", "delivery_date"],
        "expected_rows": 62884,
        "should_be_partitioned": True,
    },
    "products": {
        "columns": ["product_key", "product_name", "brand", "color", "unit_cost",
                    "unit_price", "category", "subcategory"],
        "expected_rows": 2517,
        "should_be_partitioned": False,
    },
    "customers": {
        "columns": ["customer_key", "name", "gender", "city", "state", "zip_code",
                    "country", "continent", "birthday"],
        "expected_rows": 15266,
        "should_be_partitioned": False,
    },
    "stores": {
        "columns": ["store_key", "country", "state", "square_meters", "open_date"],
        "expected_rows": 67,  # 66 real stores + 1 added "Online" row for store_key=0
        "should_be_partitioned": False,
    },
    "exchange_rates": {
        "columns": ["date", "currency", "exchange_rate"],
        "expected_rows": 11215,
        "should_be_partitioned": False,  # partitioned in practice, but not required -- won't fail if missing
    },
}
 
print("=" * 70)
print(f"BIGQUERY VERIFICATION -- dataset: {DATASET}")
print("=" * 70)
 
try:
    dataset_ref = client.dataset(DATASET)
    client.get_dataset(dataset_ref)
    print(f"[OK] Dataset '{DATASET}' exists\n")
except Exception as e:
    print(f"[FAIL] Dataset '{DATASET}' not found: {e}")
    print("Check the DATASET name at the top of this script matches what Fares actually used.")
    exit(1)
 
all_good = True
 
for table_name, expected in EXPECTED_TABLES.items():
    print("-" * 70)
    print(f"TABLE: {table_name}")
    print("-" * 70)
 
    table_id = f"{project_id}.{DATASET}.{table_name}"
    try:
        table = client.get_table(table_id)
    except Exception as e:
        print(f"[FAIL] Table not found: {e}")
        all_good = False
        continue
 
    # Check columns
    actual_cols = [field.name for field in table.schema]
    if actual_cols == expected["columns"]:
        print("[OK] Columns match schema.md exactly")
    else:
        print(f"[MISMATCH] Actual: {actual_cols}")
        print(f"           Expected: {expected['columns']}")
        all_good = False
 
    # Check row count
    actual_rows = table.num_rows
    if actual_rows == expected["expected_rows"]:
        print(f"[OK] Row count matches: {actual_rows}")
    else:
        print(f"[MISMATCH] Row count is {actual_rows}, expected {expected['expected_rows']}")
        all_good = False
 
    # Check partitioning
    is_partitioned = table.time_partitioning is not None
    if expected["should_be_partitioned"] and is_partitioned:
        print(f"[OK] Partitioned by: {table.time_partitioning.field}")
    elif expected["should_be_partitioned"] and not is_partitioned:
        print("[MISSING] This table should be partitioned by order_date but isn't")
        all_good = False
    elif not expected["should_be_partitioned"]:
        print("[OK] Partitioning not required for this table")
 
    print()
 
print("=" * 70)
if all_good:
    print("ALL CHECKS PASSED -- Pillar 1.2 is genuinely ready for Pillar 2.")
else:
    print("SOME CHECKS FAILED -- see [MISMATCH]/[MISSING]/[FAIL] above before marking 1.2 done.")
print("=" * 70)
 
# Bonus: run one real test query
print("\nRunning a test query (top 3 revenue days)...")
query = f"""
SELECT order_date, SUM(quantity) as units_sold
FROM `{project_id}.{DATASET}.sales`
GROUP BY order_date
ORDER BY units_sold DESC
LIMIT 3
"""
try:
    results = client.query(query).result()
    for row in results:
        print(f"   {row.order_date}: {row.units_sold} units")
    print("[OK] Test query ran successfully -- data is genuinely queryable.")
except Exception as e:
    print(f"[FAIL] Test query failed: {e}")