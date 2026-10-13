"""
Full Exploratory Data Analysis -- Talk-to-my-Data
 
Runs a comprehensive set of queries against the real BigQuery warehouse and
prints a full picture of the dataset: scale, geography, time, products,
customers, orders, currency, and data quality. Also saves 3 charts as PNGs
for use in presentations.
 
Usage:
    python scripts/eda.py
 
Output:
    - Full printed report in the terminal
    - 3 PNG charts saved to scripts/eda_charts/
"""
 
import os
from pathlib import Path
from dotenv import load_dotenv
from google.cloud import bigquery
import matplotlib
matplotlib.use("Agg")  # no display needed, just save files
import matplotlib.pyplot as plt
 
load_dotenv()
 
PROJECT_ID = os.getenv("GCP_PROJECT_ID")
DATASET = "retail_dw"
CHARTS_DIR = Path(__file__).parent / "eda_charts"
CHARTS_DIR.mkdir(exist_ok=True)
 
client = bigquery.Client(project=PROJECT_ID)
 
 
def q(sql):
    """Run a query and return results as a list of dict rows."""
    return [dict(row) for row in client.query(sql).result()]
 
 
def section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)
 
 
# =====================================================================
# 1. SCALE -- how big is this dataset
# =====================================================================
section("1. DATASET SCALE")
 
for table in ["sales", "products", "customers", "stores", "exchange_rates"]:
    count = q(f"SELECT COUNT(*) as n FROM `{PROJECT_ID}.{DATASET}.{table}`")[0]["n"]
    print(f"  {table}: {count:,} rows")
 
date_range = q(f"""
    SELECT MIN(order_date) as earliest, MAX(order_date) as latest
    FROM `{PROJECT_ID}.{DATASET}.sales`
""")[0]
print(f"\n  Date range: {date_range['earliest']} to {date_range['latest']}")
 
 
# =====================================================================
# 2. GEOGRAPHY -- where does business happen
# =====================================================================
section("2. GEOGRAPHIC COVERAGE")
 
countries = q(f"SELECT DISTINCT country FROM `{PROJECT_ID}.{DATASET}.stores` ORDER BY country")
print(f"  Markets ({len(countries)}): {', '.join(c['country'] for c in countries)}")
 
revenue_by_country = q(f"""
    SELECT c.country, ROUND(SUM(s.quantity * p.unit_price), 2) as revenue
    FROM `{PROJECT_ID}.{DATASET}.sales` s
    JOIN `{PROJECT_ID}.{DATASET}.customers` c ON s.customer_key = c.customer_key
    JOIN `{PROJECT_ID}.{DATASET}.products` p ON s.product_key = p.product_key
    GROUP BY c.country ORDER BY revenue DESC
""")
print("\n  Revenue by customer country:")
for r in revenue_by_country:
    print(f"    {r['country']:20} EUR {r['revenue']:>15,.2f}")
 
 
# =====================================================================
# 3. TIME -- trends and seasonality
# =====================================================================
section("3. REVENUE OVER TIME")
 
by_year = q(f"""
    SELECT EXTRACT(YEAR FROM s.order_date) as year,
           ROUND(SUM(s.quantity * p.unit_price), 2) as revenue
    FROM `{PROJECT_ID}.{DATASET}.sales` s
    JOIN `{PROJECT_ID}.{DATASET}.products` p ON s.product_key = p.product_key
    GROUP BY year ORDER BY year
""")
print("  By year:")
for r in by_year:
    print(f"    {r['year']}: EUR {r['revenue']:,.2f}")
 
by_month = q(f"""
    SELECT EXTRACT(MONTH FROM s.order_date) as month,
           ROUND(SUM(s.quantity * p.unit_price), 2) as revenue
    FROM `{PROJECT_ID}.{DATASET}.sales` s
    JOIN `{PROJECT_ID}.{DATASET}.products` p ON s.product_key = p.product_key
    GROUP BY month ORDER BY month
""")
print("\n  By calendar month (seasonality, all years combined):")
for r in by_month:
    print(f"    Month {r['month']:>2}: EUR {r['revenue']:,.2f}")
 
# Chart: revenue by year
years = [str(r["year"]) for r in by_year]
year_revenue = [r["revenue"] / 1_000_000 for r in by_year]
plt.figure(figsize=(8, 4.5))
plt.bar(years, year_revenue, color="#FF4F6D")
plt.title("Revenue by Year (EUR millions)")
plt.ylabel("EUR millions")
plt.tight_layout()
plt.savefig(CHARTS_DIR / "revenue_by_year.png", dpi=150)
plt.close()
 
