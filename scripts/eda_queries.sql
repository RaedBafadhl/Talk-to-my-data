-- ============================================================
-- Exploratory Data Analysis queries for Friday's Service Development update
-- Run each of these in BigQuery Console and note the results
-- ============================================================
 
-- 1. Overall date range covered by the data
SELECT MIN(order_date) AS earliest_order, MAX(order_date) AS latest_order
FROM `tgs-talk-to-data.retail_dw.sales`;
 
-- 2. Which countries are covered
SELECT DISTINCT country FROM `tgs-talk-to-data.retail_dw.stores` ORDER BY country;
 
-- 3. Top 5 product categories by revenue
SELECT
  p.category,
  ROUND(SUM(s.quantity * p.unit_price * e.exchange_rate), 2) AS revenue
FROM `tgs-talk-to-data.retail_dw.sales` s
JOIN `tgs-talk-to-data.retail_dw.products` p ON s.product_key = p.product_key
JOIN `tgs-talk-to-data.retail_dw.exchange_rates` e
  ON s.currency_code = e.currency AND s.order_date = e.date
GROUP BY p.category
ORDER BY revenue DESC
LIMIT 5;
 
-- 4. Revenue by year, to show trend
SELECT
  EXTRACT(YEAR FROM s.order_date) AS year,
  ROUND(SUM(s.quantity * p.unit_price * e.exchange_rate), 2) AS revenue
FROM `tgs-talk-to-data.retail_dw.sales` s
JOIN `tgs-talk-to-data.retail_dw.products` p ON s.product_key = p.product_key
JOIN `tgs-talk-to-data.retail_dw.exchange_rates` e
  ON s.currency_code = e.currency AND s.order_date = e.date
GROUP BY year
ORDER BY year;
 
-- 5. How many distinct customers, and how many orders on average per customer
SELECT
  COUNT(DISTINCT customer_key) AS distinct_customers,
  COUNT(DISTINCT order_number) AS distinct_orders,
  ROUND(COUNT(DISTINCT order_number) / COUNT(DISTINCT customer_key), 1) AS avg_orders_per_customer
FROM `tgs-talk-to-data.retail_dw.sales`;
 