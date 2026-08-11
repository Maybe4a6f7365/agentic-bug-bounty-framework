# BugBountyRange Platform Directive (authoritative)

## 1. Purpose

BugBountyRange (BBR) is a generic, product-agnostic GCP lab
platform for local, isolated differential testing of
vulnerable versus patched software stacks in support of
bug-bounty research. It is **not** a vulnerability scanner, an
exploit framework, or a target-intelligence tool. It exists
so that researchers can validate behavioural hypotheses about
a CVE or class of issue against a fully reproducible,
sandboxed lab before any contact with a HackerOne target.

The platform is intentionally generic. WordPress, GitLab,
Nginx, Node.js, Java services or any other technology stack
must be supported through a lab pack containing only
declarative manifests, Compose files, provisioning scripts,
fixtures, readiness checks, snapshot hooks, and test
scenarios. Adding a new technology stack must **not** require
changes to the platform core.

## 2. Scope

In scope:

- A Python control plane (`bbr` CLI).
- Generic Terraform infrastructure primitives for one shared
  access VPC, per-lab network segments, per-lab firewall
  policies, per-lab compute, snapshots, and shutdown.
- Two execution drivers in the first release:
  `compose_vm` and `raw_vm`.
- A lifecycle state machine covering all transitions between
  the 11 states defined in Section 9.
- A generic scenario runner that supports lab-local HTTP,
  HTTPS, raw TCP, approved shell scripts, readiness checks,
  log capture, filesystem hashes, database comparisons,
  process / container state, and full response capture.
- A generic evidence and differential engine that compares
  two lab states or two scenarios and emits a redacted
  machine-readable diff.
- Three required first-release lab packs:
  `smoke-compose`, `smoke-vm`, and `wordpress-wp2shell`.

Out of scope (version 1):

- Kubernetes, GKE, Cloud SQL, or any managed-cluster layer.
- A web dashboard or GUI of any kind.
- Multi-user tenancy, RBAC, or per-user lab quotas.
- Arbitrary dynamic Python plugin loading.
- Executing untrusted lab packs from external repositories.
- Automatically downloading unknown vulnerable images.
- Connectivity to any HackerOne target or production system.
- Internet-scanning capabilities.
- Autonomous exploit generation or CVE payload generation.

## 3. Required human-supplied inputs (Phase 0 + Phase 1)

```text
BILLING_ACCOUNT_ID
GCP_PROJECT_ID                 # one dedicated project per platform
GCP_REGION                     # default europe-west3
GCP_ZONE                       # default europe-west3-a
PLATFORM_OPERATOR_LABEL        # operator identifier, no colon (e.g. your-researcher-handle)
ACTIVE_LAB_LIMIT               # default 1, hard max 2 in v1
BUDGET_EUR_EQUIVALENT          # hard cost cap; lab stops if forecast exceeds
VPN_ALLOWED_STATIC_CIDRS       # JSON list of /32 source CIDRs allowed on
                                # WireGuard UDP/51820 (Hermes worker,
                                # known Hermes agents)
LAB_OWNER_LABEL                # lab-owner identifier, no colon (e.g. your-researcher-handle)
                                # applied to every created resource as a label

# Required: project parent. Exactly one of the two must be set.
GCP_ORGANIZATION_ID            # numeric organisation ID under which the
                                # dedicated project is created. Empty if
                                # GCP_FOLDER_ID is set instead.
GCP_FOLDER_ID                  # numeric folder ID (must pre-exist; the
                                # platform never creates folders). Empty
                                # if GCP_ORGANIZATION_ID is set instead.
```

The platform operator is expected to source these inputs from
their own workstation or runtime environment. The platform
must not ask for them at runtime through interactive prompts
once Phase 1 has begun.

## 4. Platform operator contract