# Chart: revenue by month (seasonality)
months = [str(r["month"]) for r in by_month]
month_revenue = [r["revenue"] / 1_000_000 for r in by_month]
plt.figure(figsize=(8, 4.5))
plt.plot(months, month_revenue, marker="o", color="#12173B")
plt.title("Revenue by Calendar Month (seasonality)")
plt.ylabel("EUR millions")
plt.xlabel("Month")
plt.tight_layout()
plt.savefig(CHARTS_DIR / "revenue_by_month.png", dpi=150)
plt.close()
 
 
# =====================================================================
# 4. PRODUCTS -- what sells
# =====================================================================
section("4. PRODUCT ANALYSIS")
 
top_categories = q(f"""
    SELECT p.category, ROUND(SUM(s.quantity * p.unit_price), 2) as revenue
    FROM `{PROJECT_ID}.{DATASET}.sales` s
    JOIN `{PROJECT_ID}.{DATASET}.products` p ON s.product_key = p.product_key
    GROUP BY p.category ORDER BY revenue DESC LIMIT 5
""")
print("  Top 5 categories by revenue:")
for r in top_categories:
    print(f"    {r['category']:25} EUR {r['revenue']:>15,.2f}")
 
top_brands = q(f"""
    SELECT p.brand, ROUND(SUM(s.quantity * p.unit_price), 2) as revenue
    FROM `{PROJECT_ID}.{DATASET}.sales` s
    JOIN `{PROJECT_ID}.{DATASET}.products` p ON s.product_key = p.product_key
    GROUP BY p.brand ORDER BY revenue DESC LIMIT 5
""")
print("\n  Top 5 brands by revenue:")
for r in top_brands:
    print(f"    {r['brand']:25} EUR {r['revenue']:>15,.2f}")
 
price_stats = q(f"""
    SELECT ROUND(MIN(unit_price), 2) as min_price, ROUND(MAX(unit_price), 2) as max_price,
           ROUND(AVG(unit_price), 2) as avg_price
    FROM `{PROJECT_ID}.{DATASET}.products`
""")[0]
print(f"\n  Price range: EUR {price_stats['min_price']} - EUR {price_stats['max_price']} (avg: EUR {price_stats['avg_price']})")
 
 
# =====================================================================
# 5. CUSTOMERS -- who buys
# =====================================================================
section("5. CUSTOMER ANALYSIS")
 
customer_stats = q(f"""
    SELECT COUNT(DISTINCT customer_key) as distinct_customers,
           COUNT(DISTINCT order_number) as distinct_orders,
           ROUND(COUNT(DISTINCT order_number) / COUNT(DISTINCT customer_key), 1) as avg_orders_per_customer
    FROM `{PROJECT_ID}.{DATASET}.sales`
""")[0]
print(f"  Distinct customers: {customer_stats['distinct_customers']:,}")
print(f"  Distinct orders: {customer_stats['distinct_orders']:,}")
print(f"  Average orders per customer: {customer_stats['avg_orders_per_customer']}")
 
gender_split = q(f"""
    SELECT gender, COUNT(*) as n,
           ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) as pct
    FROM `{PROJECT_ID}.{DATASET}.customers`
    GROUP BY gender
""")
print("\n  Gender split:")
for r in gender_split:
    print(f"    {r['gender']}: {r['n']:,} ({r['pct']}%)")
 
age_stats = q(f"""
    SELECT ROUND(AVG(DATE_DIFF(CURRENT_DATE(), birthday, YEAR)), 1) as avg_age
    FROM `{PROJECT_ID}.{DATASET}.customers`
""")[0]
print(f"\n  Average customer age (as of today): {age_stats['avg_age']} years")
 
 
# =====================================================================
# 6. ORDERS -- transaction patterns
# =====================================================================
section("6. ORDER VALUE DISTRIBUTION")
 
order_dist = q(f"""
    WITH order_totals AS (
        SELECT s.order_number, SUM(s.quantity * p.unit_price) AS order_value
        FROM `{PROJECT_ID}.{DATASET}.sales` s
        JOIN `{PROJECT_ID}.{DATASET}.products` p ON s.product_key = p.product_key
        GROUP BY s.order_number
    )
    SELECT
        CASE
            WHEN order_value < 100 THEN '1. Under 100'
            WHEN order_value < 500 THEN '2. 100-500'
            WHEN order_value < 1000 THEN '3. 500-1000'
            WHEN order_value < 2500 THEN '4. 1000-2500'
            WHEN order_value < 5000 THEN '5. 2500-5000'
            ELSE '6. Over 5000'
        END AS value_range, COUNT(*) as n
    FROM order_totals GROUP BY value_range ORDER BY value_range
""")
print("  Orders by value range:")
for r in order_dist:
    print(f"    {r['value_range']:15} {r['n']:>6,} orders")
 
aov = q(f"""
    SELECT ROUND(SUM(s.quantity * p.unit_price) / COUNT(DISTINCT s.order_number), 2) as aov
    FROM `{PROJECT_ID}.{DATASET}.sales` s
    JOIN `{PROJECT_ID}.{DATASET}.products` p ON s.product_key = p.product_key
""")[0]
print(f"\n  Average Order Value (AOV): EUR {aov['aov']}")
 
