resource "google_project" "bbr" {
  project_id          = var.gcp_project_id
  name                = var.gcp_project_id
  billing_account     = var.billing_account_id
  org_id              = var.gcp_organization_id
  folder_id           = var.gcp_folder_id
  auto_create_network = false

  labels = {
    purpose    = "security-research-platform"
    platform   = "your-lab-name"
    operator   = var.platform_operator_label
    owner      = var.lab_owner_label
    data_class = "synthetic"
    expires_on = replace(var.credit_expiry_date, "-", "_")
  }

  lifecycle {
    # A foundation project must never be removed as a side effect of a
    # routine plan or destroy; teardown requires an explicit policy change.
    prevent_destroy = true
  }
}
