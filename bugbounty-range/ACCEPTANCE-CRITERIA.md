# BugBountyRange — Acceptance Criteria

Phase 0 is complete when every item below is satisfied. The
items map to the 19 Phase 0 deliverables in `DIRECTIVE.md`
Section 19.

## Documentation

- [ ] `DIRECTIVE.md` exists and covers all 20 sections.
- [ ] `README.md` exists and lists every Phase 0 deliverable.
- [ ] `THREAT-MODEL.md` exists and lists the 10 critical
      invariants.
- [ ] `ACCEPTANCE-CRITERIA.md` exists and is this file.
- [ ] All seven `docs/architecture-decisions/ADR-*` files
      exist.
- [ ] `notes/PHASE-0-RISKS.md` exists and lists every
      unresolved decision.
- [ ] `notes/PHASE-0-REPORT.md` exists with the first-response
      section matching `DIRECTIVE.md` Section 18.

## Architecture

- [ ] `docs/architecture.svg` exists. Phase 0 ships a text-art
      placeholder; the SVG is required before Phase 1.
- [ ] Every layer listed in `DIRECTIVE.md` Section 5 has at
      least one file in the corresponding directory.

## Schemas

- [ ] `schemas/lab-pack.schema.json` validates against the
      official JSON Schema meta-schema.
- [ ] `schemas/scenario.schema.json` validates against the
      official JSON Schema meta-schema.
- [ ] `schemas/driver-interface.schema.json` validates against
      the official JSON Schema meta-schema.
- [ ] `schemas/lifecycle-state.schema.json` validates against
      the official JSON Schema meta-schema.
- [ ] `schemas/evidence-format.schema.json` validates against
      the official JSON Schema meta-schema.
- [ ] All five schemas reject sample inputs that violate
      their stated constraints (negative tests).

## Control plane skeleton

- [ ] `src/bbr/cli.py` exposes the 14 commands listed in
      `DIRECTIVE.md` Section 10.
- [ ] `src/bbr/lifecycle/` contains the state machine skeleton
      and rejects every invalid transition listed in
      `DIRECTIVE.md` Section 9.
- [ ] `src/bbr/state/` documents the runtime state model and
      contains the platform-operator-visible state schema.
- [ ] `src/bbr/scenarios/` contains the runner skeleton with
      the destination-validation logic.
- [ ] `src/bbr/evidence/` contains the evidence-format
      implementation skeleton.
- [ ] `src/bbr/network/` contains the per-lab subnet allocator
      and the firewall-rule-builder skeleton.
- [ ] `src/bbr/secrets/` contains the per-lab secrets-store
      skeleton.

## Terraform foundation

- [ ] `terraform/foundation/` ships only commented-out
      `resource` blocks. No `terraform apply` is permitted in
      Phase 0.
- [ ] `terraform/modules/network/`, `compute-node/`,
      `snapshot/`, and `shutdown/` ship module skeletons.
- [ ] No module contains a hardcoded IP, port, or product
      name.

## Driver skeletons

- [ ] `drivers/compose-vm/` ships a Python module skeleton and
      a `compose_vm` reference manifest.
- [ ] `drivers/raw-vm/` ships a Python module skeleton and a
      `raw_vm` reference manifest.
- [ ] Neither driver contains product-specific code.

## Lab packs (Phase 0 manifests)

- [ ] `packs/smoke-compose/` ships a manifest that validates
      against `schemas/lab-pack.schema.json` using
      `compose_vm` for both nodes.
- [ ] `packs/smoke-vm/` ships a manifest that validates
      against `schemas/lab-pack.schema.json` using `raw_vm`
      for one node.
- [ ] `packs/wordpress-wp2shell/` ships a manifest that
      validates against `schemas/lab-pack.schema.json`,
      reproduces the topology from `labs/wordpress-cve-2026/`,
      and contains no WordPress-specific code in the platform
      core.

## Pack validation evidence

- [ ] `tests/acceptance/` ships three test packs
      (`smoke-compose.bundle.json`,
      `smoke-vm.bundle.json`,
      `wordpress-wp2shell.bundle.json`) that the platform
      validator accepts.
- [ ] A rejection test confirms an intentionally malformed
      pack is refused.

## Phase 0 report

- [ ] `notes/PHASE-0-REPORT.md` reports `resources_created: 0`.
- [ ] The report's first-response section matches
      `DIRECTIVE.md` Section 18 verbatim in structure.

## Repository discipline

- [ ] No file under `platform/your-lab-name/` contains
      secret material (verified by the static secret scan in
      `tests/`).
- [ ] No file under `platform/your-lab-name/` is tracked
      while containing any literal private-key marker, any
      WireGuard key-generation invocation, or any HackerOne API token
      (the exact strings are documented in
      `scripts/run-phase0-checks.sh` and must not appear in
      tracked files).
- [ ] The repository's `.gitignore` at root excludes
      `platform/your-lab-name/evidence/*` secrets and
      Terraform state artefacts.

## Phase gate

