resource "google_storage_bucket" "state" {
  name                        = local.state_bucket_name
  project                     = google_project.bbr.project_id
  location                    = "EU"
  force_destroy               = false
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      num_newer_versions = 5
    }
    action {
      type = "Delete"
    }
  }

  labels = {
    platform = "your-lab-name"
    operator = var.platform_operator_label
    owner    = var.lab_owner_label
  }

  depends_on = [
    google_project_service.foundation["storage.googleapis.com"],
  ]
}

# Acceptance verification must confirm uniform bucket-level access,
# enforced public-access prevention, versioning, and the lifecycle rule.
