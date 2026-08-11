# Per-lab Terraform root — Phase 3 generic single-lab lifecycle.

# Backend-Konfiguration (Phase 4 Lücken-Fix Pre-Execute-Korrektur).
#
# Terraform initialisiert Backends VOR der Variablenauswertung. Daher
# darf der Backend-Block in main.tf KEINE Variablen-Referenzen
# enthalten. Statt dessen bleibt der Backend-Block leer (partial
# configuration) und der Bucket/Prefix wird zur Init-Zeit über
# `terraform init -backend-config=bucket=... -backend-config=prefix=...`
# vom CLI (bbr.py) gesetzt.
#
# Vorteil gegenüber dem früheren "Backend-Block mit Variablen"-Ansatz
# (der in 07c193e/d79fde8 versucht wurde):
#   - terraform-konform (Backend-Variablen werden nicht ausgewertet,
#     würden sonst als Literal "${var.gcp_project_id}" interpretiert)
#   - derselbe Mechanismus wie Phase 3 (kein Qualitätsverlust)
#   - CLI ist die einzige Source-of-Truth für Backend-Werte
#
# Beispiel (vom CLI):
#   terraform init \
#     -backend-config="bucket=bbr-state-your-lab-name-your-researcher-handle" \
#     -backend-config="prefix=labs/wordpress-smoke-001"

terraform {
  backend "gcs" {}
}

# Read foundation outputs from the foundation Terraform state.
# Foundation lifetime is independent; the lab never touches the
# foundation's resources directly.
data "terraform_remote_state" "foundation" {
  backend = "gcs"

  config = {
    bucket = "bbr-state-${var.gcp_project_id}"
    prefix = "foundation"
  }
}

locals {
  foundation_vpc_self_link    = data.terraform_remote_state.foundation.outputs.vpc_self_link
  foundation_wg_overlay_cidr  = data.terraform_remote_state.foundation.outputs.wireguard_overlay_cidr
  foundation_iap_source_range = data.terraform_remote_state.foundation.outputs.iap_ssh_source_range
}

module "lab_network" {
  source = "../modules/network"

  lab_id                     = var.lab_id
  cidr_block                 = var.lab_subnet_cidr
  vpc_self_link              = local.foundation_vpc_self_link
  region                     = var.gcp_region
  project_id                 = var.gcp_project_id
  runtime_service_account_id = var.lab_service_account_id
  operator_principal         = var.operator_principal
  labels                     = var.labels
}

module "lab_node" {
  source = "../modules/compute-node"

  node_id                              = var.lab_id
  machine_type                         = var.machine_type
  disk_type                            = var.disk_type
  disk_size_gb                         = var.disk_size_gb
  subnet_self_link                     = module.lab_network.subnet_self_link
  network_self_link                    = local.foundation_vpc_self_link
  runtime_service_account_email        = module.lab_network.runtime_service_account_email
  zone                                 = var.gcp_zone
  project_id                           = var.gcp_project_id
  base_image_self_link                 = var.base_image_self_link
  network_tags                         = [var.lab_id]
  wg_overlay_cidr                      = local.foundation_wg_overlay_cidr
  iap_source_range                     = local.foundation_iap_source_range
  labels                               = var.labels
  internal_ip                          = var.lab_internal_ip
  lab_id                               = var.lab_id
  pack_id                              = var.pack_id
  artifact_uri                         = var.artifact_uri
  artifact_sha256                      = var.artifact_sha256
  minisign_public_key                  = var.minisign_public_key
  supported_platform                   = var.supported_platform
  bucket_scoped_storage_reader_binding = true

  depends_on = [module.lab_network]
}

# WordPress Bootstrap Egress (Phase 4 Lücken-Fix Blocker B).
# Eine zusätzliche priority-1000 EGRESS-Firewall erlaubt während
# der Bootstrap-Phase TCP/443 zu den Google-API-Ranges für den
# GCS-Pull des Release-Artefakts. Die Phase-3-Deny-Firewall
# (priority 65000) bleibt aktiv und blockiert alles andere.
# Die Bootstrap-Firewall bleibt bis Lab-Destroy bestehen.
module "bootstrap_egress" {
  source = "../modules/bootstrap-egress"

  lab_id            = var.lab_id
  network_self_link = local.foundation_vpc_self_link
  target_tags       = [var.lab_id]
  depends_on        = [module.lab_node]
}

module "wordpress_bucket_binding" {
  source = "../modules/wordpress-bucket-binding"

  bucket_name = var.bootstrap_bucket_name
  member      = "serviceAccount:${module.lab_network.runtime_service_account_email}"
  role        = "roles/storage.objectViewer"

  depends_on = [module.lab_network]
}
