# Research-Repo Contract — contributor guidance

**Effective date:** 2026-07-16
**Authoritative schema:** [`OPEN_CONTRACT.yaml`](OPEN_CONTRACT.yaml)

`OPEN_CONTRACT.yaml` is the machine-readable, authoritative definition of repository governance, field ownership, controlled vocabularies, lifecycle rules, submission counting, closure, replication indexes, and generated files. This document is intentionally limited to human guidance. If this prose and the YAML disagree, the YAML wins and this file must be corrected.

## Field ownership

- `findings-manifest.json` owns finding identity, `record_kind`, qualification, evidence, current severity, research state, and closure reason.
- `runs/handoffs/*.yaml` owns external submission and triage events. A manifest must not manufacture submission state.
- `contract.yaml` owns target scope, program policy, authorization, and target-specific constraints.
- `pre_scan.yaml` is a refreshed operational snapshot; its known-finding count must match the manifest.
- `README.md`, `_index.md`, `OUTCOMES.md`, and `REPLICATION_INDEX.md` are generated views, never authoritative state.

## Working rules

Maintain one canonical `findings-manifest.json` per target. Run records are provenance snapshots; promote reviewed records into that canonical manifest. Never silently delete a record. Preserve verdict and severity changes in append-only `revision_history` entries.

Classify every record as `observation`, `hypothesis`, `vulnerability`, or `positive_verification`. Only vulnerabilities that pass qualification may become report-ready. A report is counted as submitted only when its handoff ledger contains a real `submitted` event and a non-placeholder HackerOne report ID. Bootstrapped or translated handoff records are not submissions.

## Closure and parking

Closed records use exactly one controlled `closure_reason`:

- `control_held`
- `intended_behavior`
- `duplicate`
- `out_of_scope`
- `no_impact`
- `privilege_equivalent`
- `version_mismatch`
- `access_blocked`

`parked` is a research state, not a closure reason. A parked record remains open and must state its unblock condition. Do not use `WALKED`, `REJECTED`, `INERT`, `informational`, or `not_submitted` as new closure reasons; translate legacy values to the taxonomy above when a record is revised.

## Severity revisions

`severity` is the current proven assessment. When evidence closes or downgrades a claim, move the former value into `revision_history[].from`, set current severity to the final assessment, and explain why. Generated views may say “previously claimed X,” but must lead with current severity.

## Replication indexes

Replication indexes use repository-relative paths only. `source_available: false` means an external source is unavailable to ordinary clones and the committed mirror is the portable source. Logical provenance belongs in `source_identifier`; host paths never belong in committed views.

## Generated files

Use explicit write/check interfaces:

```bash
tools/regenerate_readme.sh --write
tools/regenerate_readme.sh --check
```

Generated regions carry `AUTO-GENERATED-START` / `AUTO-GENERATED-END` markers. Edit canonical inputs, regenerate, and review the diff.

For exact required fields, enums, submission predicates, and lifecycle constraints, consult [`OPEN_CONTRACT.yaml`](OPEN_CONTRACT.yaml).
