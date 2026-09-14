import pandas as pd
from pathlib import Path
 
RAW_DIR = Path("data")
CLEAN_DIR = Path("data/cleaned")
CLEAN_DIR.mkdir(exist_ok=True)
 
 
def read_csv_any_encoding(filepath):
    for encoding in ["utf-8", "utf-8-sig", "cp1252", "latin-1"]:
        try:
            return pd.read_csv(filepath, encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Could not read {filepath} with any common encoding.")
 
 
def clean_sales():
    df = read_csv_any_encoding(RAW_DIR / "sales.csv")
    df = df.rename(columns={
        "Order Number": "order_number",
        "Line Item": "line_item",
        "Order Date": "order_date",
        "Delivery Date": "delivery_date",
        "CustomerKey": "customer_key",
        "StoreKey": "store_key",
        "ProductKey": "product_key",
        "Quantity": "quantity",
        "Currency Code": "currency_code",
    })
    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    # delivery_date is legitimately missing for undelivered orders -- keep as NaT, don't drop rows
    df["delivery_date"] = pd.to_datetime(df["delivery_date"], errors="coerce")
    df = df[["order_date", "order_number", "line_item", "product_key", "quantity",
              "customer_key", "store_key", "currency_code", "delivery_date"]]
    return df
 
 
def clean_products():
    df = read_csv_any_encoding(RAW_DIR / "products.csv")
    df = df.rename(columns={
        "ProductKey": "product_key",
        "Product Name": "product_name",
        "Brand": "brand",
        "Color": "color",
        "Unit Cost USD": "unit_cost",
        "Unit Price USD": "unit_price",
        "Category": "category",
        "Subcategory": "subcategory",
    })
    # Prices likely have "$" and "," in them -- strip those before converting to numbers
    for col in ["unit_cost", "unit_price"]:
        df[col] = (
            df[col].astype(str)
            .str.replace("$", "", regex=False)
            .str.replace(",", "", regex=False)
            .astype(float)
        )
    # Drop CategoryKey / SubcategoryKey -- not in schema.md, not needed
    df = df[["product_key", "product_name", "brand", "color", "unit_cost",
              "unit_price", "category", "subcategory"]]
    return df
 
 
def clean_customers():
    df = read_csv_any_encoding(RAW_DIR / "customers.csv")
    df = df.rename(columns={
        "CustomerKey": "customer_key",
        "Gender": "gender",
        "Name": "name",
        "City": "city",
        "State": "state",
        "Zip Code": "zip_code",
        "Country": "country",
        "Continent": "continent",
        "Birthday": "birthday",
    })
    df["birthday"] = pd.to_datetime(df["birthday"], errors="coerce")
    # Drop "State Code" -- not in schema.md, "state" already covers it
    df = df[["customer_key", "name", "gender", "city", "state", "zip_code",
              "country", "continent", "birthday"]]
    return df
 
 
def clean_stores():
    df = read_csv_any_encoding(RAW_DIR / "stores.csv")
    df = df.rename(columns={
        "StoreKey": "store_key",
        "Country": "country",
        "State": "state",
        "Square Meters": "square_meters",
        "Open Date": "open_date",
    })
    df["open_date"] = pd.to_datetime(df["open_date"], errors="coerce")
    # Note: no city / store_name in the real data -- schema.md was updated to match
    df = df[["store_key", "country", "state", "square_meters", "open_date"]]
    return df
 
 
def clean_exchange_rates():
    df = read_csv_any_encoding(RAW_DIR / "exchange_rates.csv")
    df = df.rename(columns={
        "Date": "date",
        "Currency": "currency",
        "Exchange": "exchange_rate",
    })
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[["date", "currency", "exchange_rate"]]
    return df
 
 
if __name__ == "__main__":
    tables = {
        "sales": clean_sales,
        "products": clean_products,
        "customers": clean_customers,
        "stores": clean_stores,
        "exchange_rates": clean_exchange_rates,
    }
 
    for name, clean_fn in tables.items():
        print(f"Cleaning {name}...")
        df = clean_fn()
        out_path = CLEAN_DIR / f"{name}.csv"
        df.to_csv(out_path, index=False)
        print(f"  -> {len(df)} rows written to {out_path}")
        print(f"  -> columns: {list(df.columns)}")
        print(f"  -> dtypes:\n{df.dtypes.to_string()}\n")
 
    print("Done. Cleaned files are in data/cleaned/, ready to load into BigQuery.")