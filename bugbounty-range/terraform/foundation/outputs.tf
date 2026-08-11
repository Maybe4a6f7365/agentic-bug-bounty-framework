output "project_id" {
  description = "Dedicated BugBountyRange GCP project ID."
  value       = google_project.bbr.project_id
  sensitive   = true
}

output "project_number" {
  description = "Dedicated BugBountyRange GCP project number."
  value       = google_project.bbr.number
  sensitive   = true
}

output "state_bucket_name" {
  description = "Terraform state bucket name."
  value       = google_storage_bucket.state.name
  sensitive   = true
}

output "state_bucket_self_link" {
  description = "Self-link of the hardened Terraform state bucket."
  value       = google_storage_bucket.state.self_link
  sensitive   = true
}

output "active_lab_limit" {
  description = "Configured active-lab limit."
  value       = var.active_lab_limit
}

output "budget_eur_equivalent" {
  description = "Monthly GCP budget-alert amount in EUR; not a hard cap."
  value       = var.budget_eur_equivalent
}

output "platform_vpc_cidr" {
  description = "Reserved platform VPC CIDR for later phases."
  value       = local.platform_vpc_cidr
}

output "control_plane_cidr" {
  description = "Reserved control-plane subnet CIDR for later phases."
  value       = local.control_plane_cidr
}

output "per_lab_pool_start" {
  description = "First /24 in the per-lab pool."
  value       = local.per_lab_pool_start
}

output "per_lab_pool_end" {
  description = "Last /24 in the per-lab pool."
  value       = local.per_lab_pool_end
}

output "wireguard_overlay_cidr" {
  description = "Reserved WireGuard overlay CIDR for later phases."
  value       = local.wireguard_overlay_cidr
}

output "vpc_self_link" {
  description = "Self-link of the platform VPC."
  value       = google_compute_network.platform.self_link
}

output "control_plane_subnet_self_link" {
  description = "Self-link of the control-plane subnet."
  value       = google_compute_subnetwork.control_plane.self_link
}

output "bastion_name" {
  description = "Name of the bastion VM."
  value       = google_compute_instance.bastion.name
}

output "bastion_internal_ip" {
  description = "Internal IPv4 of the bastion VM."
  value       = google_compute_instance.bastion.network_interface[0].network_ip
}

output "bastion_external_ip" {
  description = "Reserved regional external IPv4 attached to the bastion VM."
  value       = google_compute_address.bastion.address
}

output "bastion_service_account_email" {
  description = "Email of the bastion service account."
  value       = google_service_account.bastion.email
}

output "wireguard_listen_port" {
  description = "WireGuard UDP listen port on the bastion."
  value       = local.bastion_listen_port
}

output "iap_ssh_source_range" {
  description = "Google IAP TCP forwarding source range allowed for SSH to the bastion."
  value       = "35.235.240.0/20"
}

output "wireguard_allowed_source_cidrs" {
  description = "Source CIDRs allowed to reach the bastion WireGuard endpoint."
  value       = var.vpn_allowed_static_cidrs
  sensitive   = true
}

output "enabled_apis" {
  description = "Foundation APIs enabled for the platform project."
  value       = sort([for service in google_project_service.foundation : service.service])
}

output "budget_display_name" {
  description = "Display name of the platform billing alert budget."
  value       = google_billing_budget.platform.display_name
}
