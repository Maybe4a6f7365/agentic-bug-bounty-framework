output "bootstrap_egress_id" {
  value = google_compute_firewall.bootstrap_egress.self_link
}

output "egress_destination_ranges" {
  value = var.egress_destination_ranges
}
