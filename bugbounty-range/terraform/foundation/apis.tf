# Phase 1 enables the complete foundation API set declared in
# locals.tf. Later phases therefore do not need a second API-enable pass.

resource "google_project_service" "foundation" {
  for_each = local.foundation_apis

  project            = google_project.bbr.project_id
  service            = each.value
  disable_on_destroy = false
}
