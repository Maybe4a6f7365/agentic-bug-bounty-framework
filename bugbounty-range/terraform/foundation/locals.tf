# Phase 1 locals.tf

# Locals that name the resources consistently. No resource
# definitions in this file.

locals {
  vpc_name               = "bbr-shared-vpc"
  platform_vpc_cidr      = "10.200.0.0/16"
  control_plane_cidr     = "10.200.0.0/24"
  per_lab_pool_start     = "10.200.1.0/24"
  per_lab_pool_end       = "10.200.254.0/24"
  wireguard_overlay_cidr = "10.254.0.0/24"
  reserved_subnets       = ["10.200.0.0/24"]
  bastion_subnet_cidr    = local.control_plane_cidr
  bastion_subnet_name    = "bbr-bastion-subnet"
  bastion_name           = "bbr-bastion"
  bastion_internal_ip    = "10.200.0.10"
  bastion_listen_port    = 51820
  state_bucket_name      = "bbr-state-${var.gcp_project_id}"

  foundation_apis = toset([
    "billingbudgets.googleapis.com",
    "compute.googleapis.com",
    "cloudbilling.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "storage.googleapis.com",
    "iap.googleapis.com",
  ])
}
