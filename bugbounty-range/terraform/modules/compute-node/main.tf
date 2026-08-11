# Compute-node module — Phase 3 generic single-lab lifecycle.
#
# Creates the lab VM and the three firewall rules that bound
# its traffic: WireGuard admin access from the BBR overlay,
# IAP-tunneled SSH from Google's IAP range, and a default-deny
# egress rule that prevents any internet-bound traffic. The VM
# has no external IPv4 address and no access_config block.
# The VM runs an egress-free startup script (rendered from
# templates/raw-vm-startup.sh.tftpl) that writes a deterministic
# readiness marker at /var/lib/bbr/ready on first boot. The
# startup script is part of the Terraform plan (no separate
# post-create SSH write).

resource "google_compute_instance" "node" {
  project        = var.project_id
  name           = var.node_id
  zone           = var.zone
  machine_type   = var.machine_type
  can_ip_forward = false

  tags = var.network_tags

  boot_disk {
    initialize_params {
      image = var.base_image_self_link
      size  = var.disk_size_gb
      type  = var.disk_type
    }
  }

  network_interface {
    subnetwork = var.subnet_self_link
    network_ip = var.internal_ip
    # Explicitly NO access_config block: no external IPv4.
  }

  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }

  metadata = {
    enable-oslogin         = "TRUE"
    block-project-ssh-keys = "TRUE"
  }

  metadata_startup_script = templatefile(
    "${path.module}/templates/raw-vm-startup.sh.tftpl",
    {
      lab_id              = var.lab_id
      pack_id             = var.pack_id
      node_id             = var.node_id
      internal_ip         = var.internal_ip
      artifact_uri        = var.artifact_uri
      artifact_sha256     = var.artifact_sha256
      minisign_public_key = var.minisign_public_key
      supported_platform  = var.supported_platform
    }
  )

  service_account {
    email  = var.runtime_service_account_email
    scopes = var.runtime_service_account_scopes
  }

  labels = var.labels

  lifecycle {
    prevent_destroy = false
  }
}

# Firewall 1 — WireGuard admin access from the BBR overlay.
resource "google_compute_firewall" "wireguard_admin" {
  project = var.project_id
  name    = "bbr-lab-${var.node_id}-wg-admin"
  network = var.network_self_link

  direction = "INGRESS"
  priority  = 1000

  source_ranges = [var.wg_overlay_cidr]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
  allow {
    protocol = "icmp"
  }

  target_tags = var.network_tags

  description = "WireGuard-overlay admin SSH to lab ${var.node_id} from ${var.wg_overlay_cidr} only."
}

# Firewall 2 — IAP-tunneled SSH from the Google IAP range.
resource "google_compute_firewall" "iap_ssh" {
  project = var.project_id
  name    = "bbr-lab-${var.node_id}-iap-ssh"
  network = var.network_self_link

  direction = "INGRESS"
  priority  = 1000

  source_ranges = [var.iap_source_range]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  target_tags = var.network_tags

  description = "IAP-tunneled SSH to lab ${var.node_id} from ${var.iap_source_range} only."
}

# Firewall 3 — default-deny egress (priority 65000, higher than
# implied allow-egress at default priority 65534).
resource "google_compute_firewall" "egress_deny" {
  project = var.project_id
  name    = "bbr-lab-${var.node_id}-egress-deny"
  network = var.network_self_link

  direction = "EGRESS"
  priority  = 65000

  destination_ranges = ["0.0.0.0/0"]

  deny {
    protocol = "all"
  }

  target_tags = var.network_tags

  description = "Default-deny egress for lab ${var.node_id}. Higher priority than the implied allow-egress."
}
