variable "project_id" {
  type        = string
  description = "Google Cloud Project ID"
  default     = "tgs-talk-to-data"
}

variable "region" {
  type        = string
  description = "Google Cloud Region"
  default     = "europe-west4" # Adjust if necessary
}

variable "artifact_repo_name" {
  type        = string
  description = "Name for the Artifact Registry repository"
  default     = "talk-to-my-data-repo"
}

variable "backend_runtime_service_account" {
  type        = string
  description = "Runtime service account for Cloud Run backend"
  default     = "talk-to-my-data-backend@tgs-talk-to-data.iam.gserviceaccount.com"
}

variable "deployer_service_account" {
  type        = string
  description = "Deployer service account used for CI/CD"
  default     = "github-deployer@tgs-talk-to-data.iam.gserviceaccount.com"
}
