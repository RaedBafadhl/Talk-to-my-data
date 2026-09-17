# ============================================================
# Talk-to-my-Data
# Load cleaned CSV files into BigQuery
# ============================================================

$ErrorActionPreference = "Stop"

# Get currently configured GCP project
$PROJECT_ID = (gcloud.cmd config get-value project).Trim()

if (-not $PROJECT_ID) {
    Write-Error "No GCP project is configured."
    exit 1
}

Write-Host "Using GCP project: $PROJECT_ID"

# ------------------------------------------------------------
# 1. SALES
# ------------------------------------------------------------

Write-Host ""
Write-Host "Loading sales..."

bq.cmd load `
    --location=europe-west4 `
    --source_format=CSV `
    --skip_leading_rows=1 `
    "${PROJECT_ID}:retail_dw.sales" `
    ".\data\cleaned\sales.csv"

if ($LASTEXITCODE -ne 0) {
    throw "Loading sales failed."
}

# ------------------------------------------------------------
# 2. PRODUCTS
# ------------------------------------------------------------

Write-Host ""
Write-Host "Loading products..."

bq.cmd load `
    --location=europe-west4 `
    --source_format=CSV `
    --skip_leading_rows=1 `
    "${PROJECT_ID}:retail_dw.products" `
    ".\data\cleaned\products.csv"

if ($LASTEXITCODE -ne 0) {
    throw "Loading products failed."
}

# ------------------------------------------------------------
# 3. CUSTOMERS
# ------------------------------------------------------------

Write-Host ""
Write-Host "Loading customers..."

bq.cmd load `
    --location=europe-west4 `
    --source_format=CSV `
    --skip_leading_rows=1 `
    "${PROJECT_ID}:retail_dw.customers" `
    ".\data\cleaned\customers.csv"

if ($LASTEXITCODE -ne 0) {
    throw "Loading customers failed."
}

# ------------------------------------------------------------
# 4. STORES
# ------------------------------------------------------------

Write-Host ""
Write-Host "Loading stores..."

bq.cmd load `
    --location=europe-west4 `
    --source_format=CSV `
    --skip_leading_rows=1 `
    "${PROJECT_ID}:retail_dw.stores" `
    ".\data\cleaned\stores.csv"

if ($LASTEXITCODE -ne 0) {
    throw "Loading stores failed."
}

# ------------------------------------------------------------
# 5. EXCHANGE RATES
# ------------------------------------------------------------

Write-Host ""
Write-Host "Loading exchange rates..."

bq.cmd load `
    --location=europe-west4 `
    --source_format=CSV `
    --skip_leading_rows=1 `
    "${PROJECT_ID}:retail_dw.exchange_rates" `
    ".\data\cleaned\exchange_rates.csv"

if ($LASTEXITCODE -ne 0) {
    throw "Loading exchange rates failed."
}

Write-Host ""
Write-Host "All five BigQuery tables loaded successfully."