# terraform/modules/snapshot — application-consistent snapshot module

Creates a snapshot schedule per lab node. The driver flushes
application state before the snapshot is taken, then signals
the platform that the snapshot is safe to capture.

Phase 1+ will:

- Create one `google_compute_snapshot` per node, on demand.
- Trigger the snapshot only after the driver reports
  `pre_snapshot` complete.
- Tag snapshots with the lab_id, the pack_id, and the
  snapshot name supplied by the operator.

No resource is enabled in Phase 0.