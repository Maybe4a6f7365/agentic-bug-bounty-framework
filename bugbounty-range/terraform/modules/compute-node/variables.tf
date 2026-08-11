# Compute-node module variables — Phase 0.

variable "node_id" {
  description = "Lowercase node identifier."
  type        = string
}

variable "machine_type" {
  description = "GCE machine type."
  type        = string
}

variable "disk_type" {
  description = "GCE disk type."
  type        = string
  default     = "pd-standard"
}

variable "disk_size_gb" {
  description = "Boot disk size in GB."
  type        = number
  default     = 20
}

variable "subnet_self_link" {
  description = "Self-link of the per-lab subnet."
  type        = string
}

variable "base_image_family" {
  description = "GCE image family. Phase 3 smoke packs MUST use base_image_self_link instead; family is kept for compatibility only."
  type        = string
  default     = null
}

variable "base_image_self_link" {
  description = "GCE image self-link (projects/.../global/images/...). Pinned at plan time. Used by Phase 3 smoke packs."
  type        = string
  default     = null

  validation {
    condition     = var.base_image_self_link == null || can(regex("^projects/[^/]+/global/images/[^/]+$", var.base_image_self_link))
    error_message = "base_image_self_link, when set, must look like projects/<project>/global/images/<image>."
  }
}

variable "runtime_service_account_email" {
  description = "Email of the lab runtime service account."
  type        = string
}

variable "runtime_service_account_scopes" {
  description = <<-EOT
    OAuth scopes attached to the runtime service account on the lab VM.
    Phase 4A: must be the narrowest scope that still allows the lab to
    pull the bootstrap artifact from the GCS bootstrap bucket — that is
    https://www.googleapis.com/auth/devstorage.read_only.
    Do NOT use cloud-platform (too broad); do NOT omit scopes (causes
    403 on GCS read).
  EOT
  type        = list(string)
  default     = ["https://www.googleapis.com/auth/devstorage.read_only"]
}

variable "network_tags" {
  description = "Network tags applied to the VM for firewall targeting."
  type        = list(string)
  default     = []
}

variable "zone" {
  description = "Zone for the VM."
  type        = string
  default     = "europe-west3-a"
}

variable "project_id" {
  description = "Dedicated GCP project ID."
  type        = string
}

variable "labels" {
  description = "Resource labels."
  type        = map(string)
  default     = {}
}

variable "network_self_link" {
  description = "Self-link of the shared VPC network. Required for the firewall resources in this module."
  type        = string
}

variable "wg_overlay_cidr" {
  description = "CIDR of the BBR WireGuard overlay (e.g. 10.254.0.0/24). Used as source range for the WG-admin firewall."
  type        = string
  default     = "10.254.0.0/24"
}

variable "iap_source_range" {
  description = "Source range for IAP tunnel SSH. Must match the GCP IAP TCP forwarding range."
  type        = string
  default     = "35.235.240.0/20"
}
variable "internal_ip" {
  description = "Internal IPv4 assigned to the lab VM inside the per-lab subnet. Phase 3 smoke plan: 10.200.1.10."
  type        = string

  validation {
    condition     = can(regex("^10\\.[0-9]+\\.[0-9]+\\.[0-9]+$", var.internal_ip))
    error_message = "internal_ip must be an IPv4 address in the 10.0.0.0/8 range."
  }
}

variable "lab_id" {
  description = "Lab identifier. Used by the startup template to write the readiness marker."
  type        = string
}

variable "pack_id" {
  description = "Pack identifier. Used by the startup template to write the readiness marker."
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

variable "bucket_scoped_storage_reader_binding" {
  description = "Require a bucket-scoped roles/storage.objectViewer binding for bootstrap artifacts."
  type        = bool
  default     = true
}
