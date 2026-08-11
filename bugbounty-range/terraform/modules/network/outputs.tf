# Per-lab network module outputs — Phase 3.

output "subnet_self_link" {
  description = "Self-link of the per-lab subnet."
  value       = google_compute_subnetwork.lab.self_link
}

output "subnet_cidr" {
  description = "CIDR of the per-lab subnet."
  value       = google_compute_subnetwork.lab.ip_cidr_range
}

output "runtime_service_account_email" {
  description = "Email of the per-lab runtime service account."
  value       = google_service_account.lab_runtime.email
}

output "runtime_service_account_name" {
  description = "Resource name of the per-lab runtime service account."
  value       = google_service_account.lab_runtime.name
}