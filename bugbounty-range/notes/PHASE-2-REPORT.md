# Phase 2 — BugBountyRange Shared Access Plane Closeout Report

This report records the Phase 2 closeout for the
BugBountyRange platform. Phase 2 created the Shared
Access Plane (VPC, control-plane subnet, bastion, IAM)
on top of the Phase 1 foundation. No lab VMs, per-lab
subnets, VPC peering, Cloud NAT, or product-/pack-
specific resources were created.

The Phase 2 plan was authorised as
`APPROVE PHASE 2 EXECUTE` against exactly one plan file
with a single, verified SHA-256. This report documents
the apply, the post-apply state, the end-to-end
WireGuard sanity checks, and the idempotency
verification.

## 1. Authoritative plan file applied

- Source file: `/tmp/bbr-phase2-plan-v5.tfplan`
- Canonical copy: `/tmp/bbr-phase2-plan.tfplan`
- SHA-256: `270b23504e8456b87ecea04e4f73f624da9c08c426e65f03820348f9f6d10f5b`
- Repository commit at apply time: `dfe082123bc7dec71520e071b9238f4f08adb003`

Pre-apply gate checks (all PASS):
- HEAD == `dfe082123bc7dec71520e071b9238f4f08adb003`
- `origin/main` == `dfe082123bc7dec71520e071b9238f4f08adb003`
- `git status --porcelain` empty
- Plan file SHA-256 matched the authorised value
- Canonical copy `/tmp/bbr-phase2-plan.tfplan` byte-identical to v5

## 2. Apply result

```
Apply complete! Resources: 11 added, 0 changed, 0 destroyed.
```

The apply produced no errors and no drift. The phase 1
foundation (10 resources, project, billing budget, state
bucket, 7 project services) was untouched by the apply.

## 3. Final state inventory

The Terraform state contains 21 resources:

Phase 1 (10, no-op during apply):
- `google_billing_budget.platform`
- `google_project.bbr`
- `google_project_service.foundation["billingbudgets.googleapis.com"]`
- `google_project_service.foundation["cloudbilling.googleapis.com"]`
- `google_project_service.foundation["cloudresourcemanager.googleapis.com"]`
- `google_project_service.foundation["compute.googleapis.com"]`
- `google_project_service.foundation["iam.googleapis.com"]`
- `google_project_service.foundation["iap.googleapis.com"]`
- `google_project_service.foundation["storage.googleapis.com"]`
- `google_storage_bucket.state`

Phase 2 (11, added):
- `google_compute_network.platform` — `bbr-shared-vpc` (custom, REGIONAL, MTU 1460)
- `google_compute_subnetwork.control_plane` — `bbr-bastion-subnet`, `10.200.0.0/24`, Private Google Access
- `google_compute_address.bastion` — `bbr-bastion-eip`, regional EXTERNAL STANDARD
- `google_service_account.bastion` — `bbr-bastion-sa` (no project-wide roles)
- `google_compute_instance.bastion` — `e2-micro`, Debian 12 (pinned), shielded, OS Login, block-project-ssh-keys
- `google_compute_firewall.bastion_iap` — TCP/22 from `35.235.240.0/20`, target tag `ssh-iap`
- `google_compute_firewall.bastion_wireguard` — UDP/51820 from operator CIDRs, target tag `bbr-bastion`
- `google_compute_route.wireguard_return` — `10.254.0.0/24` via bastion internal IP, untagged
- `google_project_iam_member.operator_iap_tunnel` — `roles/iap.tunnelResourceAccessor` (project-wide)
- `google_project_iam_member.operator_os_login` — `roles/compute.osAdminLogin` (project-wide)
- `google_service_account_iam_member.operator_sa_user` — `roles/iam.serviceAccountUser` (scoped to `bbr-bastion-sa` only)

## 4. External bastion IP

The reserved regional external IPv4 is `35.207.110.97`
(network tier STANDARD, in use by the bastion).
This is reachable from operator CIDRs `91.99.86.45/32`
and `178.104.89.75/32` for UDP/51820 (WireGuard) only.

## 5. Bastion WireGuard status

The bastion generated its server private key on first
boot (mode 0600, owner root:root, locally in
`/etc/wireguard/wg0.key`). The server public key was
read out only over an authenticated IAP / OS-Login SSH
session, never via Serial Console or startup-script
logs.

Service and key checks (all PASS):

- `systemctl is-active wg-quick@wg0` -> active
- `/etc/wireguard/wg0.key` mode 600, owner root:root, size > 0
- `/etc/wireguard/wg0.conf` mode 600, owner root:root
- `/etc/wireguard/wg0.pub` size > 0
- `wg show wg0` shows the configured Interface Address
  and the Hermes peer with `allowed ips: 10.254.0.2/32`
- `ss -uln` shows WireGuard listening on UDP/51820
  (both `0.0.0.0:51820` and `[::]:51820`)

Bastion server public key:
  `kA2iGM2sdvvalf1Vc6HT6zwf3MzN/RIazXWNSzK9bkA=`

Bastion server public key SHA-256 fingerprint:
  `b515abc66f47429d43f65a7b82c351b55a36d7865036fb937a2be5c31cb830dd`

