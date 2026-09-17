-- ============================================================
-- Talk-to-my-Data
-- BigQuery Data Warehouse Setup
--
-- Source of truth:
-- contracts/schema.md
--
-- Dataset:
-- retail_dw
--
-- IMPORTANT:
-- Replace YOUR_PROJECT_ID with the actual GCP project ID.
-- ============================================================


-- ============================================================
-- 1. SALES
-- One row per line item within an order.
-- ============================================================

CREATE TABLE IF NOT EXISTS `572029936014.retail_dw.sales`
(
    order_date DATE,
    order_number STRING,
    line_item INT64,
    product_key INT64,
    quantity INT64,
    customer_key INT64,
    store_key INT64,
    currency_code STRING,
    delivery_date DATE
)
PARTITION BY order_date
CLUSTER BY product_key, customer_key, store_key;


-- ============================================================
-- 2. PRODUCTS
-- One row per product.
-- ============================================================

CREATE TABLE IF NOT EXISTS `572029936014.retail_dw.products`
(
    product_key INT64,
    product_name STRING,
    brand STRING,
    color STRING,
    unit_cost NUMERIC,
    unit_price NUMERIC,
    category STRING,
    subcategory STRING
);


-- ============================================================
-- 3. CUSTOMERS
-- One row per customer.
-- ============================================================

CREATE TABLE IF NOT EXISTS `572029936014.retail_dw.customers`
(
    customer_key INT64,
    name STRING,
    gender STRING,
    city STRING,
    state STRING,
    zip_code STRING,
    country STRING,
    continent STRING,
    birthday DATE
);


-- ============================================================
-- 4. STORES
-- One row per physical store.
--
-- NOTE:
-- The real dataset does NOT contain city or store_name.
-- This follows contracts/schema.md exactly.
-- ============================================================

CREATE TABLE IF NOT EXISTS `572029936014.retail_dw.stores`
(
    store_key INT64,
    country STRING,
    state STRING,
    square_meters INT64,
    open_date DATE
);


-- ============================================================
-- 5. EXCHANGE RATES
-- One row per currency per date.
-- Used to convert sales into a common currency.
-- ============================================================

CREATE TABLE IF NOT EXISTS `572029936014.retail_dw.exchange_rates`
(
    date DATE,
    currency STRING,
    exchange_rate NUMERIC
)
PARTITION BY date
CLUSTER BY currency;