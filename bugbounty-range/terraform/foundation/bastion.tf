# Phase 2 foundation bastion.tf
#
# Defines the bastion — the only VM with a public IPv4 on the
# platform. The bastion hosts:
#   - Identity-aware TCP Forwarding (IAP SSH) endpoint
#   - WireGuard server (UDP 51820)
#
# SSH access policy:
#   - IAP TCP Forwarding only (no public TCP/22)
#   - OS Login with operator principal
#   - block-project-ssh-keys = "TRUE" — no SSH keys in metadata
#
# WireGuard server private key:
#   - generated locally on first boot of the bastion
#   - mode 0600, owner root:root
#   - never enters Terraform, state, metadata, or logs
#
# Operator public key flow (corrected in v3):
#   - The operator workstation reads its public key file.
#   - The plan wrapper sets TF_VAR_bbr_operator_wg_public_key
#     from that file (public material only).
#   - Terraform embeds the public key directly into the bastion
#     bootstrap script via templatefile().
#   - The VM does not read any operator file or environment
#     variable at runtime; the key is provided by Terraform
#     via the bootstrap template only.

resource "google_service_account" "bastion" {
  project      = google_project.bbr.project_id
  account_id   = "bbr-bastion-sa"
  display_name = "BugBountyRange Bastion Service Account"
  description  = "Dedicated service account for the bbr-bastion instance. No project-wide roles; the bastion does not call GCP APIs."
}

# Reserved regional external IPv4. Exactly one is allocated in
# Phase 2; per-lab resources never get public IPs.
resource "google_compute_address" "bastion" {
  project      = google_project.bbr.project_id
  name         = "bbr-bastion-eip"
  region       = var.gcp_region
  description  = "BugBountyRange bastion public IPv4 (UDP 51820 only)"
  address_type = "EXTERNAL"
  network_tier = "STANDARD"

  depends_on = [
    google_project_service.foundation["compute.googleapis.com"],
  ]
}

# Locals for the bastion image and startup script so the image
# is pinned at plan time and never refreshed at apply time. The
# image is referenced by a fully resolved Self-Link, not a
# family, so the bastion cannot drift to a newer image.
locals {
  bastion_image_self_link = "projects/debian-cloud/global/images/debian-12-bookworm-v20260721"
}
resource "google_compute_instance" "bastion" {
  project        = google_project.bbr.project_id
  name           = local.bastion_name
  zone           = var.gcp_zone
  machine_type   = "e2-micro"
  can_ip_forward = true

  tags = ["bbr-bastion", "ssh-iap", "wireguard"]

  # OS Login + block-project-ssh-keys — no SSH keys in metadata.
  metadata = {
    enable-oslogin         = "TRUE"
    block-project-ssh-keys = "TRUE"
  }

  boot_disk {
    initialize_params {
      image = local.bastion_image_self_link
      size  = 10
      type  = "pd-standard"
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.control_plane.self_link

    network_ip = local.bastion_internal_ip

    access_config {
      nat_ip       = google_compute_address.bastion.address
      network_tier = "STANDARD"
    }
  }

  service_account {
    email  = google_service_account.bastion.email
    scopes = ["cloud-platform"]
  }

  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }

  labels = {
    operator = var.platform_operator_label
    owner    = var.lab_owner_label
    purpose  = "security-research-platform"
    role     = "bastion"
  }

  metadata_startup_script = templatefile(
    "${path.module}/templates/bastion-startup.sh.tftpl",
    {
      bastion_listen_port        = local.bastion_listen_port
      wireguard_overlay_cidr     = local.wireguard_overlay_cidr
      wireguard_server_address   = local.wireguard_server_address
      wireguard_operator_address = local.wireguard_operator_address
      bastion_internal_ip        = local.bastion_internal_ip
      operator_public_key        = var.bbr_operator_wg_public_key
    }
  )
}

# ─────────────────────────────────────────────────────────────────────
# IAM bindings for the bastion.
#
# Read-only pre-check (2026-07-26):
#   Operator principal user:your-contact@example.com already has
#   roles/owner at project level. That includes osAdminLogin and
#   IAP tunnel access via inheritance, but the explicit minimal
#   bindings below are kept so that Phase-2 access works even
#   if the project-level owner role is revoked later. None of
#   them add Owner, Editor, or Compute Admin roles.
#
# roles/iam.serviceAccountUser is bound to the operator so
#   gcloud compute ssh / IAP-tunnel-based sessions can run as
#   the bastion service account if explicitly required.
# ─────────────────────────────────────────────────────────────────────

resource "google_project_iam_member" "operator_iap_tunnel" {
  project = google_project.bbr.project_id
  role    = "roles/iap.tunnelResourceAccessor"
  member  = var.bbr_operator_principal
}

resource "google_project_iam_member" "operator_os_login" {
  project = google_project.bbr.project_id
  role    = "roles/compute.osAdminLogin"
  member  = var.bbr_operator_principal
}

resource "google_service_account_iam_member" "operator_sa_user" {
  service_account_id = google_service_account.bastion.name
  role               = "roles/iam.serviceAccountUser"
  member             = var.bbr_operator_principal
}
