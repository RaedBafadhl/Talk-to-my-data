terraform {
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

# 1. Artifact Registry for Docker Images
resource "google_artifact_registry_repository" "docker_repo" {
  location      = var.region
  repository_id = var.artifact_repo_name
  description   = "Docker repository for Talk-to-my-Data application"
  format        = "DOCKER"
}

# 2. Backend Cloud Run Service
resource "google_cloud_run_v2_service" "backend" {
  name     = "talk-to-my-data-backend"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = var.backend_runtime_service_account
    scaling {
      min_instance_count = 1
      max_instance_count = 2
    }
    containers {
      image = "us-docker.pkg.dev/cloudrun/container/hello" # Placeholder image, updated by GitHub Actions
      ports {
        container_port = 8080
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "GCP_REGION"
        value = var.region
      }
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].containers[0].image,
      template[0].containers[0].env,
      client,
      client_version,
    ]
  }
}

# Make Backend Public (or restrict to Frontend only, but for this stage we make it public)
data "google_iam_policy" "noauth_backend" {
  binding {
    role    = "roles/run.invoker"
    members = ["allUsers"]
  }
}

resource "google_cloud_run_service_iam_policy" "backend_noauth" {
  location    = google_cloud_run_v2_service.backend.location
  project     = google_cloud_run_v2_service.backend.project
  service     = google_cloud_run_v2_service.backend.name
  policy_data = data.google_iam_policy.noauth_backend.policy_data
}

# 3. Frontend Cloud Run Service
resource "google_cloud_run_v2_service" "frontend" {
  name     = "talk-to-my-data-frontend"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account  = var.backend_runtime_service_account
    session_affinity = true
    scaling {
      min_instance_count = 1
      max_instance_count = 2
    }
    containers {
      image = "us-docker.pkg.dev/cloudrun/container/hello" # Placeholder image
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
    ignore_changes = [
      template[0].containers[0].image,
      client,
      client_version,
    ]
  }
}

# Make Frontend Public
data "google_iam_policy" "noauth_frontend" {
  binding {
    role    = "roles/run.invoker"
    members = ["allUsers"]
  }
}

resource "google_cloud_run_service_iam_policy" "frontend_noauth" {
  location    = google_cloud_run_v2_service.frontend.location
  project     = google_cloud_run_v2_service.frontend.project
  service     = google_cloud_run_v2_service.frontend.name
  policy_data = data.google_iam_policy.noauth_frontend.policy_data
}
