# ADR-0006 — State and locking model

## Status

Accepted, 2026-07-25.

## Context

The platform needs:

- Per-lab runtime state (the lifecycle state machine
  position, the node list, the snapshots, the cost
  projection, the TTL deadline).
- A lock that prevents two control-plane processes from
  applying conflicting changes to the same lab.
- A means of recording who created which lab and when.
- A means of recovering from a corrupted or missing state
  file.

## Decision

### Per-lab runtime state

Per-lab runtime state lives in the platform's runtime state
file. The schema is `schemas/lifecycle-state.schema.json`.
The file lives at one of:

- `state/<lab-id>.json` inside the platform repository
  (committed, reviewable).
- `<runtime-state-bucket>/labs/<lab-id>/state.json` inside
  a GCS bucket (private, versioned, lifecycle-cleaned).

For v1, the file is committed to `state/` because the
platform's runtime is the operator's workstation, not a
shared server. Future versions may move to the GCS bucket.

The state file is append-only. Each transition records the
`from` state, the `to` state, the timestamp, the operator
identity, and the rationale. The state machine rejects
transitions that are not in the allowed set
(see `DIRECTIVE.md` Section 9).

### Lock

The platform uses the Terraform state lock (GCS object lock
on the lab's tfstate file) as the primary concurrency
control. A second control-plane process that tries to
acquire the lock waits or fails fast depending on
configuration.

A second lock, the runtime-state lock, prevents two
processes from recording conflicting lifecycle transitions
on the same lab. The runtime-state lock is implemented as
a small `state/<lab-id>.lock` file written with
`O_CREAT | O_EXCL`. The lock is removed on every
transition, including on error.

### Operator identity

Every transition records the operator identity from the
gcloud credentials (the email address returned by
`gcloud auth list --filter=status:ACTIVE --format="value(account)"`).
A transition is rejected if no active gcloud identity is
present.

### Recovery from corrupted or missing state

`bbr list` reports all known labs. A lab whose state file
is missing is reported as `UNKNOWN`. The platform refuses
to apply changes to an `UNKNOWN` lab until the operator
issues an explicit `bbr reconcile <lab-id>` which compares
the runtime state against the Terraform state and the GCP
state and surfaces discrepancies for the operator to
resolve.

A lab whose state file is corrupted is reported as
`CORRUPT`. The platform refuses all transitions until the
operator manually restores from a backup.

## Consequences

- Two operators cannot simultaneously create conflicting
  changes to the same lab.
- The full history of a lab is recoverable from the
  appended transitions.
- A misbehaving control-plane process cannot silently
  desynchronise a lab from GCP because the runtime state
  records every Terraform apply.
- Recovery is operator-driven; the platform does not guess
  what to do.

## Alternatives considered

- **SQLite or PostgreSQL for runtime state.** Rejected
  because the platform is operator-local in v1. A future
  version may migrate.
- **etcd / ZooKeeper.** Rejected because the platform does
  not need distributed consensus in v1.
- **Event sourcing.** Considered but rejected because the
  append-only transition log is sufficient and simpler.