- [ ] The platform does not advance past Phase 0 until
      `APPROVE PHASE 1` is received verbatim from the platform
      operator.
## Phase 3 — Generic Single-Lab Lifecycle

Phase 3 acceptance:

  - `bbr validate platform/your-lab-name/packs/smoke-vm` exits 0.
  - The Phase 3 create plan produces exactly 7 resources and
    changes zero foundation resources.
  - The plan file is `/tmp/bbr-phase3-smoke-create-v1.tfplan`
    with a SHA-256 that matches the value recorded in
    `notes/PHASE-3-PLAN.md`.
  - `pytest -q` passes 100% across `tests/unit/` and
    `tests/acceptance/`.
  - `terraform fmt -check -recursive` reports PASS for the
    Phase 3 files (`terraform/lab/`, `modules/network/`,
    `modules/compute-node/`).
  - `terraform validate` reports PASS for both foundation and
    lab roots.
  - `./tools/check_phase2_wireguard_patterns.sh` reports PASS.
  - `git diff --check` reports clean.
  - The smoke-vm pack uses a pinned image self-link (no moving
    family).
  - The lab VM has no `access_config` block.
  - The lab network has an egress-deny firewall with
    priority 65000 targeting `0.0.0.0/0`.
  - The active lab limit of 1 is enforced by the allocator.
  - The Phase 3 create plan produces no VPC peering and no
    Cloud NAT resources.
  - No WordPress code, no Compose driver, no external IP, no
    external image or package downloads.

## Phase 3 — v2 hardening acceptance

  - `git check-ignore -v platform/your-lab-name/src/bbr/state/locking.py`
    reports NOT ignored; `git ls-files --error-unmatch ...` PASS.
  - `git check-ignore -v state/_probe.json` reports ignored.
  - The compute-node module binds `network_ip = var.internal_ip`
    and the startup template is rendered via `templatefile()`
    into `metadata_startup_script`.
  - `post-create.sh` performs no write actions.
  - The lab-subnet module has no `prevent_destroy` guard.
  - `PHASE3_SMOKE_CYCLE_LIMIT_EUR = 1.00` is enforced at the
    pack validation boundary (default value).
  - `bbr create` rejects missing flags, mismatched SHA, wrong
    commit, dirty working tree, `HEAD != origin/main`, missing
    runtime state, wrong state, wrong lab_id, wrong
    backend_prefix, plan shape not 7/0/0, unallowed resource
    types, or unallowed provider actions.
  - `bbr verify` rejects a missing VM with a non-zero exit.
  - `bbr destroy` produces a stored destroy plan and refuses
    to apply it.
  - 75 tests pass across `tests/unit/` and `tests/acceptance/`
    when invoked from a fresh clone with no ignored helper
    files polluting the source tree.

## Phase 3 — v4 closeout acceptance

The Phase 3 EXECUTE on the v3 plan completed successfully.
Two attempts to apply the original destroy plan failed;
the plan was retired as OBSOLETE. The following v4
closeout acceptance criteria are now required.

### Closeout fixes

- `bbr create` and any future apply-bearing command MUST
  reject a missing `GOOGLE_OAUTH_ACCESS_TOKEN` BEFORE
  any terraform subprocess runs. Exit code 18 is
  reserved for this case. The State stays unmutated.
