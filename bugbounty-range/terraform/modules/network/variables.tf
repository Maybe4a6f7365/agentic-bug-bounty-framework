# Per-lab network module variables — Phase 0.

variable "lab_id" {
  description = "Lowercase lab identifier."
  type        = string
}

variable "cidr_block" {
  description = "Per-lab /24 subnet CIDR allocated by the platform."
  type        = string
}

variable "vpc_self_link" {
  description = "Self-link of the shared access VPC. Sourced from the foundation."
  type        = string
}

variable "region" {
  description = "Region for the subnet. Default europe-west3."
  type        = string
  default     = "europe-west3"
}

variable "project_id" {
  description = "Dedicated GCP project ID."
  type        = string
}

variable "runtime_service_account_id" {
  description = "Account ID for the lab runtime service account."
  type        = string
}

variable "labels" {
  description = "Resource labels applied to every created resource."
  type        = map(string)
  default     = {}
}

variable "operator_principal" {
  description = "GCP principal that may use the lab runtime service account. Format: user:EMAIL or serviceAccount:EMAIL. Scoped to this lab SA only via google_service_account_iam_member."
  type        = string
}