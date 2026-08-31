# Database Schema

Source dataset: **Global Electronics Retailer** (Maven Analytics / Microsoft, public domain)

This is the shared reference for every layer of the system — the LLM uses this to know what it can query, the data pipeline uses this as its target structure, and anyone writing SQL by hand should check here first instead of guessing column names.

---

## Table: `sales`
One row per line item within an order.

| Column | Type | Notes |
|---|---|---|
| order_date | DATE | When the order was placed |
| order_number | STRING | Order identifier — multiple rows can share the same order_number (one per line item) |
| line_item | INTEGER | Line number within the order |
| product_key | INTEGER | Foreign key → `products.product_key` |
| quantity | INTEGER | Units sold in this line item |
| customer_key | INTEGER | Foreign key → `customers.customer_key` |
| store_key | INTEGER | Foreign key → `stores.store_key` |
| currency_code | STRING | e.g. "USD", "EUR", "GBP" — needed to convert to a common currency using `exchange_rates` |
| delivery_date | DATE | Can be null if not yet delivered |

## Table: `products`
One row per product.

| Column | Type | Notes |
|---|---|---|
| product_key | INTEGER | Primary key |
| product_name | STRING | |
| brand | STRING | |
| color | STRING | |
| unit_cost | DECIMAL | What it costs the retailer |
| unit_price | DECIMAL | What the customer pays |
| category | STRING | e.g. "Audio", "Computers" |
| subcategory | STRING | e.g. "Headphones", "Laptops" |

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

| Column | Type | Notes |
|---|---|---|
| store_key | INTEGER | Primary key |
| country | STRING | |
| state | STRING | |
| city | STRING | |
| store_name | STRING | |
| square_meters | INTEGER | Store size |
| open_date | DATE | |

## Table: `exchange_rates`
One row per currency per date — used to convert all sales into a common currency (recommend USD) for consistent revenue KPIs.

| Column | Type | Notes |
|---|---|---|
| date | DATE | |
| currency | STRING | Matches `sales.currency_code` |
| exchange_rate | DECIMAL | Rate to USD on that date |

---

## Relationshipssales.

product_key → products.product_key
sales.customer_key → customers.customer_key
sales.store_key → stores.store_key
sales.currency_code + sales.order_date → exchange_rates.currency + exchange_rates.date

---

## Business terms → SQL mapping

The LLM should use this table when it sees these words in a user's question:

| Business term | SQL meaning |
|---|---|
| "revenue" / "sales" (in € or $) | `SUM(sales.quantity * products.unit_price * exchange_rates.exchange_rate)` |
| "units sold" / "volume" | `SUM(sales.quantity)` |
| "profit" | `SUM(sales.quantity * (products.unit_price - products.unit_cost) * exchange_rates.exchange_rate)` |
| "average order value" / "AOV" | total revenue ÷ `COUNT(DISTINCT sales.order_number)` |
| "top product" | highest `SUM(quantity)` or `SUM(revenue)`, grouped by `product_name` |
| "by country" / "by region" | `GROUP BY customers.country` or `stores.country` — confirm which one the user means |

**Note:** if a question is genuinely ambiguous, the assistant should ask a clarification question rather than guess — see `api.md`.