Hermes (or any other agent acting on the operator's behalf)
must follow these rules exactly:

1. Execute one numbered phase at a time.
2. Stop at every `HUMAN GATE` and wait for the exact approval
   phrase shown in the relevant report.
3. Do not create or modify any GCP resource before the exact
   `APPROVE PHASE N` phrase has been received for that phase.
4. Do not add "helpful" services, products, or platforms
   without approval.
5. Do not run untrusted lab packs from external sources. Every
   pack must live inside `packs/<pack-name>/` in this
   repository.
6. Do not introduce product-specific adapters. A new product
   is added by creating a new pack, never by editing the
   platform core.
7. Do not modify the Python control plane, Terraform
   foundation, lifecycle state machine, network isolation
   model, scenario runner, evidence engine, or secrets model
   in order to support a new product.
8. All Terraform changes must be idempotent and reviewable
   through `terraform plan`.
9. Use Infrastructure as Code. Terraform is mandatory for GCP
   resources.
10. Never place secrets in Git, Terraform state, Terraform
    variables, VM metadata, startup scripts, console output,
    issue comments, or logs.
11. Never resolve, follow, or exfiltrate destinations outside
    an active lab's registered network.
12. Stop immediately on any stop condition in Section 15.

For each completed phase, return:

- commands and actions performed;
- files created or changed;
- resources created or changed;
- verification output with secrets redacted;
- current estimated cost and remaining budget headroom;
- deviations: `none` or a precise explanation;
- the next required approval phrase.

## 5. Required repository layout (Phase 0 minimum)

```text
platform/your-lab-name/
├── DIRECTIVE.md                              (this file)
├── README.md
├── THREAT-MODEL.md
├── ACCEPTANCE-CRITERIA.md
├── pyproject.toml
├── src/bbr/                                  (control plane)
│   ├── __init__.py
│   ├── cli.py
│   ├── state/
│   ├── lifecycle/
│   ├── scenarios/
│   ├── evidence/
│   ├── network/
│   └── secrets/
├── schemas/                                  (JSON Schema definitions)
│   ├── lab-pack.schema.json
│   ├── scenario.schema.json
│   ├── driver-interface.schema.json
│   ├── lifecycle-state.schema.json
│   └── evidence-format.schema.json
├── terraform/
│   ├── foundation/                           (single project, VPC,
│   │                                         bastion, state bucket)
│   └── modules/
│       ├── network/                          (per-lab subnet)
│       ├── compute-node/                     (generic VM module)
│       ├── snapshot/                         (per-lab snapshot policy)
│       └── shutdown/                         (scheduled-stop policy)
├── drivers/
│   ├── compose-vm/                           (compose_vm driver)
│   └── raw-vm/                               (raw_vm driver)
├── packs/                                    (lab packs)
│   ├── smoke-compose/
│   ├── smoke-vm/
│   └── wordpress-wp2shell/
├── tests/                                    (platform tests)
├── docs/
│   ├── architecture-decisions/               (ADR-0001, ...)
│   └── architecture.svg                      (Phase 0 diagram)
├── evidence/                                 (per-lab evidence)
└── state/                                    (runtime state docs only)
    └── README.md
```

Runtime state, Terraform state, secrets, generated VPN
configurations, private keys, and temporary credentials must
never be committed.

## 6. Generic execution drivers

Two drivers are required in v1. They are the only sanctioned
ways the control plane can create state on a compute node.

### 6.1 `compose_vm`

Creates a private Compute Engine VM and deploys a
lab-pack-supplied Docker Compose topology on that VM.

Inputs (from the lab pack, validated against
`schemas/lab-pack.schema.json`):

- A pinned Debian 12 base image digest.
- A `compose_vm.composelist` manifest describing services,
  networks, volumes, restart policies, security options, log
  rotation, and resource limits.
- A readiness check manifest describing how each service is
  verified as healthy.
- Lifecycle hooks: `pre_create`, `post_create`, `pre_destroy`,
  `post_destroy`. Hooks are scripts bundled in the pack.
- Snapshot hooks: `pre_snapshot`, `post_snapshot`.

The driver MUST NOT contain WordPress-specific behaviour, or
any product-specific branches.

### 6.2 `raw_vm`

Creates a private Compute Engine VM from an allowlisted base
image and executes lab-pack-supplied provisioning and
lifecycle hooks.

Inputs:

- An allowlisted base image identifier from the platform
  operator's curated image list (Debian 12 by default).
- A list of `packages` to install.
- A list of `systemd_units` to enable.
- A list of `provisioning_scripts` to run on first boot.
- A readiness check manifest.
- Lifecycle hooks (same as `compose_vm`).
- Snapshot hooks (same as `compose_vm`).

The driver MUST NOT contain WordPress-specific behaviour. It
is designed for software that requires systemd, native
packages, custom OS configuration, or cannot run correctly in
containers.

A lab topology may contain multiple nodes and may mix both
drivers. The platform core must not special-case any
combination.

## 7. Generic topology support

A lab pack declares:

- one or more `nodes`;
- `driver` per node (`compose_vm` or `raw_vm`);
- `machine_type` per node;
- `disk_type` and `disk_size` per node;
- `base_image` per node (pinned by digest or allowlisted by
  identifier);
- Compose file or provisioning scripts per node;
- private IP allocation (assigned by the platform from a
  per-lab pool);
- exposed private services (only reachable from inside the
  lab's network);
- `dependencies` between nodes;
- `readiness_checks` per node;
- runtime and bootstrap egress policy;
- permitted node-to-node flows;
- snapshot hooks;
- restoration hooks;
- health verification commands;
- `evidence_sources` (which files to capture and where);
- `comparison_groups` (which nodes form a pair for the
  differential engine);
- `test_scenarios` (which scenarios the runner will execute);
- `ttl` (time-to-live; auto-destroy deadline);
- `cost_limits` (per-lab and per-cycle);
- `teardown_requirements` (must-be-running checks before
  destroy).

No node, service, port, version, product, or private IP may
be hardcoded in the platform core.

## 8. Networking model

### 8.1 Shared access plane

The platform provisions one shared VPC inside the dedicated
GCP project. Inside the shared VPC:

- One WireGuard access subnet holds the bastion VM that
  receives WireGuard tunnels from operators.
- The bastion is the only VM with a public IPv4 address
  (UDP/51820, source-restricted to `VPN_ALLOWED_STATIC_CIDRS`).

### 8.2 Per-lab network segments

Every active lab receives, provisioned through Terraform on
`bbr create`:

- A dedicated subnet (`10.<lab-id>.<lab-index>.0/24`,
  allocated by the platform from a documented range).
- Dedicated network tags and a dedicated runtime service
  account, used together to target the lab's firewall rules.
- Default-deny ingress from any other lab's subnet.
- Default-deny runtime internet egress. Bootstrap egress is
  permitted only while a per-lab `enable_bootstrap_egress`
  flag is set to `true` (e.g. for one-shot image pull during
  `bbr bootstrap`); the allowlist persists until `bbr destroy`.
- VPN-only operator access via the bastion. The lab's VMs
  have no public IPv4 address.
- A unique private IP allocation derived by the platform.
- Independently removable firewall and routing policy. A lab
  can be destroyed without disturbing other labs' network
  state.

### 8.3 Enforcement

The platform must enforce the isolation policy through GCP
cloud controls — VPC firewall rules, subnet routing, service
accounts, IAP TCP forwarding, and shielded VM options — not
through Python CLI behaviour alone. A misbehaving scenario
script must not be able to exfiltrate data outside the lab's
network.

### 8.4 Active-lab cap

The default maximum number of active labs is **one**. The
hard configurable maximum for v1 is **two**. The platform
must reject `bbr create` once the cap is reached.

## 9. Lifecycle state machine

```
DEFINED
  → VALIDATED    (bbr validate)
  → PLANNED      (bbr plan)
  → CREATED      (bbr create)
  → BOOTSTRAPPING (bbr bootstrap)
  → ISOLATED     (bbr isolate)
  → READY        (bbr verify)
  → TESTING      (bbr run / bbr diff)
  → STOPPED      (bbr stop)
  → DESTROYED    (bbr destroy)
```

Side transitions:

- `STOPPED → READY` (bbr start)
- `READY → STOPPED` (bbr stop)
- `CREATED → DESTROYED` is rejected; the lab must first be
  `STOPPED` then destroyed via `bbr destroy --force` if
  partial provisioning left network state behind.
- Any transition not listed above is rejected by the state
  machine.

The state machine MUST be generic. WordPress-specific
transitions or product-specific shortcuts are forbidden.

## 10. Required commands

```text
bbr validate <pack>                 # Validate a pack against the schema.
bbr plan <pack>                     # Render a Terraform plan summary.
bbr create <pack>                   # Provision the lab.
bbr bootstrap <lab-id>              # Pull images / run provisioning.
bbr isolate <lab-id>                # Preserve the until-destroy GCS allowlist.
bbr verify <lab-id>                 # Run readiness checks.
bbr snapshot <lab-id> --name <n>    # Application-consistent snapshot.
bbr restore <lab-id> --snapshot <n> # Restore a lab from a snapshot.
bbr run <lab-id> --scenario <s>     # Run a scenario.
bbr diff <lab-id> --scenario <s>    # Differential engine on a scenario.
bbr stop <lab-id>                   # Stop all nodes cleanly.
bbr start <lab-id>                  # Restart stopped nodes.
bbr destroy <lab-id>                # Destroy a lab.
bbr list                            # List active labs.
```

The lifecycle commands MUST be implemented in the generic
control plane. Pack-specific convenience wrappers are
forbidden.

## 11. Generic scenario runner

The scenario runner supports lab-local:

- HTTP requests;
- HTTPS requests;
- raw TCP exchanges;
- approved shell scripts bundled inside the lab pack;
- readiness checks;
- log capture;
- filesystem before / after hashes;
- database snapshot or dump comparison;
- process and container state inspection;
- response status, headers, body, hash, size, and timing.

All scenario destinations MUST resolve to services
registered in the active lab state. The runner rejects:

- arbitrary external URLs;
- public IP destinations;
- unregistered hostnames;
- automatic redirect following unless explicitly permitted by
  the lab pack;
- automatic retries unless explicitly declared;
- destinations inherited from response data;
- production target hostnames;
- bug-bounty target data, cookies, tokens, or credentials.

The network isolation layer is the final enforcement
boundary. A buggy scenario script cannot escape the lab.

## 12. Generic evidence and differential engine

The evidence engine captures, per scenario and per node:

- response status;
- response headers (full set, normalised);
- response body (raw bytes + content hash + size);
- response timing;
- container / process state;
- filesystem hashes for declared paths;
- log excerpts from declared log sources.

The differential engine consumes two lab states (typically
`vulnerable` and `patched` comparison groups defined in the
pack) and emits a machine-readable diff. The diff lists:

- status-code differences;
- header additions, removals, modifications;
- body byte differences and content hash differences;
- timing differences beyond a configurable threshold;
- filesystem hash differences for declared paths;
- process / container-state differences.

Output format is documented in
`schemas/evidence-format.schema.json`. Secrets are redacted
at the runner layer, not at the diff layer.

## 13. Secrets model

Secrets are scoped per lab. They live on disk only inside
`/etc/bbr/<lab-id>/secrets/`, mode `0600`, owner `root:root`,
generated by the platform using a cryptographic RNG. They
are never committed. They are never written to Terraform
variables, Terraform state, the lab manifest, or scenario
output. They are destroyed by `bbr destroy`.

The platform core never reads user-supplied private keys.
Client WireGuard keys for the operator are generated on the
operator's workstation. The platform receives only public
keys. Private keys for the bastion are generated on first
boot and never leave the bastion's `/etc/wireguard/`.

## 14. Cost and TTL model

- `BUDGET_EUR_EQUIVALENT` is the hard cost cap for the entire
  platform, not per-lab.
- Each pack declares `cost_limits` (per-lab and per-cycle).
  The control plane must reject `bbr create` if the sum of
  per-lab limits across active labs would exceed
  `BUDGET_EUR_EQUIVALENT - safety_margin`.
- Each pack declares `ttl`. The control plane enforces TTL
  via a scheduled stop and destroy.
- Forced teardown deadline is set to 48 hours before
  `CREDIT_EXPIRY_DATE`, supplied by the platform operator.
- The control plane records per-lab cost projections and
  surfaces them in `bbr list`.

## 15. Mandatory stop conditions

The control plane stops any operation and surfaces a
machine-readable error if:

1. The platform core is asked to introduce a product-specific
   branch.
2. The platform is asked to expose a lab VM's public IPv4 or
   to add a public load balancer.
3. The platform is asked to relax default-deny ingress between
   labs.
4. The platform is asked to allow runtime internet egress
   without an explicit per-lab bootstrap flag.
5. A scenario attempts to reach an unregistered destination.
6. A scenario follows a redirect without explicit pack
   permission.
7. A scenario inherits a destination from response data.
8. A scenario references production-target data, cookies,
   tokens, or credentials.
9. A lab exceeds its `cost_limits` projection.
10. The cumulative cost forecast across active labs exceeds
    `BUDGET_EUR_EQUIVALENT - safety_margin`.
11. A lab's TTL is reached.
12. A pack fails schema validation.
13. A Terraform plan would modify or delete resources outside
    the active lab.
14. A pack fetches an image that is not pinned by digest or
    not allowlisted by identifier.
15. The control plane is asked to load Python code from
    outside the platform repository.
16. The platform is asked to start more than
    `ACTIVE_LAB_LIMIT` labs.
17. A requested action is not explicitly covered by this
    directive.

## 16. Migration from the existing WordPress lab

The existing `labs/wordpress-cve-2026/` directory remains the
reference specification until the WordPress pack in
`packs/wordpress-wp2shell/` demonstrates full parity. The
migration is documented in
`docs/architecture-decisions/ADR-0002-migration.md` and
executed only after Phase 0 approval.

The WordPress pack must preserve:

- exact WordPress versions 6.9.4 and 6.9.5;
- immutable image digests;
- identical PHP and MariaDB versions;
- identical configuration, themes, plugins, and synthetic
  content;
- disabled automatic WordPress updates;
- no public application access;
- no runtime internet egress;
- application-consistent snapshots;
- deterministic restoration;
- direct private communication to each target;
- raw response and side-effect comparison.

## 17. Explicit prohibitions

The control plane MUST NOT:

- introduce a WordPress-specific or any product-specific
  adapter class;
- hardcode the three WordPress VMs, their IPs, their ports,
  or any WordPress-related constants;
- execute a Terraform `apply` outside an approved phase;
- enable APIs outside the approved allowlist;
- create additional public IPs beyond the single bastion
  external address;
- create additional SSH ingress beyond the IAP TCP forwarder;
- resolve or contact any HackerOne target, production system,
  or external host other than the bastion, the lab VMs, and
  the registry / image-distribution endpoints explicitly
  allowlisted for image pulls;
- download an image whose digest is not pinned in the lab pack;
- load Python code from outside the platform repository;
- start more than `ACTIVE_LAB_LIMIT` labs concurrently;
- retain state past `bbr destroy`; the state file must be
  shredded, not merely removed.

## 18. First response format

Hermes must begin Phase 0 with only the following
information and must not create resources:

```text
BBR PHASE 0 STARTED — PLAN ONLY

Required inputs present/missing:
- BILLING_ACCOUNT_ID: <present|missing>
- GCP_PROJECT_ID: <present|missing>
- GCP_REGION: <present|missing>
- GCP_ZONE: <present|missing>
- PLATFORM_OPERATOR_LABEL: <present|missing>
- GCP_ORGANIZATION_ID: <present|missing>
- GCP_FOLDER_ID: <present|missing>
- ACTIVE_LAB_LIMIT: <present|missing>
- BUDGET_EUR_EQUIVALENT: <present|missing>
- VPN_ALLOWED_STATIC_CIDRS: <present|missing>
- LAB_OWNER_LABEL: <present|missing>

Proposed project ID:
Proposed region/zone:
Estimated cost (1 lab, scheduled, 14 days):
Estimated cost (2 labs, scheduled, 14 days):
Platform validation status:
Schema validation status:
Pack validation status (smoke-compose, smoke-vm, wordpress-wp2shell):
Resources created: 0

Next action: provide Phase 0 deliverables and wait for APPROVE PHASE 1.
```

## 19. Phase 0 deliverables

The platform must produce, before any `APPROVE PHASE 1`
phrase may be issued:

1. Platform directive — this file.
2. Threat model — `THREAT-MODEL.md`.
3. Architecture diagram — `docs/architecture.svg`.
4. Generic lab-pack schema — `schemas/lab-pack.schema.json`.
5. Generic scenario schema — `schemas/scenario.schema.json`.
6. Execution-driver interface — `schemas/driver-interface.schema.json`.
7. Lifecycle state model — `schemas/lifecycle-state.schema.json` plus the
   state machine implementation skeleton in
   `src/bbr/lifecycle/`.
8. Network-isolation model — `docs/architecture-decisions/ADR-0003-network.md`.
9. Secrets model — `docs/architecture-decisions/ADR-0004-secrets.md`.
10. Terraform module boundaries — `docs/architecture-decisions/ADR-0005-terraform.md`.
11. State and locking model — `docs/architecture-decisions/ADR-0006-state.md`.
12. Evidence format — `schemas/evidence-format.schema.json`.
13. Cost and TTL model — `docs/architecture-decisions/ADR-0007-cost.md`.
14. Acceptance test plan — `tests/acceptance/`.
15. Migration map from the existing WordPress lab —
    `docs/architecture-decisions/ADR-0002-migration.md`.
16. Risks and unresolved decisions — `notes/PHASE-0-RISKS.md`.
17. Complete proposed repository tree — the tree printed by
    `bbr tree` once implemented, and documented inline in
    Section 5 above.
18. Phase 0 report — `notes/PHASE-0-REPORT.md`.
19. Exact Human Gate 0 approval phrase — `APPROVE PHASE 1`.

The Phase 0 design must demonstrate, using the schemas and
interfaces, how all three required packs can be represented
without changing platform-core code.

## 20. Stopping point

Stop at HUMAN GATE 0. Do not create, modify, or delete GCP
resources. Do not run Terraform apply. Do not migrate the
existing WordPress lab. Do not begin implementation until the
exact phrase `APPROVE PHASE 1` is received.

## 21. Separated gates — plan approval vs execute approval

The platform uses two distinct Human Gates per phase. They
must never be conflated.

**`APPROVE PHASE N`** authorises:

- planning of Phase N (reports, schemas, terraform plan,
  validation, cost projections);
- reviewable implementation work in source files;
- any read-only or local-only operation;
- commit and push of in-source changes that do not mutate
  GCP state.

`APPROVE PHASE N` does **not** authorise:

- `terraform apply` or any equivalent GCP-mutating command;
- creation, modification, or deletion of any GCP resource;
- activation of a previously disabled backend.

**`APPROVE PHASE N EXECUTE`** is a separate, explicit phrase.
It authorises only:

- application of the previously reviewed and stored
  `terraform plan` output (typically loaded via
  `terraform apply <planfile>`);
- the GCP mutations that result from that exact plan;
- immediate read-only verification of the created
  resources.

`APPROVE PHASE N EXECUTE` does **not** authorise:

- any change to the plan that has not been re-reviewed;
- any resource outside the reviewed plan;
- any state migration that has not been pre-documented.

For Phase 1 the plan approval phrase is `APPROVE PHASE 1`
(issued 2026-07-25) and the execute approval phrase is
`APPROVE PHASE 1 EXECUTE`. The execute approval has not yet
been issued.

The platform must reject any GCP-mutating operation between
the plan approval and the execute approval, regardless of
operator pressure.
## 22. Phase 2 — Shared Access Plane

Phase 2 creates the Shared Access Plane only. It does
not create lab VMs, per-lab subnets, VPC peering,
Cloud NAT, or any product- or pack-specific resource.

Resource budget for Phase 2 (authoritative after plan):

- exactly one custom-mode VPC `bbr-shared-vpc`
- exactly one control-plane subnet `bbr-bastion-subnet`
- exactly one reserved regional external IPv4
- exactly one bastion service account
- exactly one bastion VM (`e2-micro`, Debian 12)
- exactly one WireGuard ingress firewall (UDP/51820)
- exactly one IAP SSH ingress firewall (TCP/22,
  `35.235.240.0/20`)
- exactly one return route for `10.254.0.0/24`
- three minimal operator IAM bindings
  (`iap.tunnelResourceAccessor`, `compute.osAdminLogin`,
  `iam.serviceAccountUser`)

No Owner, Editor, or Compute Admin roles are added.
The bastion service account has no project-wide roles.

### Phase 2 cost guard

A separate phase-2 incremental monthly cost guard applies:

```
PHASE2_INCREMENTAL_MONTHLY_COST_LIMIT_EUR = 25
```

If the SKU-based monthly projection exceeds €25, the
Phase 2 plan must not be committed or applied. The
projection is documented in `notes/PHASE-2-PLAN.md`.

### Phase 2 SSH policy

- `enable-oslogin = "TRUE"` on the bastion instance.
- `block-project-ssh-keys = "TRUE"` blocks SSH keys in
  project or instance metadata.
- No public TCP/22 rule. SSH is exclusively via IAP TCP
  Forwarding.

### Phase 2 WireGuard key handling

- The server private key is generated locally on the
  bastion VM at first boot (mode 0600, owner root:root).
- The operator's public key is passed to Terraform as the
  `bbr_operator_wg_public_key` variable, embedded into
  the bastion bootstrap via `templatefile()`, and never
  read inside the VM from a file or environment variable.
- The rendered VM bootstrap must NOT reference
  `BBR_WG_OPERATOR_PUBLIC_KEY_FILE`. The VM does not
  read any operator file.
- The rendered VM bootstrap uses `set +x` and
  `unset PS4` before any private-key operation;
  `unset BASH_XTRACEFD` is no longer used.
- The operator's private key never enters Terraform,
  the state file, instance metadata, or logs.

### Phase 2 WireGuard address layout

- Server WireGuard tunnel address: `10.254.0.1/24`
- Operator WireGuard tunnel address: `10.254.0.2/32`
- WireGuard overlay (return route destination): `10.254.0.0/24`
- Bastion VPC subnet: `10.200.0.0/24` (control plane)
- Per-lab subnet pool: `10.200.1.0/24` … `10.200.254.0/24`
  (declared, not allocated by Phase 2)

### Phase 2 IAM scope

- `roles/iap.tunnelResourceAccessor` — project-wide on
  the operator principal.
- `roles/compute.osAdminLogin` — project-wide on the
  operator principal.
- `roles/iam.serviceAccountUser` — scoped via
  `google_service_account_iam_member` to the bastion
  service account `bbr-bastion-sa` only. Future service
  accounts in the project are NOT covered.

### Phase 2 return route

- `google_compute_route.bbr-wg-return` is UNTAGGED and
  applies to every instance in the BBR VPC, including
  future lab VMs.
- It has an explicit `depends_on` on
  `google_compute_instance.bastion`.

### Phase 2 apply gate

The apply gate phrase is `APPROVE PHASE 2 EXECUTE`. The
pre-check list (planfile SHA-256, `git rev-parse HEAD`
against origin/main, resource-count assertion, no
modification of Phase 1 resources, no public SSH rule,
no Lab-VM, no per-lab subnet, no Cloud NAT, no VPC
peering) must all pass before the phrase is honoured.

### Phase 2 image pinning

- The bastion image is referenced by Self-Link:
  `projects/debian-cloud/global/images/debian-12-bookworm-v20260721`
- The Self-Link is resolved at plan time and frozen in
  the plan. Moving-image references (family + data
  source) are forbidden by the repository pattern guard.
- A future change of the image requires an explicit
  commit that updates the Self-Link and a fresh plan.

### Phase 2 operator public key regex

- The accepted regex is exactly:
  `^[A-Za-z0-9+/]{43}=$`
  (43 base64 characters plus the trailing `=`, total
  length 44).
- Any other regex variant is forbidden. The
  `{44}=$` form and other lengths are not accepted and
  must not appear in the platform tree.

The Phase 2 plan file is `/tmp/bbr-phase2-plan.tfplan`.
Only this file is applied; any other file is rejected.

## 23. Phase 3 — Generic Single-Lab Lifecycle

Phase 3 introduces a fully generic per-lab Terraform root, a
deterministic subnet allocator, local runtime state with
advisory locking, and reviewable CLI commands.

Authorization gates:

  - `APPROVE PHASE 3 EXECUTE` authorizes ONLY the reviewed
    create plan. It must specify the plan-file SHA-256 and
    the repository commit.
  - After a live test, a separate destroy plan is produced.
    That destroy plan requires `APPROVE PHASE 3 DESTROY
    EXECUTE` to apply. Destroy is NEVER automatic.
  - Both gates are independent. The create gate alone is not
    sufficient to destroy anything.

The Phase 3 vertical slice is the minimum viable lab lifecycle.
WordPress and other products are deferred to Phase 4.

`PHASE3_SMOKE_CYCLE_LIMIT_EUR = 1`. The CLI refuses to plan a
lab whose projected 8-hour cost exceeds this limit. The current
vertical slice projects ~EUR 0.10 per cycle, well under the
limit.

See `notes/PHASE-3-PLAN.md` for the current reviewable plan,
`docs/architecture-decisions/ADR-0009-lab-lifecycle.md` for the
decisions, and `tests/` for the Phase 3 acceptance tests.

## 24. Phase 3 — v2 hardening

Phase 3 v1 was reviewed and accepted in shape but contained
several execution blockers. The Phase 3 v2 commit resolves:

  - Readiness marker is now part of the Terraform plan via
    `metadata_startup_script` (templatefile). No out-of-plan
    SSH write. `post-create.sh` is read-only.
  - The lab subnet does NOT carry `prevent_destroy`. The
    `APPROVE PHASE 3 DESTROY EXECUTE` phrase remains the
    authoritative gate for destruction.
  - `state/` gitignore now matches only the repo-root runtime
    directory. The source module `src/bbr/state/` is tracked.
  - `PHASE3_SMOKE_CYCLE_LIMIT_EUR = 1.00 EUR` exactly.
  - `bbr create` requires `--plan-file --expected-sha256
    --expected-commit` and verifies HEAD, origin/main, working
    tree, runtime state, backend prefix, plan SHA, plan shape,
    and provider actions.
  - `bbr verify` performs a full read-only verification and
    records lifecycle transitions atomically.
  - `bbr destroy` produces a stored destroy plan and its SHA.

The v1 plan file
`/tmp/bbr-phase3-smoke-create-v1.tfplan`
(SHA-256 `a79483b485673920de796a6f32dfa8b95725b8634f2a163ebc22612bbc216ad4`)
is obsolete and must never be applied. The current reviewable
plan is the v2 plan file generated from the v2 commit.

## 25. Phase 3 — Closeout fixes (v4)

The Phase 3 EXECUTE on the v3 plan completed successfully.
Two attempts to apply the original destroy plan failed and
the plan was retired as OBSOLETE. The CLI was hardened so
that the failure modes are caught before the State is
touched. These decisions are binding for any future plan
or apply.

### 25.1 Credential preflight (mandatory)

Every CLI command that may invoke `terraform apply` MUST
verify `GOOGLE_OAUTH_ACCESS_TOKEN` is set and non-empty
BEFORE the first terraform subprocess runs. Missing or
empty token aborts the command with exit code 18 and a
clear message. The State MUST stay unmutated in this case.

### 25.2 Plan-freshness check (mandatory)

`bbr create` MUST compare the saved plan's recorded
State serial against the current lab State serial
(`terraform state pull`). On mismatch the command aborts
with exit code 19 and instructs the operator to re-plan.
A plan bound to a divergent State cannot be applied.

### 25.3 Destroy plan overwrite protection (mandatory)

`bbr destroy` MUST refuse to silently overwrite an existing
destroy plan whose State serial matches the current State.
Exit code 10 is reserved for this case. The operator MUST
rename the existing plan file to `.OBSOLETE` or advance the
State before producing a fresh plan.

### 25.4 Verify command hardening (mandatory)

`bbr verify` MUST use `gcloud compute firewall-rules list
--format=json` and filter `targetTags` in Python. The
obsolete alias `gcloud compute firewalls list` and the
invalid `targetTags:` filter expression are forbidden in
any executable line of `cmd_verify`. The runtime-state
check MUST fail with exit code 13 when the state is
`PLANNED` but lacks `transition_history`.

### 25.5 Lifecycle state machine (binding)

Lifecycle transitions are written by the CLI commands
themselves, never by a Python helper invoked outside the
CLI surface:

| Command | Transition |
|---|---|
| `bbr plan` | `DEFINED -> VALIDATED -> PLANNED` |
| `bbr verify` | `PLANNED -> CREATED -> BOOTSTRAPPING -> ISOLATED -> READY` |
| `bbr destroy` | `READY -> STOPPED -> DESTROYED` |

The runtime state MUST contain a complete
`transition_history` for the CLI to advance it further.

### 25.6 WireGuard routing/NAT (status)

The WireGuard data-path from the operator to the lab VM
through the bastion tunnel did NOT work in Phase 3
EXECUTE. IAP-tunneled SSH to the same VM succeeded. The
most likely cause is a MASQUERADE rule on the bastion that
rewrites the source of packets leaving `ens4` from the WG
overlay to the bastion's internal IP; the lab firewall
expects `10.254.0.0/24` as the source range.

This is documented as a **working hypothesis only**. No
Foundation change will be made on the basis of this
hypothesis alone. Verification requires packet captures,
`iptables -t nat -L`, and routing-table inspection on the
bastion. The investigation is deferred to Phase 4 and
documented in `notes/PHASE-3-PLAN.md` and
`ADR-0009-lab-lifecycle.md`.

### 25.7 Authorisation gates (closeout)

- The original `APPROVE PHASE 3 DESTROY EXECUTE` against
  plan `/tmp/bbr-smoke-vm-001-destroy.tfplan` (SHA-256
  `a2bbce9a394f735b51acd4ac5ec09a6fc9c0d9ffc2e596b5858353d99a36e272`)
  is **OBSOLETE**. That plan file must never be re-applied.
- A new destroy plan (v2) MUST be generated from the
  current State in a separate planning gate before any
  new `APPROVE PHASE 3 DESTROY EXECUTE` is considered.

### 25.8 What is NOT in this commit

- No new destroy plan was generated.
- No `terraform apply` was attempted.
- No GCP resource was mutated.
- No Foundation resource was modified.

## 26. Phase 4 Implementation

Phase 4.0 implements ADR-0010, ADR-0011 and `notes/PHASE-4-PLAN.md`.
It adds authenticated GCS pull, Minisign/SHA-256/manifest verification,
runtime-only secrets, atomic state extensions, lifecycle failure/rollback,
the `wordpress-smoke` pack, and bootstrap egress persistent until destroy.

Implementation is complete in code, schemas, Terraform module,
documentation and tests. Artifact publication and live execution remain
behind the EXECUTE gate; no GCP resource was changed.

## 27. Phase 4 Pre-Execute-Korrektur (Backend + Konsistenz)

Phase-4-Pre-Execute-Korrektur schließt drei Punkte aus dem ersten
Phase-4-Create-Plan-Review.

### 27.1 Backend-Konfiguration (Blocker A)

Terraform initialisiert Backends VOR der Variablenauswertung. Daher
darf der Backend-Block in `terraform/lab/main.tf` KEINE Variablen-
Referenzen enthalten. Der Phase-3-Mechanismus (partial configuration
via `terraform init -backend-config=bucket=... -backend-config=prefix=...`)
bleibt unverändert und ist die einzige korrekte Lösung.

Der fehlerhafte Versuch, den Backend-Block mit Variablen-Interpolation
in HCL zu deklarieren (`bucket = "bbr-state-${var.gcp_project_id}"`,
`prefix = "labs/${var.lab_id}"`), wurde rückgängig gemacht.

### 27.2 Bootstrap-Egress instanziiert (Blocker B)

Das `bootstrap-egress`-Terraform-Modul existierte seit Phase-4.0,
wurde aber nicht im Lab-Root instanziiert. Dadurch fehlte die
priority-1000-EGRESS-Firewall im Plan; die VM konnte im
Bootstrap-Zustand keinen GCS-Pull machen. Nach der Korrektur wird
das Modul instanziiert und der Plan enthält eine zusätzliche
Ressource. Default-Deny-Egress (priority 65000) bleibt aktiv.

### 27.3 Ressourcenanzahl 7 → 8

Lab-Ressourcen pro Plan: 7 (Phase 3) + 1 (Bootstrap-Egress) = **8**.

### 27.4 Tests

- `tests/acceptance/test_phase3_terraform.py:test_lab_root_backend_is_partial_configuration`
  bestätigt explizit, dass kein Backend-Block mit Variablen existiert.
- `tests/acceptance/test_bootstrap_egress_firewall.py:test_module_instantiated_in_lab_main_tf`
  bestätigt die Modul-Instanziierung.

### 27.5 Plan v3

- Planpfad: `/tmp/bbr-phase4-wordpress-create-v3.tfplan`
- Planform: **9 add / 0 change / 0 destroy**

### 27.6 Phase 4A Runtime-, Trust- und IAM-Korrektur

Der Runtime-Stack wird vollständig offline im Release-Artefakt
ausgeliefert; Paketmanager- und Internetzugriffe auf der Lab-VM bleiben
verboten. Minisign 0.12 wird einmalig in das feste Custom Image
`projects/your-lab-name-your-researcher-handle/global/images/bbr-debian-12-bootstrap-tools-20260727-v2`
gebacken. Der Phase-4-VM wird der GCE Default Service Account attached,
der am gehärteten Bootstrap-Bucket eine bucket-scoped
`roles/storage.objectViewer`-Rolle besitzt. Die Lab-Runtime-SA bleibt
als Plan-Ressource bestehen. Lab-Planform bleibt 8/0/0; Bucket und
Bucket-IAM gehören zur einmaligen Release-Infrastruktur.
