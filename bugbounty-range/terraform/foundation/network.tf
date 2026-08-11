# Phase 2 foundation network.tf
#
# Defines the Shared Access Plane:
#   - Custom-mode VPC: bbr-shared-vpc
#   - Regional routing mode
#   - Control-plane subnet: bbr-bastion-subnet (10.200.0.0/24)
#
# Phase 2 explicitly does NOT create:
#   - Per-lab subnets (handled dynamically by `bbr create <pack>`)
#   - VPC peering
#   - Cloud NAT
#   - Snapshots
#   - Product- or pack-specific resources
#
# Range layout (declared, not allocated by Phase 2):
#   10.200.0.0/16     platform VPC allocation space
#   10.200.0.0/24     control-plane subnet (created here)
#   10.200.1.0/24 ..
#   10.200.254.0/24   per-lab pool (not allocated by Phase 2)
#   10.254.0.0/24     WireGuard overlay (route only, no subnet)

locals {
  vpc_name                   = "bbr-shared-vpc"
  platform_vpc_cidr          = "10.200.0.0/16"
  control_plane_cidr         = "10.200.0.0/24"
  per_lab_pool_start         = "10.200.1.0/24"
  per_lab_pool_end           = "10.200.254.0/24"
  wireguard_overlay_cidr     = "10.254.0.0/24"
  wireguard_server_address   = "10.254.0.1/24"
  wireguard_operator_address = "10.254.0.2/32"
  reserved_subnets           = ["10.200.0.0/24"]
  bastion_subnet_cidr        = local.control_plane_cidr
  bastion_subnet_name        = "bbr-bastion-subnet"
  bastion_name               = "bbr-bastion"
  bastion_internal_ip        = "10.200.0.10"
  bastion_listen_port        = 51820
  state_bucket_name          = "bbr-state-${var.gcp_project_id}"
}

# ─────────────────────────────────────────────────────────────────────
# Custom-mode VPC with regional routing
# ─────────────────────────────────────────────────────────────────────

resource "google_compute_network" "platform" {
  project                         = google_project.bbr.project_id
  name                            = local.vpc_name
  auto_create_subnetworks         = false
  routing_mode                    = "REGIONAL"
  description                     = "BugBountyRange shared access plane (custom mode, regional routing)"
  delete_default_routes_on_create = false
  mtu                             = 1460

  depends_on = [
    google_project_service.foundation["compute.googleapis.com"],
  ]
}

# Control-plane subnet (bastion). Private Google Access enabled so
# the bastion can reach Google APIs without an external IP path
# beyond the WireGuard endpoint. Only one subnet is created in
# Phase 2; per-lab subnets are added dynamically per `bbr create`.
resource "google_compute_subnetwork" "control_plane" {
  project       = google_project.bbr.project_id
  name          = local.bastion_subnet_name
  ip_cidr_range = local.bastion_subnet_cidr
  region        = var.gcp_region
  network       = google_compute_network.platform.id
  purpose       = "PRIVATE"

  log_config {
    aggregation_interval = "INTERVAL_5_SEC"
    flow_sampling        = 0.5
    metadata             = "INCLUDE_ALL_METADATA"
  }

  private_ip_google_access = true
}
