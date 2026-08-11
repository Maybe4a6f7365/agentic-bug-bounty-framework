# ADR-0005 — Terraform module boundaries

## Status

Accepted, 2026-07-25.

## Context

The platform needs a Terraform layout that:

- Provisions one shared access VPC, one bastion, one state
  bucket, and one billing budget.
- Provisions per-lab network segments, compute nodes,
  snapshot policies, and shutdown schedules.
- Contains no product-specific code (no WordPress, no
  GitLab, no Nginx, no Java).
- Is reviewable through `terraform plan`.
- Supports the active-lab cap of 1 by default, 2 by hard
  cap.
- Supports the secrets model in ADR-0004.
- Supports the network isolation model in ADR-0003.

## Decision

### Top-level layout

```
terraform/
├── foundation/                # One project, one shared VPC, one
│   │                          # bastion, one state bucket, one
│   │                          # billing budget. Created in
│   │                          # Phase 1, applied once.
│   ├── project.tf             # The dedicated GCP project.
│   ├── billing.tf             # The 150 EUR-equivalent budget.
│   ├── network.tf             # The shared access VPC.
│   ├── bastion.tf             # The single bastion VM.
│   ├── firewall.tf            # The bastion ingress firewall.
│   ├── state-bucket.tf        # The runtime state bucket.
│   ├── providers.tf           # Terraform + provider config.
│   └── outputs.tf
└── modules/
    ├── network/               # Per-lab subnet, routing, SA.
    ├── compute-node/          # Generic VM module.
    ├── snapshot/              # Application-consistent snapshot
    │                          # policy.
    └── shutdown/              # Daily 02:00 Europe/Berlin stop
                               # schedule.
```

The platform consumes the foundation as a single Terraform
root module. It consumes the modules as Terraform modules
keyed by lab.

### Module boundaries

Each module under `terraform/modules/` is generic. The
network module takes a `lab_id` and a `subnet_cidr_block`
and returns a subnet. The compute-node module takes a
`node_id`, a `driver_id`, a `base_image_digest_or_family`,
a `machine_type`, a `disk_type`, a `disk_size`, and an
optional `driver_payload` (which is passed through to the
driver but not interpreted by the module). The module
returns a private IP and a self-link.

The snapshot module takes a `lab_id` and a list of
`node_ids` and creates one snapshot schedule per node,
plus the hook entries the driver will use to flush state.
The shutdown module attaches a daily 02:00 Europe/Berlin
stop schedule.

No module reads product-specific variables. No module
contains a default value that names a product.

### Driving Terraform from Python

The control plane wraps `terraform plan` and
`terraform apply` for every state transition. It never
calls `terraform apply` outside an approved phase. The
control plane reads `terraform output` to record the
private IPs into the lab state.

### State backend

The foundation creates a private GCS bucket with:

- uniform bucket-level access;
- public access prevention enforced;
- object versioning enabled;
- lifecycle cleanup for obsolete non-current state versions
  after 30 days;
- no anonymous principals.

The lab state is stored in the same bucket, keyed by
`<lab-id>.tfstate`.

### Idempotency and review

Every Terraform change is reviewable through `terraform
plan`. The control plane surfaces the plan summary in
`bbr plan` and before every `bbr apply`. The plan must
contain no surprises: only the resources the lab pack
declared, no pre-existing unrelated resources, no out-of-
scope modifications.

## Consequences

- Adding a new product requires zero Terraform changes.
- Re-applying the foundation is idempotent.
- The control plane can preview every lab change before
  applying it.
- A misbehaving pack cannot trick Terraform into deleting
  foundation resources because the foundation root module
  is independent of the per-lab root module.

## Alternatives considered

- **One root module for everything.** Rejected because it
  would conflate the foundation lifetime with per-lab
  lifetimes.
- **Pulumi / Crossplane.** Rejected because Terraform is
  the operator's declared toolchain and the platform is
  not in a position to introduce a new IaC layer.
- **Terraform Cloud / Atlantis.** Rejected because the
  platform does not depend on a SaaS that cannot be
  audited.