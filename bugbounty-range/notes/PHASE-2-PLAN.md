# BugBountyRange Phase 2 — Shared Access Plane Plan

**Date:** 2026-07-26 (Europe/Berlin)
**Operator:** your-researcher-handle
**Remote HEAD at start:** `dbc30bf666d0a5120c9c6ae06eca99ede0f79a60`
**Tag:** `bbr-phase1-closed` (Phase 1 closed)

---

## 1. Scope

Phase 2 creates the **Shared Access Plane**: the minimal
network and compute layer needed to access per-lab VMs
securely. It explicitly does **not** create lab VMs, lab
subnets, VPC peering, Cloud NAT, or any product- or
pack-specific resource.

Phase 2 resource set:

- 1× `google_compute_network` — custom-mode VPC
- 1× `google_compute_subnetwork` — control-plane subnet
- 1× `google_compute_address` — reserved regional IPv4
- 1× `google_service_account` — dedicated bastion SA
- 1× `google_compute_instance` — bastion VM (e2-micro)
- 1× `google_compute_firewall` — WireGuard UDP ingress
- 1× `google_compute_firewall` — IAP SSH ingress
- 1× `google_compute_route` — return route to overlay
- 3× `google_project_iam_member` — minimal operator
  bindings (iap.tunnelResourceAccessor, compute.osAdminLogin,
  iam.serviceAccountUser)

**Total:** 11 resources, **0 changes**, **0 destroys**.

## 2. Network design

| Layer | Name | CIDR | Notes |
|---|---|---|---|
| VPC | `bbr-shared-vpc` | `10.200.0.0/16` | Custom mode, regional routing, MTU 1460 |
| Subnet | `bbr-bastion-subnet` | `10.200.0.0/24` | Private Google Access enabled |
| Bastion IP | internal | `10.200.0.10` | fixed internal IPv4 |
| Bastion IP | external | reserved regional | attached to bastion NIC |
| Per-lab pool | (declared, not allocated) | `10.200.1.0/24` … `10.200.254.0/24` | dynamic via `bbr create` |
| WireGuard overlay | route only | `10.254.0.0/24` | routed via bastion |

## 3. Bastion design

| Property | Value |
|---|---|
| Name | `bbr-bastion` |
| Zone | `europe-west3-a` |
| Machine type | `e2-micro` |
| Image | `debian-12-bookworm-v20260721` (pinned Self-Link at plan time) |
| Boot disk | 10 GB `pd-standard` |
| `can_ip_forward` | `true` |
| Service account | `bbr-bastion-sa` (dedicated; no project-wide roles) |
| Shielded VM | secure boot, vTPM, integrity monitoring all enabled |
| OS Login | enabled on the instance, blocked project-wide SSH keys |
| IAP TCP Forwarding | source range `35.235.240.0/20` |
| Public SSH | none |

## 4. WireGuard bootstrap

- Server private key generated on first boot inside the
  bastion VM, mode `0600`, owner `root:root`,
  **only when `/etc/wireguard/wg0.key` does not exist**
  (idempotent).
- Operator public key passed to Terraform as
  `bbr_operator_wg_public_key`, validated as a
  WireGuard public key, and embedded directly into the
  bastion bootstrap via `templatefile()`.
- The rendered VM bootstrap must NOT reference
  `BBR_WG_OPERATOR_PUBLIC_KEY_FILE`. The VM does not
  read any operator file.
- The rendered VM bootstrap uses `set +x` and
  `unset PS4` before any private-key operation;
  `unset BASH_XTRACEFD` is removed.
- Operator private key never enters Terraform, state,
  metadata, or logs.
- Listen port: `51820/UDP`.
- Server tunnel address: `10.254.0.1/24`.
- Operator tunnel address: `10.254.0.2/32`.
- Overlay return-route destination: `10.254.0.0/24`.

### 4.1 Bastion image pinning

- The bastion image is referenced by Self-Link:
  `projects/debian-cloud/global/images/debian-12-bookworm-v20260721`
- The Self-Link is resolved at plan time and frozen in
  the plan. Moving-image references (family + data
  source) are forbidden by the repository pattern guard.

### 4.2 Operator public key validation

- The accepted regex is exactly
  `^[A-Za-z0-9+/]{43}=$` (43 base64 characters plus
  the trailing `=`, total length 44).
- The `44}=$` form and other lengths are not accepted.


## 5. Firewall rules

### 5.1 WireGuard ingress

- direction: `INGRESS`
- protocol: `udp`
- port: `51820`
- source_ranges: `var.vpn_allowed_static_cidrs`
- target_tags: `["bbr-bastion"]`

### 5.2 IAP SSH ingress

- direction: `INGRESS`
- protocol: `tcp`
- port: `22`
- source_ranges: `["35.235.240.0/20"]`
- target_tags: `["ssh-iap"]`

