variable "bucket_name" {
  description = "Bootstrap artifact bucket; the grant is not project-wide."
  type        = string
}

variable "member" {
  description = "Dedicated lab service-account member (serviceAccount:EMAIL)."
  type        = string
}

variable "role" {
  description = "Read-only bootstrap object role."
  type        = string
  default     = "roles/storage.objectViewer"

  validation {
    condition     = var.role == "roles/storage.objectViewer"
    error_message = "Only roles/storage.objectViewer is allowed."
  }
}