# Chart: order value distribution
ranges = [r["value_range"][3:] for r in order_dist]
counts = [r["n"] for r in order_dist]
plt.figure(figsize=(8, 4.5))
plt.bar(ranges, counts, color="#2DD4BF")
plt.title("Order Value Distribution")
plt.ylabel("Number of orders")
plt.xticks(rotation=20)
plt.tight_layout()
plt.savefig(CHARTS_DIR / "order_value_distribution.png", dpi=150)
plt.close()
 
 
# =====================================================================
# 7. CURRENCY -- how sales are spread across currencies
# =====================================================================
section("7. CURRENCY MIX")
 
currency_mix = q(f"""
    SELECT currency_code, COUNT(*) as n
    FROM `{PROJECT_ID}.{DATASET}.sales`
    GROUP BY currency_code ORDER BY n DESC
""")
print("  Transactions by currency:")
for r in currency_mix:
    print(f"    {r['currency_code']}: {r['n']:,}")
 
 
# =====================================================================
# 8. DATA QUALITY -- anything worth flagging
# =====================================================================
section("8. DATA QUALITY SUMMARY")
 
delivery_stats = q(f"""
    SELECT
        COUNT(*) as total,
        COUNTIF(delivery_date IS NULL) as missing_delivery
    FROM `{PROJECT_ID}.{DATASET}.sales`
""")[0]
pct_missing = round(delivery_stats["missing_delivery"] / delivery_stats["total"] * 100, 1)
print(f"  Missing delivery_date: {delivery_stats['missing_delivery']:,} of {delivery_stats['total']:,} ({pct_missing}%) -- expected, these are undelivered orders")
 
 
# =====================================================================
# 9. SALES CHANNEL -- online vs physical stores
# =====================================================================
section("9. SALES CHANNEL: ONLINE VS PHYSICAL")
 
channel_split = q(f"""
    SELECT
        CASE WHEN s.store_key = 0 THEN 'Online' ELSE 'Physical store' END as channel,
        ROUND(SUM(s.quantity * p.unit_price), 2) as revenue,
        COUNT(DISTINCT s.order_number) as orders
    FROM `{PROJECT_ID}.{DATASET}.sales` s
    JOIN `{PROJECT_ID}.{DATASET}.products` p ON s.product_key = p.product_key
    GROUP BY channel
""")
for r in channel_split:
    print(f"  {r['channel']:15} EUR {r['revenue']:>15,.2f}  ({r['orders']:,} orders)")
 
 
# =====================================================================
# 10. TOP INDIVIDUAL PRODUCTS -- not just categories/brands
# =====================================================================
section("10. TOP 10 INDIVIDUAL PRODUCTS BY REVENUE")
 
top_products = q(f"""
    SELECT p.product_name, p.brand, ROUND(SUM(s.quantity * p.unit_price), 2) as revenue
    FROM `{PROJECT_ID}.{DATASET}.sales` s
    JOIN `{PROJECT_ID}.{DATASET}.products` p ON s.product_key = p.product_key
    GROUP BY p.product_name, p.brand ORDER BY revenue DESC LIMIT 10
""")
for i, r in enumerate(top_products, 1):
    print(f"  {i:>2}. {r['product_name']:35} ({r['brand']:12}) EUR {r['revenue']:>12,.2f}")
 
 
# =====================================================================
# 11. CUSTOMER LOYALTY -- order frequency distribution
# =====================================================================
section("11. CUSTOMER ORDER FREQUENCY (loyalty pattern)")
 
order_freq = q(f"""
    WITH customer_orders AS (
        SELECT customer_key, COUNT(DISTINCT order_number) as n_orders
        FROM `{PROJECT_ID}.{DATASET}.sales`
        GROUP BY customer_key
    )
    SELECT
        CASE
            WHEN n_orders = 1 THEN '1 order'
            WHEN n_orders = 2 THEN '2 orders'
            WHEN n_orders BETWEEN 3 AND 5 THEN '3-5 orders'
            ELSE '6+ orders'
        END as freq_group,
        COUNT(*) as n_customers
    FROM customer_orders
    GROUP BY freq_group ORDER BY freq_group
""")
print("  Customers by number of orders placed:")
for r in order_freq:
    print(f"    {r['freq_group']:15} {r['n_customers']:>6,} customers")
 
# Chart: customer order frequency
freq_labels = [r["freq_group"] for r in order_freq]
freq_counts = [r["n_customers"] for r in order_freq]
plt.figure(figsize=(8, 4.5))
plt.bar(freq_labels, freq_counts, color="#FF4F6D")
plt.title("Customer Order Frequency")
plt.ylabel("Number of customers")
plt.tight_layout()
plt.savefig(CHARTS_DIR / "customer_order_frequency.png", dpi=150)
plt.close()
 
 
# =====================================================================
# 12. REVENUE BY CONTINENT -- broader geographic view
# =====================================================================
section("12. REVENUE BY CONTINENT")
 
