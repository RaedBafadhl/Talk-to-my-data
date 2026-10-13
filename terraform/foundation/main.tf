terraform {
  required_version = ">= 1.5"
  backend "gcs" {}
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

variable "environment" {
  type = string
  validation {
    condition     = contains(["raed", "personal"], var.environment)
    error_message = "Choose raed or personal."
  }
}

locals {
  config     = jsondecode(file("${path.module}/../environments/${var.environment}.tfvars.json"))
  federation = local.config.auth_mode == "federation"
  apis = toset([
    "run.googleapis.com", "artifactregistry.googleapis.com", "cloudbuild.googleapis.com",
    "bigquery.googleapis.com", "aiplatform.googleapis.com", "iam.googleapis.com",
    "iamcredentials.googleapis.com", "sts.googleapis.com", "storage.googleapis.com"
  ])
}

provider "google" {
  project = local.config.project_id
  region  = local.config.region
}

data "google_project" "application" {
  project_id = local.config.project_id
}

resource "google_project_service" "api" {
  for_each           = local.apis
  project            = local.config.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_storage_bucket" "state" {
  project                     = local.config.state_project_id
  name                        = local.config.state_bucket
  location                    = local.config.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  versioning {
    enabled = true
  }
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_storage_bucket_iam_member" "state_writer" {
  bucket = google_storage_bucket.state.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${local.config.deployer_service_account}"
}

resource "google_service_account" "runtime" {
  account_id   = "talk-to-my-data-backend"
  display_name = "talk-to-my-data-backend"
  depends_on   = [google_project_service.api]
  lifecycle {
    prevent_destroy = true
    ignore_changes  = [description]
  }
}

resource "google_service_account" "deployer" {
  account_id   = "github-deployer"
  display_name = "GitHub deployment for Talk-to-my-data"
  depends_on   = [google_project_service.api]
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_project_iam_member" "runtime" {
  for_each = toset(["roles/bigquery.jobUser", "roles/aiplatform.user"])
  project  = local.config.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "deployer_api" {
  project = local.config.project_id
  role    = "roles/serviceusage.serviceUsageConsumer"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_service_account_iam_member" "act_as" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_artifact_registry_repository_iam_member" "image_writer" {
  project    = local.config.project_id
  location   = local.config.region
  repository = local.config.artifact_repo_name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_cloud_run_v2_service_iam_member" "deployer" {
  for_each = toset(["backend", "frontend"])
  project  = local.config.project_id
  location = local.config.region
  name     = "talk-to-my-data-${each.value}"
  role     = "roles/run.developer"
  member   = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_iam_workload_identity_pool" "github" {
  count                     = local.federation ? 1 : 0
  workload_identity_pool_id = "github"
  display_name              = "GitHub Actions"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  count                              = local.federation ? 1 : 0
  workload_identity_pool_id          = google_iam_workload_identity_pool.github[0].workload_identity_pool_id
  workload_identity_pool_provider_id = "talk-to-my-data"
  attribute_mapping = {
    "google.subject"                = "assertion.sub"
    "attribute.repository_id"       = "assertion.repository_id"
    "attribute.repository_owner_id" = "assertion.repository_owner_id"
    "attribute.ref"                 = "assertion.ref"
  }
  attribute_condition = "assertion.repository_id == '1351354609' && assertion.repository_owner_id == '259883354' && assertion.ref == 'refs/heads/main'"
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "federation" {
  count              = local.federation ? 1 : 0
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/projects/${data.google_project.application.number}/locations/global/workloadIdentityPools/github/attribute.repository_id/1351354609"
  depends_on         = [google_iam_workload_identity_pool_provider.github]
}

resource "google_bigquery_dataset" "retail" {
  dataset_id                 = "retail_dw"
  location                   = local.config.region
  description                = "Talk-to-my-Data retail data warehouse"
  delete_contents_on_destroy = false
  depends_on                 = [google_project_service.api]
  lifecycle {
    prevent_destroy = true
    ignore_changes  = [access]
  }
}

resource "google_bigquery_table_iam_member" "runtime_reader" {
  for_each   = google_bigquery_table.retail
  project    = local.config.project_id
  dataset_id = google_bigquery_dataset.retail.dataset_id
  table_id   = each.value.table_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_bigquery_table" "retail" {
  for_each            = toset(["sales", "products", "customers", "stores", "exchange_rates"])
  dataset_id          = google_bigquery_dataset.retail.dataset_id
  table_id            = each.value
  schema              = file("${path.module}/../schemas/${each.value}.json")
  deletion_protection = true
  clustering          = each.value == "sales" ? ["product_key", "customer_key", "store_key"] : each.value == "exchange_rates" ? ["currency"] : null
  dynamic "time_partitioning" {
    for_each = contains(["sales", "exchange_rates"], each.value) ? [each.value] : []
    content {
      type  = "DAY"
      field = time_partitioning.value == "sales" ? "order_date" : "date"
    }
  }
  lifecycle {
    prevent_destroy = true
  }
}
