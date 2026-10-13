variable "project_id" {
  type = string
}
variable "region" {
  type = string
}
variable "artifact_repo_name" {
  type = string
}
variable "backend_runtime_service_account" {
  type = string
}
variable "deployer_service_account" {
  type = string
}
variable "state_bucket" {
  type = string
}
variable "state_project_id" {
  type = string
}
variable "auth_mode" {
  type = string
  validation {
    condition     = contains(["credentials", "federation"], var.auth_mode)
    error_message = "auth_mode must be credentials or federation."
  }
}
variable "workload_identity_provider" {
  type    = string
  default = ""
}
variable "min_instances" {
  type    = number
  default = 1
}
variable "max_instances" {
  type    = number
  default = 2
  validation {
    condition     = var.max_instances >= 1 && floor(var.max_instances) == var.max_instances
    error_message = "max_instances must be a positive integer."
  }
}
variable "backend_image" {
  type = string
}
variable "frontend_image" {
  type = string
}