by_continent = q(f"""
    SELECT c.continent, ROUND(SUM(s.quantity * p.unit_price), 2) as revenue
    FROM `{PROJECT_ID}.{DATASET}.sales` s
    JOIN `{PROJECT_ID}.{DATASET}.customers` c ON s.customer_key = c.customer_key
    JOIN `{PROJECT_ID}.{DATASET}.products` p ON s.product_key = p.product_key
    GROUP BY c.continent ORDER BY revenue DESC
""")
for r in by_continent:
    print(f"  {r['continent']:15} EUR {r['revenue']:>15,.2f}")
 
 
# =====================================================================
# 13. STORE SIZE VS PERFORMANCE -- does bigger mean better
# =====================================================================
section("13. STORE SIZE VS PERFORMANCE")
 
store_perf = q(f"""
    SELECT st.square_meters, SUM(s.quantity) as units_sold
    FROM `{PROJECT_ID}.{DATASET}.sales` s
    JOIN `{PROJECT_ID}.{DATASET}.stores` st ON s.store_key = st.store_key
    WHERE st.store_key != 0 AND st.square_meters IS NOT NULL
    GROUP BY st.square_meters
""")
if store_perf:
    sizes = [r["square_meters"] for r in store_perf]
    units = [r["units_sold"] for r in store_perf]
    correlation = None
    try:
        import numpy as np
        correlation = round(float(np.corrcoef(sizes, units)[0, 1]), 2)
    except ImportError:
        pass
    print(f"  Correlation between store size and units sold: {correlation if correlation is not None else 'numpy not installed, skipped'}")
    print("  (Closer to 1.0 = bigger stores sell more; closer to 0 = size doesn't predict performance)")
 
 
 
# =====================================================================
# 14. NEW RELATIONSHIPS -- price/quantity, age/spending, channel/AOV
# =====================================================================
section("14. BUSINESS RELATIONSHIPS")
 
price_qty = q(f"""
    SELECT
        CASE
            WHEN p.unit_price < 100 THEN '1. Under 100'
            WHEN p.unit_price < 500 THEN '2. 100-500'
            WHEN p.unit_price < 1000 THEN '3. 500-1000'
            ELSE '4. Over 1000'
        END as price_band,
        SUM(s.quantity) as total_units
    FROM `{PROJECT_ID}.{DATASET}.sales` s
    JOIN `{PROJECT_ID}.{DATASET}.products` p ON s.product_key = p.product_key
    GROUP BY price_band ORDER BY price_band
""")
print("  Price band vs units sold (does price affect volume?):")
for r in price_qty:
    print(f"    {r['price_band']:15} {r['total_units']:>10,} units")
 
age_spending = q(f"""
    SELECT
        CASE
            WHEN DATE_DIFF(CURRENT_DATE(), c.birthday, YEAR) < 30 THEN '1. Under 30'
            WHEN DATE_DIFF(CURRENT_DATE(), c.birthday, YEAR) < 45 THEN '2. 30-45'
            WHEN DATE_DIFF(CURRENT_DATE(), c.birthday, YEAR) < 60 THEN '3. 45-60'
            ELSE '4. 60+'
        END as age_band,
        ROUND(SUM(s.quantity * p.unit_price), 2) as revenue
    FROM `{PROJECT_ID}.{DATASET}.sales` s
    JOIN `{PROJECT_ID}.{DATASET}.customers` c ON s.customer_key = c.customer_key
    JOIN `{PROJECT_ID}.{DATASET}.products` p ON s.product_key = p.product_key
    GROUP BY age_band ORDER BY age_band
""")
print("\n  Customer age band vs revenue:")
for r in age_spending:
    print(f"    {r['age_band']:15} EUR {r['revenue']:>15,.2f}")
 
channel_aov = q(f"""
    SELECT
        CASE WHEN s.store_key = 0 THEN 'Online' ELSE 'Physical' END as channel,
        ROUND(SUM(s.quantity * p.unit_price) / COUNT(DISTINCT s.order_number), 2) as aov
    FROM `{PROJECT_ID}.{DATASET}.sales` s
    JOIN `{PROJECT_ID}.{DATASET}.products` p ON s.product_key = p.product_key
    GROUP BY channel
""")
print("\n  Average Order Value, online vs physical:")
for r in channel_aov:
    print(f"    {r['channel']:15} EUR {r['aov']:>10,.2f}")
 
print("\n" + "=" * 70)
print(f"DONE. 4 charts saved to {CHARTS_DIR}/")
print("=" * 70)
 