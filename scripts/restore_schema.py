"""
Writes contracts/schema.md with the correct markdown structure.

Why this exists: the AI reads contracts/schema.md on every question. If that file
loses its markdown (## headings, `backticks`, | table pipes |) -- for example after
copying rendered text instead of the raw file -- the code finds NO tables and the AI
is sent no schema at all, so it invents column names.

Usage (from the project root):
    python scripts/restore_schema.py
"""

from pathlib import Path

SCHEMA = r"""# Database Schema

Source dataset: **Global Electronics Retailer** (Maven Analytics / Microsoft, public domain)

This is the shared reference for every layer of the system -- the LLM uses this to know what it can query, the data pipeline uses this as its target structure, and anyone writing SQL by hand should check here first instead of guessing column names.

---

## Table: `sales`
One row per line item within an order.

| Column | Type | Notes |
|---|---|---|
| order_date | DATE | When the order was placed |
| order_number | STRING | Order identifier -- multiple rows can share the same order_number (one per line item) |
| line_item | INTEGER | Line number within the order |
| product_key | INTEGER | Foreign key -> `products.product_key` |
| quantity | INTEGER | Units sold in this line item |
| customer_key | INTEGER | Foreign key -> `customers.customer_key` |
| store_key | INTEGER | Foreign key -> `stores.store_key` |
| currency_code | STRING | e.g. "USD", "EUR", "GBP" -- needed to convert to a common currency using `exchange_rates` |
| delivery_date | DATE | Can be null if not yet delivered |

## Table: `products`
One row per product.

| Column | Type | Notes |
|---|---|---|
| product_key | INTEGER | Primary key |
| product_name | STRING | |
| brand | STRING | |
| color | STRING | |
| unit_cost | DECIMAL | What it costs the retailer (cost per unit) |
| unit_price | DECIMAL | What the customer pays (selling price per unit) |
| category | STRING | e.g. "Audio", "Computers" |
| subcategory | STRING | e.g. "Headphones", "Laptops" |

**Cost and price columns:** the ONLY cost column is `unit_cost` and the ONLY price column is `unit_price`. There is no `cost`, `cost_price`, `product_cost`, `purchase_price` or `price` column -- never use those names.

## Table: `customers`
One row per customer.

| Column | Type | Notes |
|---|---|---|
| customer_key | INTEGER | Primary key |
| name | STRING | |
| gender | STRING | |
| city | STRING | |
| state | STRING | |
| zip_code | STRING | |
| country | STRING | |
| continent | STRING | |
| birthday | DATE | |

## Table: `stores`
One row per physical store.

**Updated after real data check (Pillar 1.1):** the real dataset does not include `city` or `store_name` -- removed from this schema so the AI and team never reference columns that don't actually exist. Stores can only be identified by `store_key`, `country`, and `state`.

**Online sales:** `store_key = 0` (with `country = 'Online'`, `state = 'Online'`) represents all online orders, not a physical location. Added during Pillar 1.1 cleaning since online orders in the raw data had no matching physical store.

**Important:** `stores` does NOT have a `continent` column. If a question asks about continent, it must be answered via `customers.continent` (the customer's continent), never through `stores` -- even though `stores` has a `country` column, it has no continent/region hierarchy at all.

| Column | Type | Notes |
|---|---|---|
| store_key | INTEGER | Primary key |
| country | STRING | |
| state | STRING | |
| square_meters | INTEGER | Store size |
| open_date | DATE | |

## Table: `exchange_rates`
One row per currency per date -- used to convert all sales into a common currency (recommend USD) for consistent revenue KPIs.

| Column | Type | Notes |
|---|---|---|
| date | DATE | |
| currency | STRING | Matches `sales.currency_code` |
| exchange_rate | DECIMAL | Rate to USD on that date |

---

## Relationships

```
sales.product_key   -> products.product_key
sales.customer_key  -> customers.customer_key
sales.store_key     -> stores.store_key
sales.currency_code + sales.order_date -> exchange_rates.currency + exchange_rates.date
```

---

## Business terms -> SQL mapping

The LLM should use this table when it sees these words in a user's question:

| Business term | SQL meaning |
|---|---|
| "revenue" / "sales" (always in USD) | `SUM(sales.quantity * products.unit_price * exchange_rates.exchange_rate)` |
| "units sold" / "volume" | `SUM(sales.quantity)` |
| "profit" | `SUM(sales.quantity * (products.unit_price - products.unit_cost) * exchange_rates.exchange_rate)` |
| "average order value" / "AOV" | total revenue divided by `COUNT(DISTINCT sales.order_number)` |
| "top product" | highest `SUM(quantity)` or `SUM(revenue)`, grouped by `product_name` |
| "by country" / "by region" | `GROUP BY customers.country` or `stores.country` -- confirm which one the user means (customer location vs. store location can differ) |
| "online sales" / "online orders" | `WHERE stores.store_key = 0` (or `stores.country = 'Online'`) -- this is the only "store" that isn't a physical location |
| "top-line" | same as "revenue" -- total sales before any costs |
| "basket size" / "order size" | same as "average order value" |
| "SKU" / "item" | a single `product_key` |
| "repeat customer" / "loyal customer" | a `customer_key` with more than 1 distinct `order_number` |
| "best-seller" | highest `SUM(quantity)`, not necessarily highest revenue -- confirm which the user means |
| "margin" / "profit margin" | profit divided by revenue, i.e. `SUM(quantity * (unit_price - unit_cost) * exchange_rate) / SUM(quantity * unit_price * exchange_rate)` |
| "delivered" / "undelivered" order | there is no status column -- `delivery_date IS NOT NULL` means delivered, `delivery_date IS NULL` means undelivered |

**Note:** if a question is genuinely ambiguous (e.g. "sales" could mean revenue or units), the assistant should ask a clarification question rather than guess -- see `api.md`.
"""

target = Path(__file__).resolve().parent.parent / "contracts" / "schema.md"
target.parent.mkdir(exist_ok=True)
if target.exists():
    backup = target.with_name("schema_backup.md")
    backup.write_text(
        target.read_text(encoding="utf-8", errors="replace"), encoding="utf-8"
    )
    print(f"Backed up the old file to {backup}")
target.write_text(SCHEMA, encoding="utf-8", newline="\n")
print(f"Wrote {target} ({len(SCHEMA.splitlines())} lines)")