- `bbr create` MUST detect a stale plan (current State
  serial differs from the plan's recorded serial) BEFORE
  invoking terraform apply. Exit code 19 is reserved for
  this case. The operator is instructed to re-plan.
- `bbr destroy` MUST refuse to silently overwrite an
  existing destroy plan whose State serial matches the
  current State. Exit code 10 is reserved for this case.
- `bbr verify` MUST use
  `gcloud compute firewall-rules list --format=json` and
  filter `targetTags` in Python. The obsolete alias
  `gcloud compute firewalls list` and the invalid
  `targetTags:` filter expression are forbidden.
- `bbr verify` MUST fail loudly (exit code 13) when the
  runtime state is `PLANNED` but lacks `transition_history`.
- Lifecycle transitions MUST be written by the CLI
  commands themselves. A Python helper invoked outside
  the CLI surface MUST NOT be used to advance the state.

### WireGuard routing/NAT

- The Phase 3 WireGuard data-path from the operator to
  the lab VM through the bastion tunnel did NOT work.
  IAP-tunneled SSH to the same VM succeeded.
- The most likely cause is a MASQUERADE rule on the bastion
  that rewrites the source of packets leaving `ens4` from
  the WG overlay to the bastion's internal IP.
- This is documented as a **working hypothesis only**. No
  Foundation change is permitted on the basis of this
  hypothesis alone. Verification requires packet captures,
  `iptables -t nat -L`, and routing-table inspection on
  the bastion.

### Authorisation gates

- The original `APPROVE PHASE 3 DESTROY EXECUTE` for
  plan `/tmp/bbr-smoke-vm-001-destroy.tfplan` (SHA-256
  `a2bbce9a394f735b51acd4ac5ec09a6fc9c0d9ffc2e596b5858353d99a36e272`)
  is OBSOLETE. That plan file MUST NOT be re-applied.
- A new destroy plan (v2) MUST be generated from the
  current State in a separate planning gate before any
  new `APPROVE PHASE 3 DESTROY EXECUTE` is considered.

### Tests

- 80 tests pass across `tests/unit/` and
  `tests/acceptance/` from a clean working tree with
  HEAD equal to origin/main.
- No regression in any previously-passing test.
- New tests cover the four closeout fixes:
  credential preflight, plan-freshness check, destroy
  plan overwrite protection, verify firewall filter fix.

## Phase 4 — Implementation Acceptance

- Teststand: 134 gesammelt, 132 bestanden, 2 Root-Ownership-Prüfungen auf
  dem unprivilegierten Runner übersprungen.
- [x] Bootstrap downloader, verifier, runtime secret handling and exits 30–39.
- [x] Atomic artifact, timestamp, substate and health-state writes.
- [x] Extended lifecycle including failure and rollback.
- [x] WordPress-Smoke pack and until-destroy priority-1000 HTTPS egress module.
- [x] Deterministic tar/zstd arguments and tool versions are documented.
- [x] Tests, Terraform validation/fmt, pattern guards and diff checks specified.
- [x] Artifact upload and live GCP execution (separate EXECUTE gate).

## Phase 4 — Pre-Execute-Korrektur Acceptance

- [x] **Blocker A — Backend-Konfiguration terraform-konform.**
  Lab-Root verwendet Partial Configuration (kein Backend-Block mit
  Variablen-Interpolation). Backend-Werte werden zur Init-Zeit
  per `terraform init -backend-config=bucket=...` übergeben
  (Phase-3-Mechanismus, unverändert).
- [x] **Blocker A Test.** `test_lab_root_backend_is_partial_configuration`
  prüft explizit, dass kein `terraform { backend "..." { ... } }`-Block
  mit `${var.}`-Interpolation existiert.
- [x] **Blocker B — Bootstrap-Egress instanziiert.** Plan v3 enthält
  genau 9 add (statt 8). Die zusätzliche Ressource ist die
  bucket-scoped `roles/storage.objectViewer`-Bindung; außerdem bleibt
  `module.bootstrap_egress.google_compute_firewall.bootstrap_egress`
  mit priority 1000, direction EGRESS, protocol tcp/443 und
  destination_ranges `['199.36.153.4/30']`, TCP/443, until destroy.
- [x] **Blocker B Test.** `test_module_instantiated_in_lab_main_tf`
  bestätigt die Instanziierung.
- [x] **Plan-Stats konsistent.** Plan v3 = 9 add / 0 change / 0 destroy,
  dokumentiert in README.md und diesem Acceptance-Dokument.
- [x] **Default-Deny-Egress bleibt.** `module.lab_node.google_compute_firewall.egress_deny`
  mit priority 65000 bleibt unverändert.
- [x] **Keine Foundation-Ressourcen.** Foundation-Adresse erscheint
  weiterhin nur in `data.terraform_remote_state.foundation`, nicht im Plan.
- [x] **Keine externe IP auf Lab-VM.** `network_interface[].access_config = []`.
- [x] **Kein Cloud NAT.** Kein `google_compute_router_nat` im Plan.
- [x] **Keine VPC-Peering-Änderung.** Kein Peering-Resource im Plan.
- [x] **Pattern-Guards.** `./tools/check_phase2_wireguard_patterns.sh` PASS.
- [x] **Backend-Konsistenz mit Phase 3.** Bucket = `bbr-state-${var.gcp_project_id}`
  (nur in `data.terraform_remote_state.foundation`, dort erlaubt).
  Prefix = `labs/<lab_id>` (per `-backend-config=prefix=labs/${lab_id}`).
- [x] **Kein lokaler terraform.tfstate.** `*.tfstate` in `.gitignore`,
  State lebt in GCS.

## Phase 4A — Release Acceptance

- [x] Vollständiger Offline-Runtime-Bundle aus 160 Debian-12-Paketen.
- [x] WordPress 6.8.2 Input-SHA-256 verifiziert.
- [x] Produktiver Minisign-0.12-Key erzeugt; Private Key 0600.
- [x] Artefakt deterministisch gebaut, signiert und lokal rebuild-verifiziert.
- [x] Festes Custom Image mit vorinstalliertem Minisign ist `READY`.
- [x] GCS-Bucket: UBLA, PAP enforced, Versioning, versionierter Pfad.
- [x] Dedicated runtime SA besitzt bucket-scoped Object-Viewer als 9. Lab-Ressource.
- [x] Startup lädt authentifiziert, prüft SHA/Minisign/Manifest, entpackt
  nach `/opt/bbr`, bootstrapt und schreibt Ready erst nach Erfolg.
- [x] Reviewbarer finaler Create-Plan v10 9/0/0 wird nach dem finalen
  Commit unter `/tmp/bbr-phase4-wordpress-create-v10.tfplan` erzeugt.