No rule for TCP/22 from `0.0.0.0/0` or from operator CIDRs.

### 5.3 WireGuard return route (untagged)

- `google_compute_route.bbr-wg-return` covers
  `10.254.0.0/24` via bastion internal IP.
- The route is UNTAGGED and applies to every instance
  in the BBR VPC, including future lab VMs.
- It has an explicit `depends_on` on
  `google_compute_instance.bastion`.

## 6. IAM additions

Read-only pre-check (2026-07-26):
- Operator already has `roles/owner` at project level
- The following minimal bindings are added so Phase 2 works
  even if the project-level owner role is revoked later:

| Role | Member | Justification |
|---|---|---|
| `roles/iap.tunnelResourceAccessor` | `var.bbr_operator_principal` | IAP SSH access to the bastion |
| `roles/compute.osAdminLogin` | `var.bbr_operator_principal` | OS Login SSH as root-equivalent |
| `roles/iam.serviceAccountUser` | `var.bbr_operator_principal` | Run sessions as bastion SA when needed. Bound via `google_service_account_iam_member` to `bbr-bastion-sa` ONLY, not project-wide. |

No Owner, Editor, or Compute Admin roles added.

## 7. Cost projection (Phase 2 incremental)

| Item | USD/month | EUR/month (≈ 0.92) |
|---|---|---|
| e2-micro europe-west3 (730h) | $5.85 | €5.38 |
| pd-standard 10 GB | $0.40 | €0.37 |
| External IPv4 (regional, in use) | $7.52 | €6.92 |
| Network (WireGuard, conservative) | $1.00 | €0.92 |
| **Phase 2 incremental total** | **$14.77** | **≈ €13.59** |
| **Phase-2-Plan-Guard limit** | — | **€25.00** |
| **Status** | — | **PASSED (13.59 < 25.00)** |

No Free Tier is assumed for europe-west3. The existing
Phase 1 budget of 245 EUR/month is unchanged and remains
the global GCP alert cap.

## 8. Variables added in Phase 2

- `bbr_operator_principal` (default
  `user:your-contact@example.com`)
- `bbr_operator_wg_public_key` (default null, sensitive).
  Validated as a WireGuard public key
  (`^[A-Za-z0-9+/]{43}=$`). Embedded directly into the
  bastion bootstrap by Terraform via `templatefile()`.

## 9. Outputs added in Phase 2

- `vpc_self_link`
- `control_plane_subnet_self_link`
- `bastion_name`
- `bastion_internal_ip`
- `bastion_external_ip`
- `bastion_service_account_email`
- `wireguard_listen_port`
- `iap_ssh_source_range`
- `wireguard_allowed_source_cidrs` (sensitive)

## 10. Plan assertion summary

| Assertion | Result |
|---|---|
| Plan output: `11 to add, 0 to change, 0 to destroy` | PASS |
| 10 Phase-1 resources unmodified | PASS |
| No Lab-VM, no per-lab subnet | PASS |
| No Cloud NAT | PASS |
| No VPC Peering | PASS |
| No public SSH (TCP/22 from 0.0.0.0/0) | PASS |
| Exactly one external IPv4 | PASS |
| Exactly one bastion VM | PASS |
| Exactly one WireGuard ingress rule | PASS |
| Exactly one IAP SSH rule | PASS |
| No private key in Terraform, state, metadata, or logs | PASS |
| No service-account-key resource | PASS |
| Phase-1-Plan-Guard: incremental cost < €25/month | PASS |

## 11. Files changed in Phase 2

- `terraform/foundation/network.tf` (locals + VPC + subnet)
- `terraform/foundation/bastion.tf` (address + SA + VM + IAM)
- `terraform/foundation/firewall.tf` (2 firewalls + 1 route)
- `terraform/foundation/variables.tf` (2 new variables)
- `terraform/foundation/outputs.tf` (9 new outputs)
- `terraform/foundation/templates/bastion-startup.sh.tftpl`
  (new file, bootstrap script template)

## 12. Next required human phrase

```
APPROVE PHASE 2 EXECUTE
```

This phrase is not yet issued. No `terraform apply` runs
without it.

Plan-file evolution:
  `/tmp/bbr-phase2-plan.tfplan` (initial, obsolete)
    SHA-256 4f3d58a19d5beb12a0263580c2ac16f885473d86d72e8304fab19b8e30bb17c1
  `/tmp/bbr-phase2-plan-v2.tfplan` (public-key path + SA-scoped IAM, obsolete)
  `/tmp/bbr-phase2-plan-v3.tfplan` (current: network_tier match,
    WireGuard server address consolidation to 10.254.0.1/24, and
    44-char key validation)
    SHA-256 7e4831412c26d5239abfb4ee4c49ae3b209b17605632ccf74db949da75adc284

Only the v3 plan file may be applied after the APPROVE
phrase.
