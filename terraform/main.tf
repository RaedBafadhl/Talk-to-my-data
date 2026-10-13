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

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_artifact_registry_repository" "docker_repo" {
  location      = var.region
  repository_id = var.artifact_repo_name
  description   = "Docker repository for Talk-to-my-Data application"
  format        = "DOCKER"
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_cloud_run_v2_service" "backend" {
  name     = "talk-to-my-data-backend"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"
  template {
    service_account = var.backend_runtime_service_account
    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }
    containers {
      image = var.backend_image
      ports {
        container_port = 8080
      }
      dynamic "env" {
        for_each = [
          { name = "VERTEX_AI_PROJECT_ID", value = var.project_id },
          { name = "BIGQUERY_PROJECT_ID", value = var.project_id },
          { name = "GCP_PROJECT_ID", value = var.project_id },
          { name = "GCP_REGION", value = var.region },
        ]
        content {
          name  = env.value.name
          value = env.value.value
        }
      }
    }
  }
  lifecycle {
    prevent_destroy = true
    ignore_changes  = [client, client_version]
    precondition {
      condition     = var.min_instances >= 0 && var.min_instances <= var.max_instances && floor(var.min_instances) == var.min_instances
      error_message = "min_instances must be a nonnegative integer no greater than max_instances."
    }
  }
}

resource "google_cloud_run_v2_service" "frontend" {
  name     = "talk-to-my-data-frontend"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"
  template {
    service_account  = var.backend_runtime_service_account
    session_affinity = true
    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }
    containers {
      image = var.frontend_image
      ports {
        container_port = 8501
      }
      env {
        name  = "BACKEND_API_URL"
        value = "${google_cloud_run_v2_service.backend.uri}/ask"
      }
    }
  }
  lifecycle {
    prevent_destroy = true
    ignore_changes  = [client, client_version]
  }
}

resource "google_cloud_run_v2_service_iam_member" "public" {
  for_each = {
    backend  = google_cloud_run_v2_service.backend.name
    frontend = google_cloud_run_v2_service.frontend.name
  }
  project  = var.project_id
  location = var.region
  name     = each.value
  role     = "roles/run.invoker"
  member   = "allUsers"
}

output "backend_url" {
  value = google_cloud_run_v2_service.backend.uri
}
output "frontend_url" {
  value = google_cloud_run_v2_service.frontend.uri
}
