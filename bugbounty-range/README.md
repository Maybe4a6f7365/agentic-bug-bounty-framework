# BugBountyRange — README

## Phase-4A correction

The WordPress lab uses its dedicated runtime service account and a per-bucket
`roles/storage.objectViewer` member; no project-wide storage grant or default
Compute Engine service account is used. The plan-v5 contract is 9 add, 0 change,
0 destroy. Bootstrap egress stays restricted to the documented Google API
ranges for the lab lifetime and is removed only by `bbr destroy`.

`bbr verify wordpress-smoke-001` defaults to the real, read-only GCP and
IAP-SSH verification path. Keep this operator tunnel open:

```bash
gcloud compute ssh wordpress-smoke-001 --tunnel-through-iap -- -L 8080:127.0.0.1:80 -N
```

Run HTTP and WordPress tests in another shell.

## What this is

BugBountyRange is a generic, product-agnostic GCP lab
platform for local, isolated differential testing of
vulnerable-versus-patched software stacks in support of
bug-bounty research. See `DIRECTIVE.md` for the authoritative
specification and `THREAT-MODEL.md` for the security model.

## Status

**Phase 4A — Release und Create-Plan vollständig.**
Der vollständige Offline-Runtime-Bundle wurde deterministisch gebaut,
mit dem produktiven Minisign-Key signiert, lokal rebuild-verifiziert
und unveränderlich nach GCS hochgeladen. Das feste Custom Compute Image
mit Minisign 0.12 ist `READY`. Es erfolgte kein `terraform apply`;
die Lab-Ausführung bleibt am separaten EXECUTE-Gate.

**Phase 4 — Pre-Execute-Korrektur abgeschlossen.** Zwei
Lücken aus dem v1-Plan-Review sind behoben:

- **Blocker A — Backend-Konfiguration.** Der Phase-3-Mechanismus
  (`terraform init -backend-config=bucket=... -backend-config=prefix=...`)
  bleibt unverändert. Der Versuch, den Backend-Block in HCL mit
  Variablen zu deklarieren, wurde rückgängig gemacht, weil Terraform
  Backends VOR der Variablenauswertung initialisiert.
- **Blocker B — Bootstrap-Egress instanziiert.** Das `bootstrap-egress`-Modul
  (priority-1000-EGRESS-Firewall, tcp/443, Zielbereiche
  `199.36.153.4/30`, TCP/443) wird jetzt im Lab-Root
  instanziiert. Dadurch erhöht sich die Anzahl der Lab-Ressourcen
  von 7 auf **8**. Default-Deny-Egress (priority 65000) bleibt
  unverändert.

Der reviewbare Phase-4A-Create-Plan v4
`/tmp/bbr-phase4-wordpress-create-v4.tfplan` hat
**9 add / 0 change / 0 destroy** und SHA-256
`f5995993db29c7e8286c0a419d54f72a32d0c637cc0bf4c73a81e1057759aecd`.

**Phase 3 — generic single-lab lifecycle vertical slice
applied.** The Phase 3 create plan was reviewed, applied
(`7 add / 0 change / 0 destroy`), the lab went through the
full lifecycle into `READY`, and the readiness marker,
egress-deny behaviour, and WireGuard handshake were
verified end-to-end. The Foundation resources (Phase 1,
Phase 2) remain at 21 / unchanged.

Two attempts to apply the original destroy plan failed
(credential preflight missing, then saved plan bound to a
divergent State). The plan was retired as OBSOLETE. The
CLI was hardened to catch both failure modes before any
State mutation. See `notes/PHASE-3-PLAN.md` and
`docs/architecture-decisions/ADR-0009-lab-lifecycle.md`
for the full root-cause analysis and the v4 closeout
corrections.

Phase 0 produced the platform directive, threat model,
architecture diagram, schemas, state machine, network
isolation model, evidence format, cost and TTL model, three
required lab packs, and the Phase 0 report.

Phase 2 produced the shared access plane (bbr-bastion,
bbr-shared-vpc, bbr-bastion-subnet, WireGuard overlay) and
the 21 foundation resources. See
`notes/PHASE-2-REPORT.md` and
`notes/PHASE-2-WIREGUARD-VALIDATION.md`.

Phase 3 produces the generic per-lab Terraform root, the
network allocator, the lifecycle state machine, the
runtime-state lock, the reviewable CLI commands, and the
closeout corrections. See `notes/PHASE-3-PLAN.md` and
`docs/architecture-decisions/ADR-0009-lab-lifecycle.md`.

## Repository layout

```
platform/your-lab-name/
├── DIRECTIVE.md            authoritative specification
├── README.md               this file
├── THREAT-MODEL.md         threat model
├── ACCEPTANCE-CRITERIA.md  acceptance test plan
├── pyproject.toml          Python control plane packaging
├── src/bbr/                Python control plane (skeleton)
├── schemas/                JSON Schema definitions
├── terraform/              Terraform foundation + modules
├── drivers/                compose_vm and raw_vm driver skeletons
├── packs/                  smoke-compose, smoke-vm, wordpress-wp2shell
├── tests/                  platform tests
├── docs/                   diagrams and architecture decisions
├── evidence/               per-lab evidence (empty in Phase 0)
└── state/                  runtime state docs only
```

## Required inputs (Phase 1)

```
BILLING_ACCOUNT_ID
GCP_PROJECT_ID
GCP_REGION
GCP_ZONE
PLATFORM_OPERATOR_LABEL
ACTIVE_LAB_LIMIT
BUDGET_EUR_EQUIVALENT
VPN_ALLOWED_STATIC_CIDRS
LAB_OWNER_LABEL
```

See `DIRECTIVE.md` Section 3.

## Phase 0 deliverables (status)

| # | Deliverable | Location |
|---|---|---|
| 1 | Platform directive | `DIRECTIVE.md` |
| 2 | Threat model | `THREAT-MODEL.md` |
| 3 | Architecture diagram | `docs/architecture.svg` (placeholder) |
| 4 | Lab-pack schema | `schemas/lab-pack.schema.json` |
| 5 | Scenario schema | `schemas/scenario.schema.json` |
| 6 | Driver interface schema | `schemas/driver-interface.schema.json` |
| 7 | Lifecycle state model | `schemas/lifecycle-state.schema.json` + `src/bbr/lifecycle/` |
| 8 | Network-isolation model | `docs/architecture-decisions/ADR-0003-network.md` |
| 9 | Secrets model | `docs/architecture-decisions/ADR-0004-secrets.md` |
| 10 | Terraform module boundaries | `docs/architecture-decisions/ADR-0005-terraform.md` |
| 11 | State and locking model | `docs/architecture-decisions/ADR-0006-state.md` |
| 12 | Evidence format | `schemas/evidence-format.schema.json` |
| 13 | Cost and TTL model | `docs/architecture-decisions/ADR-0007-cost.md` |
| 14 | Acceptance test plan | `tests/acceptance/` |
| 15 | Migration map | `docs/architecture-decisions/ADR-0002-migration.md` |
| 16 | Risks and unresolved decisions | `notes/PHASE-0-RISKS.md` |
| 17 | Repository tree | Section 5 of `DIRECTIVE.md` |
| 18 | Phase 0 report | `notes/PHASE-0-REPORT.md` |
| 19 | Approval phrase | `DIRECTIVE.md` Section 20 |

## Phase 0 gate

The platform cannot proceed until the exact phrase
`APPROVE PHASE 1` is received from the platform operator.
