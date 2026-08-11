# Compute-node module outputs — Phase 3.

output "private_ip" {
  description = "Internal IPv4 of the lab node."
  value       = google_compute_instance.node.network_interface[0].network_ip
}

output "self_link" {
  description = "Self-link of the lab node."
  value       = google_compute_instance.node.self_link
}

output "instance_id" {
  description = "Numeric ID of the lab node."
  value       = google_compute_instance.node.id
}

output "name" {
  description = "Name of the lab node."
  value       = google_compute_instance.node.name
}