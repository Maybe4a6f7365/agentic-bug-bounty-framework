# Per-lab network module — Phase 3 generic single-lab lifecycle.
#
# Creates the per-lab subnet, the lab runtime service account,
# and the scoped IAM binding that allows the operator to use the
# service account when SSH-ing into the lab node. No project-wide
# roles, no service-account keys, no extra firewall rules (those
# live in the compute-node module and the per-lab root).

resource "google_compute_subnetwork" "lab" {
  name          = "bbr-lab-${var.lab_id}"
  ip_cidr_range = var.cidr_block
  region        = var.region
  network       = var.vpc_self_link
  project       = var.project_id

  private_ip_google_access = true

  # The lab subnet is ephemeral and is destroyed by the Phase 3
  # destroy gate (APPROVE PHASE 3 DESTROY EXECUTE). It does NOT
  # carry a prevent_destroy guard because that would prevent
  # the explicit, audited destroy of the lab lifetime.
}

resource "google_service_account" "lab_runtime" {
  project      = var.project_id
  account_id   = var.runtime_service_account_id
  display_name = "BugBountyRange lab runtime (${var.lab_id})"
  description  = "Dedicated service account for the ${var.lab_id} lab runtime. No project-wide roles. The lab node does not call GCP APIs."
}

resource "google_service_account_iam_member" "operator_sa_user" {
  service_account_id = google_service_account.lab_runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = var.operator_principal
}