The bastion WireGuard peer entry uses the Hermes
operator public key derived locally from the operator's
existing WireGuard private key. The peer public key
matches the value derived with wg pubkey. The Hermes
operator private key was never read by Terraform or GCP.

## 6. IAP / OS-Login test

IAP-tunnelled SSH to the bastion succeeded under the
operator principal `user:your-contact@example.com` via
OS Login. No SSH keys were stored in project or
instance metadata; `block-project-ssh-keys = TRUE`
was honoured. The IAP firewall rule
`bbr-bastion-iap-ssh` allows TCP/22 only from
`35.235.240.0/20` (the Google IAP range), and no
public TCP/22 rule exists.

## 7. WireGuard service test

`wg-quick@wg0` is active. The interface has:

```
interface: wg0
  public key: kA2iGM2sdvvalf1Vc6HT6zwf3MzN/RIazXWNSzK9bkA=
  private key: (hidden)
  listening port: 51820

peer: <Hermes operator public key>
  allowed ips: 10.254.0.2/32
```

The interface address and the operator AllowedIPs match
the architecture exactly:

- Server Interface Address: `10.254.0.1/24`
- Operator Peer AllowedIPs: `10.254.0.2/32`
- Overlay (return route destination): `10.254.0.0/24`

## 8. Firewall and route verification

| Resource | Status |
|---|---|
| `bbr-bastion-iap-ssh` | exists, TCP/22, source `35.235.240.0/20`, target tag `ssh-iap` |
| `bbr-bastion-wireguard` | exists, UDP/51820, sources `91.99.86.45/32`, `178.104.89.75/32`, target tag `bbr-bastion` |
| `bbr-wg-return` | exists, dest `10.254.0.0/24`, next-hop `10.200.0.10`, tags unset (untagged, applies to the whole VPC), priority 100 |

No Cloud NAT, no VPC Peering, no per-lab subnet or
per-lab VM were created. The platform VPC and the
control-plane subnet are present; lab subnets are
allocated dynamically by `bbr create` in later phases
and do not exist yet.

## 9. Secret scan

| Scan target | Result |
|---|---|
| `BEGIN (RSA \|EC \|OPENSSH \|)PRIVATE KEY` in `terraform/` | 0 hits |
| `BEGIN ... PRIVATE KEY` in `notes/` | 0 hits |
| operator API-token assignments in `platform/` | 0 hits |
| Concrete operator key filename literals in the platform tree | 0 hits |
| `BBR_WG_PRIVATE_KEY_FILE` in `terraform/`, `src/`, `scripts/`, `tools/` | 0 hits |
| Concrete Hermes / private secret paths in `platform/` | 0 hits |
| `wg genkey` occurrences in `platform/your-lab-name/` | 1 hit, in the reviewed bastion bootstrap template |
| Bastion Serial Console output | no private-key material, no `wg genkey` output |
| Terraform state on disk (GCS) | no `BEGIN ... PRIVATE KEY`, no Hermes paths |

The single `wg genkey` occurrence lives in the bastion
bootstrap template and is the controlled, expected
server-key generation. The repository pattern guard
enforces exactly this configuration:

The current repository-wide Phase 2 WireGuard pattern
guard completed successfully. It scans notes and docs
for private-key block markers, concrete operator key
filenames, and operator secret-path segments.

## 10. Idempotency

After the apply, a second plan was produced with the
real Hermes operator public key. It was locally derived
from the operator's existing WireGuard private key
using wg pubkey; Terraform never read the private key.

- Plan file: `/tmp/bbr-phase2-idempotency.tfplan`
- SHA-256: `6f24d0ee84599ed7ddc7c0f67b0581114ab0c36537e7ed19b9c41e0491bb8992`
- `terraform plan -detailed-exitcode` exit code: 0
- Output: `No changes. Your infrastructure matches the configuration.`

The infrastructure is fully idempotent. Re-running the
apply against the canonical plan file would be a no-op.

## 11. Cost notes

Phase 2 SKU-based monthly projection (no free tier):

| Posten | USD / Monat |
|---|---|
| e2-micro (europe-west3, 730h) | $5.85 |
| pd-standard 10 GB | $0.40 |
| External IPv4 regional STANDARD | $7.52 |
| Network WireGuard (konservativ) | $1.00 |
| **Summe Phase-2-Inkrement** | **$14.77 ≈ €13.59** |

This is below the Phase 2 cost guard of
`PHASE2_INCREMENTAL_MONTHLY_COST_LIMIT_EUR = 25`.

The Phase 1 budget alert (`BugBountyRange monthly alert
budget`) of `245 EUR / month` remains the global GCP
budget and is unchanged by Phase 2.

## 12. Deviations

None. All ten Phase-1 resources were untouched. The
eleven Phase-2 resources match the plan exactly. The
bastion image is pinned by Self-Link (no family). The
bastion access_config and the reserved address share
network tier STANDARD. The return route is untagged.
The IAM binding for `roles/iam.serviceAccountUser` is
scoped via `google_service_account_iam_member` to the
bastion service account only.

## 13. Next phase

Phase 3 (lab lifecycle, per-lab subnet allocation,
WordPress pack bring-up) is not started in this report.
The shared access plane is ready. Phase 3 begins only
after an explicit `APPROVE PHASE 3` authorisation.
