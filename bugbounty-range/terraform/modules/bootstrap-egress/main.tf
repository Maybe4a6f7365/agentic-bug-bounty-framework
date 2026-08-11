resource "google_compute_firewall" "bootstrap_egress" {
  name               = "bbr-${var.lab_id}-bootstrap-egress"
  network            = var.network_self_link
  direction          = "EGRESS"
  priority           = 1000
  target_tags        = var.target_tags
  destination_ranges = var.egress_destination_ranges

  allow {
    protocol = var.egress_protocol
    ports    = var.egress_ports
  }
}
