# Phase 2 foundation firewall.tf
#
# Two firewall rules; no others.
#
# 1. WireGuard ingress:
#    direction=INGRESS protocol=UDP port=51820
#    source_ranges = var.vpn_allowed_static_cidrs (operator CIDs)
#    target        = bbr-bastion tag
#
# 2. IAP SSH ingress:
#    direction=INGRESS protocol=TCP port=22
#    source_ranges = ["35.235.240.0/20"] (Google IAP range)
#    target        = bbr-bastion tag
#
# There MUST NOT be a rule for TCP/22 from 0.0.0.0/0 or from the
# operator CIDs. SSH is exclusively via IAP TCP Forwarding.

resource "google_compute_firewall" "bastion_wireguard" {
  project     = google_project.bbr.project_id
  name        = "bbr-bastion-wireguard"
  description = "WireGuard UDP ingress to the bastion. Source CIDs are operator-supplied."
  direction   = "INGRESS"
  network     = google_compute_network.platform.self_link
  priority    = 1000

  source_ranges = var.vpn_allowed_static_cidrs
  target_tags   = ["bbr-bastion"]

  allow {
    protocol = "udp"
    ports    = [tostring(local.bastion_listen_port)]
  }

  log_config {
    metadata = "INCLUDE_ALL_METADATA"
  }
}

resource "google_compute_firewall" "bastion_iap" {
  project     = google_project.bbr.project_id
  name        = "bbr-bastion-iap-ssh"
  description = "IAP TCP forwarding SSH ingress to the bastion. IAP CIDR only."
  direction   = "INGRESS"
  network     = google_compute_network.platform.self_link
  priority    = 1000

  source_ranges = ["35.235.240.0/20"]
  target_tags   = ["ssh-iap"]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  log_config {
    metadata = "INCLUDE_ALL_METADATA"
  }
}

# Single return route from VPC/lab networks to WireGuard clients
# via the bastion. This is the only custom route in Phase 2.
resource "google_compute_route" "wireguard_return" {
  project     = google_project.bbr.project_id
  name        = "bbr-wg-return"
  description = "Return route from VPC and lab networks to the WireGuard overlay via the bastion. Untagged: applies to every instance in the BBR VPC, including future lab VMs."
  network     = google_compute_network.platform.self_link
  dest_range  = local.wireguard_overlay_cidr
  next_hop_ip = local.bastion_internal_ip
  priority    = 100

  depends_on = [
    google_compute_instance.bastion,
  ]
}
