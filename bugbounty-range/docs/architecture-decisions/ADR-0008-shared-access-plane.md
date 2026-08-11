# ADR-0008 — Phase 2 Shared Access Plane

- Status: proposed (Phase 2 plan approved; apply pending)
- Date: 2026-07-26 (Europe/Berlin)
- Operator: your-researcher-handle
- Supersedes: (none)
- Related: ADR-0001 (Phase 0 platform), ADR-0004 (secrets),
  Phase-1-Closeout Report, Phase-2-Plan

## Context

Phase 1 created the project, the alert budget, the state
bucket, and the API enablement. None of these resources
allow the operator to actually reach a VM. Phase 2 closes
that gap by introducing a small, hardened bastion with
two access paths:

1. IAP TCP Forwarding for SSH (no public TCP/22)
2. WireGuard for overlay-mesh access (UDP 51820)

Phase 2 must be a Shared Access Plane only. No lab VMs,
no per-lab subnets, no VPC peering, no Cloud NAT.

## Decision

The Phase 2 Shared Access Plane consists of exactly:

- 1 custom-mode VPC: `bbr-shared-vpc` (`10.200.0.0/16`,
  regional routing, MTU 1460)
- 1 control-plane subnet: `bbr-bastion-subnet`
  (`10.200.0.0/24`, Private Google Access)
- 1 reserved regional external IPv4 attached to the
  bastion NIC
- 1 dedicated bastion service account
  (`bbr-bastion-sa`) with no project-wide roles
- 1 bastion VM (`bbr-bastion`, e2-micro, Debian 12 image
  pinned at plan time to its Self-Link)
- 1 WireGuard ingress firewall (UDP/51820, source CIDs
  from `var.vpn_allowed_static_cidrs`)
- 1 IAP ingress firewall (TCP/22, source range
  `35.235.240.0/20`)
- 1 return route (`10.254.0.0/24` via bastion internal IP)
- 3 IAM member bindings for the operator principal
  (`iap.tunnelResourceAccessor`, `compute.osAdminLogin`,
  `iam.serviceAccountUser`)

## SSH access policy

- OS Login is enabled on the bastion instance
  (`enable-oslogin = "TRUE"`).
- `block-project-ssh-keys = "TRUE"` blocks SSH keys in
  project or instance metadata.
- Public TCP/22 is **never** opened. SSH reaches the
  bastion only via IAP TCP Forwarding
  (`gcloud compute ssh --tunnel-through-iap`).

## WireGuard key handling

- The server private key is generated **locally on the
  bastion VM** at first boot, mode `0600`, owner
  `root:root`. It never enters Terraform, the Terraform
  state, instance metadata, or Compute Engine console
  output.
- The operator's public key is read by Terraform as the
  `bbr_operator_wg_public_key` variable, validated as a
  WireGuard public key (`^[A-Za-z0-9+/]{43}=$` — exactly
  44 characters, 43 base64 plus the trailing '='), and
  embedded directly into the bastion bootstrap via
  `templatefile()`.
- The rendered VM bootstrap does NOT reference
  `BBR_WG_OPERATOR_PUBLIC_KEY_FILE`. The VM does not
  read any operator file at runtime.
- The rendered VM bootstrap uses `set +x` and
  `unset PS4` before any private-key operation.
- The operator's private key never enters Terraform,
  the state file, instance metadata, or logs.

## Bastion image pinning

- The bastion image is referenced by Self-Link:
  `projects/debian-cloud/global/images/debian-12-bookworm-v20260721`
- The image is resolved at plan time and never refreshed at
  apply time. Moving-image references (family + data source)
  are forbidden by the repository pattern guard.

## WireGuard address layout

- Server tunnel address: `10.254.0.1/24`
- Operator tunnel address: `10.254.0.2/32`
- Overlay return-route destination: `10.254.0.0/24`

## IAM scope

- `roles/iap.tunnelResourceAccessor` and
  `roles/compute.osAdminLogin` are project-wide on the
  operator principal.
- `roles/iam.serviceAccountUser` is bound via
  `google_service_account_iam_member` to the bastion
  service account `bbr-bastion-sa` only. Future service
  accounts are NOT covered.

## Return route

- `google_compute_route.bbr-wg-return` is UNTAGGED and
  applies to every instance in the BBR VPC, including
  future lab VMs.
- It has an explicit `depends_on` on
  `google_compute_instance.bastion`.

## Alternatives considered

- **Allow public TCP/22**: rejected. IAP is sufficient and
  removes an entire class of risk.
- **Use the Compute Engine default service account on the
  bastion**: rejected. The default SA carries more
  scopes than necessary. A dedicated empty SA is safer.
- **Generate the WireGuard key in Terraform**: rejected.
  Private material must not enter the state file or any
  Terraform output.
- **Open per-lab subnets in Phase 2**: rejected. Per-lab
  subnets are dynamic; Phase 2 reserves the CIDR range
  only.

## Cost consequences

Phase 2 incremental cost: ≈ €13.59/month (e2-micro +
10 GB pd-standard + reserved regional IPv4 + conservative
network egress). The Phase-2-Plan-Guard limit of €25/month
is satisfied. The existing Phase 1 budget of €245/month
remains unchanged and continues to act as the global alert
cap (not a hard stop).

## Consequences

- Future phases (`bbr create <pack>`) will allocate
  per-lab subnets inside the `10.200.1.0/24` …
  `10.200.254.0/24` pool.
- The WireGuard return route makes the bastion the single
  next hop for overlay traffic; per-lab VMs route back
  through the bastion.
- The Phase 1 closeout state (GCS-backed, idempotent)
  remains authoritative; the Phase 2 apply must not
  modify any of the 10 Phase 1 resources.