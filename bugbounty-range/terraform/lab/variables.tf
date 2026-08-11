# Per-lab Terraform root variables — Phase 3.

variable "gcp_project_id" {
  description = "Dedicated GCP project ID (your-lab-name-<owner>)."
  type        = string
}

variable "gcp_region" {
  description = "GCP region for lab resources."
  type        = string
  default     = "europe-west3"
}

variable "gcp_zone" {
  description = "GCP zone for the lab VM."
  type        = string
  default     = "europe-west3-a"
}

variable "lab_id" {
  description = "Lowercase lab identifier. For Phase 3 smoke this is smoke-vm-001."
  type        = string
}

variable "lab_subnet_cidr" {
  description = "Per-lab /24 subnet CIDR allocated by the platform network allocator."
  type        = string
}

variable "lab_internal_ip" {
  description = "Internal IP inside the per-lab subnet assigned to the lab VM. Phase 3 smoke: 10.200.1.10."
  type        = string
  default     = null
}

variable "lab_service_account_id" {
  description = "Service-account account_id for the lab runtime."
  type        = string
  default     = "bbr-lab-wordpress-smoke-001"
}

variable "machine_type" {
  description = "GCE machine type for the lab VM."
  type        = string
  default     = "e2-micro"
}

variable "disk_size_gb" {
  description = "Boot disk size in GB."
  type        = number
  default     = 10
}

variable "disk_type" {
  description = "Boot disk type."
  type        = string
  default     = "pd-standard"
}

variable "base_image_self_link" {
  description = "Pinned GCE image self-link for the lab VM boot disk."
  type        = string
}

variable "operator_principal" {
  description = "GCP principal that may use the lab runtime SA. Format: user:EMAIL."
  type        = string
}

variable "ttl_max_lifetime_seconds" {
  description = "Maximum lab lifetime in seconds. Default 28800 (8h)."
  type        = number
  default     = 28800
}

variable "ttl_idle_timeout_seconds" {
  description = "Idle timeout in seconds. Default 1800 (30m)."
  type        = number
  default     = 1800
}

variable "per_cycle_eur_limit" {
  description = "Cost guard for one create-destroy cycle, in EUR. Enforced by the CLI before plan."
  type        = number
  default     = 1.00
}

variable "labels" {
  description = "Resource labels applied to every created resource."
  type        = map(string)
  default     = {}
}
variable "pack_id" {
  description = "Pack identifier. Phase 3 smoke plan: smoke-vm."
  type        = string
}

variable "artifact_uri" {
  type    = string
  default = ""
}

variable "artifact_sha256" {
  type    = string
  default = ""
}

variable "minisign_public_key" {
  type    = string
  default = ""
}

variable "supported_platform" {
  type    = string
  default = ""
}

variable "bootstrap_bucket_name" {
  description = "Bucket containing the signed bootstrap release."
  type        = string
  default     = "bbr-bootstrap-your-lab-name-your-researcher-handle"
}
