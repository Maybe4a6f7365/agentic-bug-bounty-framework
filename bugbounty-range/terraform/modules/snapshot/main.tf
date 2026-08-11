# Snapshot module — Phase 0.

# Phase 1+ will create:
#   google_compute_snapshot.node
#     name        = "bbr-<lab-id>-<node-id>-<snapshot_name>"
#     source_disk = var.source_disk_self_link
#     labels      = var.labels
# No active resource definitions in Phase 0.

output "snapshot_self_link" {
  description = "Phase 0 stub."
  value       = null
}