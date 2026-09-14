import pandas as pd
from pathlib import Path

DATA_DIR = Path("data")

FILES = {
    "sales": "sales.csv",
    "products": "products.csv",
    "customers": "customers.csv",
    "stores": "stores.csv",
    "exchange_rates": "exchange_rates.csv",
}

# What we AGREED the columns should be called, per contracts/schema.md.
# If the real file has different names (e.g. "Order Date" instead of
# "order_date"), this script will flag the mismatch so you know what to rename.
EXPECTED_COLUMNS = {
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
    "stores": [
        "store_key",
        "country",
        "state",
        "city",
        "store_name",
        "square_meters",
        "open_date",
    ],
    "exchange_rates": ["date", "currency", "exchange_rate"],
}

print("=" * 70)
print("DATA HEALTH CHECK")
print("=" * 70)

for table_name, filename in FILES.items():
    filepath = DATA_DIR / filename
    print(f"\n{'-' * 70}")
    print(f"TABLE: {table_name}  (file: {filename})")
    print("-" * 70)

    if not filepath.exists():
        print(
            f"[MISSING FILE] Not found at {filepath} -- check the filename matches exactly."
        )
        continue

    df = None
    used_encoding = None
    for encoding in ["utf-8", "utf-8-sig", "cp1252", "latin-1"]:
        try:
            df = pd.read_csv(filepath, encoding=encoding)
            used_encoding = encoding
            break
        except UnicodeDecodeError:
            continue

    if df is None:
        print(f"[ERROR] Could not read {filepath} with any common encoding.")
        continue

    if used_encoding != "utf-8":
        print(
            f"[NOTE] File needed encoding='{used_encoding}' instead of standard utf-8 -- remember this for the loading script later."
        )

    # 1. Row count
    print(f"Rows: {len(df)}")

    # 2. Actual columns vs expected columns
    actual_cols = list(df.columns)
    expected_cols = EXPECTED_COLUMNS[table_name]
    print(f"\nActual columns in file:   {actual_cols}")
    print(f"Expected (per schema.md): {expected_cols}")

    if actual_cols == expected_cols:
        print("[OK] Column names match schema.md exactly.")
    else:
        print(
            "[MISMATCH] Column names DON'T match schema.md -- you'll need to rename these before loading to BigQuery."
        )

    # 3. Missing values
    missing = df.isnull().sum()
    missing = missing[missing > 0]
    if missing.empty:
        print("\n[OK] No missing values in any column.")
    else:
        print("\n[MISSING VALUES] found:")
        for col, count in missing.items():
            print(f"   {col}: {count} missing ({count / len(df):.1%})")

    # 4. Data types -- flag anything that looks like a date but isn't parsed as one
    print("\nData types:")
    for col in df.columns:
        dtype = df[col].dtype
        looks_like_date = "date" in col.lower()
        flag = (
            " [WARN: looks like a date but isn't parsed as one]"
            if (looks_like_date and dtype == "object")
            else ""
        )
        print(f"   {col}: {dtype}{flag}")

print(f"\n{'=' * 70}")
print("Next steps: fix any [MISMATCH]/[WARN] items above (rename columns, parse dates,")
print("handle missing values) before writing the BigQuery loading script.")
print("=" * 70)
