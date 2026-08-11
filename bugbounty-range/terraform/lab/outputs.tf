# Per-lab Terraform root outputs — Phase 3.

output "lab_id" {
  description = "Lab identifier."
  value       = var.lab_id
}

output "lab_subnet_cidr" {
  description = "Allocated per-lab subnet CIDR."
  value       = module.lab_network.subnet_cidr
}

output "lab_subnet_self_link" {
  description = "Self-link of the per-lab subnet."
  value       = module.lab_network.subnet_self_link
}

output "node_name" {
  description = "Name of the lab VM."
  value       = module.lab_node.name
}

output "node_internal_ip" {
  description = "Internal IPv4 of the lab VM."
  value       = module.lab_node.private_ip
}

output "node_self_link" {
  description = "Self-link of the lab VM."
  value       = module.lab_node.self_link
}

output "node_service_account_email" {
  description = "Email of the lab runtime service account."
  value       = module.lab_network.runtime_service_account_email
}

output "ttl_max_lifetime_seconds" {
  description = "TTL max lifetime in seconds."
  value       = var.ttl_max_lifetime_seconds
}

output "ttl_idle_timeout_seconds" {
  description = "TTL idle timeout in seconds."
  value       = var.ttl_idle_timeout_seconds
}

output "per_cycle_eur_limit" {
  description = "Per-cycle cost guard in EUR."
  value       = var.per_cycle_eur_limit
}