# Phase 3 Plan — Generic Single-Lab Lifecycle (hardened v2)

Phase 3 delivers a fully generic, reproducible lifecycle for
exactly one small raw-vm smoke lab. Phase 3 v2 hardens the
lifecycle execution gates after the v1 review.

The Phase 3 v1 plan file
`/tmp/bbr-phase3-smoke-create-v1.tfplan` (SHA-256
`a79483b485673920de796a6f32dfa8b95725b8634f2a163ebc22612bbc216ad4`)
is **obsolete** and must never be applied.

## Scope (in)

- `packs/smoke-vm/manifest.json` with one raw-vm node,
  default-deny egress, no external IP, pinned image self-link
- `schema/lab-pack.schema.json` extended for `base_image.self_link`
- Independent `terraform/lab/` root that reads foundation via
  `terraform_remote_state`
- `modules/network` (subnet + service account + scoped IAM, no
  `prevent_destroy` on the lab subnet)
- `modules/compute-node` (instance + 3 firewalls: WG-admin,
  IAP-SSH, egress-deny) — no `access_config`, no external IPv4,
  `can_ip_forward = false`, `network_ip = var.internal_ip`
- The VM's readiness marker is created by a Terraform-rendered
  `metadata_startup_script` (templatefile) embedded in the plan.
  The plan is therefore the SOLE source of truth for the
  bootstrap behaviour.
- `post-create.sh` is now strictly read-only. It only checks
  that the marker exists via IAP-tunneled SSH; it does NOT
  write anything.
- `src/bbr/network/allocator.py`: deterministic /24 allocator
- `src/bbr/lifecycle/state_machine.py`: explicit transition
  table
- `src/bbr/state/locking.py`: fcntl advisory lock
- `src/bbr/pack_validation.py`: schema + node-ref + cost-limit
  + ttl + image-self-link validation; default cost guard
  `PHASE3_SMOKE_CYCLE_LIMIT_EUR = 1.00` (NOT 2.00).
- `src/bbr/cli.py`: `validate`, `plan`, `create`, `verify`,
  `list`, `destroy` (last three are reviewable / read-only).

## Scope (out)

- WordPress (Phase 4, after a controlled bootstrap path)
- Docker Compose drivers
- External image / package downloads in lab VMs
- Cloud NAT
- External IPs for lab VMs
- Snapshots, diff, scenarios, multiple active labs
- Direct changes to the 21 foundation resources

## Reference Lab

- `pack_id = smoke-vm`
- `lab_id = smoke-vm-001`
- subnet `10.200.1.0/24`, internal IP `10.200.1.10` (fixed
  in the pack, enforced by the CLI)
- region `europe-west3`, zone `europe-west3-a`
- machine `e2-micro`, 10 GB `pd-standard`
- image `projects/debian-cloud/global/images/debian-12-bookworm-v20260721`
  (pinned Self-Link, no moving family)
- TTL 8h, idle 30m

## v1 vs v2 corrections

| Concern | v1 | v2 |
|---|---|---|
| Readiness marker | written by `post-create.sh` SSH write (out-of-plan mutation) | written by `metadata_startup_script` inside the Terraform plan |
| Internal IP | optional default | fixed at `10.200.1.10`, validated |
| Lab subnet | `prevent_destroy = true` | `prevent_destroy` removed; explicit destroy gate applies |
| `state/` | `state/` matched and ignored the source module | `/state/` matches only the repo-root runtime directory |
| Cost guard | `PHASE3_SMOKE_CYCLE_LIMIT_EUR * 2 = 2.00 EUR` | exactly `PHASE3_SMOKE_CYCLE_LIMIT_EUR = 1.00 EUR` |
| `bbr plan` | partial implementation | full pipeline (init, validate, plan, show -json, SHA, atomic state write) |
| `bbr create` | required `--plan-file` and `--expected-sha256` | additionally requires `--expected-commit`; refuses to apply without all three |
| `bbr verify` | stub | full read-only verification of VM, IP, marker, firewalls, lifecycle |
| `bbr destroy` | stub | produces a real stored destroy plan and SHA |

## Plan

The v2 plan is generated from the committed Phase-3 code on
top of HEAD and stored at
`/tmp/bbr-phase3-smoke-create-v3.tfplan`.

Expected:
- `Plan: 7 to add, 0 to change, 0 to destroy`
- exactly the seven expected resource addresses
- internal IP exactly `10.200.1.10`
- `metadata_startup_script` embedded in the instance
- `can_ip_forward = false`, no `access_config`
- the three firewalls (WG-admin, IAP-SSH, egress-deny)
- no `prevent_destroy` on the lab subnet
- no foundation resources managed by the lab root
- no NAT, no VPC peering, no public ingress

## Cost projection (formula and result)

Variables:
- `e2-micro` hourly USD rate: `R_MACHINE = 0.00838 USD/h`
- 10 GB `pd-standard` monthly USD rate: `R_DISK = 0.40 USD/month`
- 1 month = 730 hours
- max lifetime `T = 8h`

Per-cycle cost (one create + 8h lifecycle + destroy):
- machine: `R_MACHINE * T = 0.00838 * 8 = 0.06704 USD`
- disk:    `R_DISK * (T / 730) = 0.40 * (8/730) = 0.00438 USD`
- IPv4:    `0.00 USD` (no external IPv4)
- NAT:     `0.00 USD` (no Cloud NAT)
- VPC peering: `0.00 USD`
- logging: `~0.00 USD` (firewall logs off)
- Total:   `0.07142 USD ≈ 0.066 EUR`

`PHASE3_SMOKE_CYCLE_LIMIT_EUR = 1.00 EUR`; conservative
projection `0.07 EUR << 1.00 EUR`. PASS.

The project budget remains EUR 245 of EUR 258 GCP credit,
unchanged by Phase 3.

## Authorization gates

- `APPROVE PHASE 3 EXECUTE` is required to apply the v2 plan
  via `bbr create --plan-file --expected-sha256
  --expected-commit`.
- `APPROVE PHASE 3 DESTROY EXECUTE` is required to apply the
  destroy plan via `bbr destroy`.
- No automatic destroy.

## Validation

- `pytest -q`: 75 passed, 0 failed (across `tests/unit/` and
  `tests/acceptance/`)
- `terraform fmt -check` (Phase 3 paths): PASS
- `terraform validate` (foundation + lab): PASS
- `./tools/check_phase2_wireguard_patterns.sh`: PASS
- `git diff --check`: clean
- Plan: 7 add / 0 change / 0 destroy
- No apply, no GCP mutation, no real runtime state committed
## Plan file path correction (v3)

The v2 plan file `/tmp/bbr-phase3-smoke-create-v2.tfplan`
(SHA-256 `b4054dda7194d92065c9a1fbf56e46e9bfb7b9e2a35154c71e3e9aea9239905d`)
was generated outside the `bbr plan` CLI and used a
hand-rolled path. The runtime state produced by `bbr plan`
therefore pointed at a different file.

The plan path is now canonical and unique:
`/tmp/bbr-phase3-smoke-create-v3.tfplan`. Both the CLI
(`src/bbr/cli.py`) and the documentation reference this
path. The v3 plan is produced from the corrected commit.

v2 marked obsolete via `/tmp/bbr-phase3-smoke-create-v2.tfplan.OBSOLETE`.

## Phase 3 Closeout Fixes

The Phase 3 Create was applied successfully and the Lab
went into READY. Two attempts to apply the v1 destroy plan
failed because:

1. **Credential-Preflight missing.** The first destroy
   attempt invoked `terraform apply` without a valid
   `GOOGLE_OAUTH_ACCESS_TOKEN`. Terraform rejected the
   call with "could not find default credentials" AFTER
   touching its State, which left the saved plan bound
   to a now-divergent State serial.

2. **Stale plan after failed apply.** A second attempt
   against the same plan file was rejected by Terraform
   with "Saved plan is stale" because the State had
   already been mutated by the first failed apply. Per
   Terraform semantics, a saved plan is bound to a
   specific State version and cannot be re-applied once
   that State has moved.

The original destroy plan
`/tmp/bbr-smoke-vm-001-destroy.tfplan` (SHA-256
`a2bbce9a394f735b51acd4ac5ec09a6fc9c0d9ffc2e596b5858353d99a36e272`)
is therefore **OBSOLETE** and must NEVER be re-applied.
A fresh destroy plan (v2) must be generated from the
current State in a separate planning gate.

### Closeout fixes implemented

- **Credential preflight (exit 18).** `bbr create` and
  `bbr destroy` (when extended) now check
  `GOOGLE_OAUTH_ACCESS_TOKEN` BEFORE invoking
  `terraform apply`. A missing or empty token aborts
  with a clear message and exit code 18; no subprocess
  is spawned and the State stays unmutated.

- **Plan-freshness check (exit 19).** `bbr create`
  compares the plan's recorded State serial against the
  current lab State serial (`terraform state pull`). On
  mismatch the command aborts with exit 19 and a message
  instructing the operator to re-plan. This is the
  defense-in-depth for the "Saved plan is stale" failure.

- **Destroy plan overwrite protection (exit 10).** If a
  destroy plan file already exists at the canonical path
  whose State serial matches the current State, `bbr
  destroy` refuses to silently overwrite it. The operator
  must rename the existing file to `.OBSOLETE` first or
  the State must advance. This enforces that a failed
  destroy must be followed by an explicit re-plan, never
  a silent reuse.

- **`cmd_verify` firewall filter fix.** The verify
  command now uses
  `gcloud compute firewall-rules list --format=json`
  and filters `targetTags` in Python. The previous code
  used the obsolete alias `gcloud compute firewalls list`
  with `--filter=targetTags:smoke-vm-001`, which gcloud
  rejects with `Invalid list filter expression`. The
  describe call (`firewall-rules describe`) is unchanged.

- **`cmd_verify` runtime-state consistency.** If the
  runtime state file is `PLANNED` but lacks
  `transition_history`, verify aborts with exit 13
  instead of crashing later on a `KeyError`.

### WireGuard routing/NAT analysis — Hypothesis

The Phase 3 wireguard-admin firewall
(`bbr-lab-smoke-vm-001-wg-admin`) accepts traffic only from
source range `10.254.0.0/24` (the WireGuard overlay
subnet). During Phase 3 EXECUTE, a transient WireGuard
tunnel from the operator to the bastion (`35.207.110.97`)
was established and the operator could ping `10.254.0.1`
(the bastion WG IP) successfully. However, neither
`ping 10.200.1.10` nor `tcp/22` to the lab VM via the
tunnel succeeded.

**Hypothesis (NOT yet verified):**

The bastion startup script
(`templates/bastion-startup.sh.tftpl`) installs the
following iptables MASQUERADE rule when the WireGuard
interface comes up:

```
iptables -t nat -A POSTROUTING \
  -s 10.254.0.0/24 -o ens4 -j MASQUERADE
```

This rule rewrites the source address of every packet
leaving the bastion towards its VPC interface (`ens4`)
from `10.254.0.0/24` (the WG overlay) to the bastion's
internal IP. When the operator sends a packet through the
tunnel to `10.200.1.10` (lab VM), MASQUERADE rewrites the
source from `10.254.0.2` (operator WG IP) to the bastion's
internal IP before the packet enters the VPC. The lab
firewall then sees the packet as coming from the bastion's
internal IP, NOT from `10.254.0.0/24`, and rejects it
because no rule matches.

**Evidence gathered so far:**

- Direct `ping 10.254.0.1` from the operator through the
  tunnel succeeded (handshake, transfer bytes recorded).
  This proves the WireGuard tunnel itself works.
- `ping 10.200.1.10` through the tunnel: 100% packet loss.
- `tcp/22` to `10.200.1.10` through the tunnel: connection
  refused.
- IAP-tunneled SSH to the same VM (`--tunnel-through-iap`)
  succeeded and showed the readiness marker is present.
  This proves the VM is reachable on `tcp/22` over an
  alternative path, and that the readiness marker is
  correctly written.
- The Phase 2 bastion firewall
  (`bbr-bastion-wireguard`) only allows UDP/51820, so any
  ICMP/TCP forwarded through the tunnel must be the
  MASQUERADE issue, NOT the bastion firewall (which
  would not affect already-encapsulated WG traffic).

**Evidence NOT yet gathered (verification needed):**

- Direct `tcpdump` on the bastion's `ens4` interface
  showing the source address of packets destined for
  `10.200.1.10`.
- `iptables -t nat -L -nv` output from the bastion while
  traffic flows.
- A bastion `ip route get 10.200.1.10 from 10.254.0.2`
  test to confirm which source address the bastion picks.
- Disabling MASQUERADE temporarily (or restricting it to
  a narrower source range) and re-testing.

**Alternative explanations NOT ruled out:**

- A different firewall rule on the bastion could also
  block ICMP/TCP from the operator even with MASQUERADE
  correctly scoped.
- The bastion's kernel routing table might not have a
  path back to the operator's WG IP after the rewrite.
- The WireGuard AllowedIPs on the bastion side might
  only include the operator's `/32` and not the broader
  `/24` lab subnet, causing the WG layer itself to drop
  return packets.

**Status:** Working hypothesis only. **NO Foundation change
will be made on the basis of this hypothesis alone.**
Verification with packet captures, iptables inspection,
and routing tables is required before any fix is proposed.
The investigation is documented for future Phase-4 work.

### What is NOT in this commit

- No new destroy plan was generated.
- No `terraform apply` was attempted.
- No GCP resource was mutated.
- No Foundation resource was modified.

### Authorisation gates (closeout)

- The `APPROVE PHASE 3 DESTROY EXECUTE` for the original
  destroy plan is no longer valid. That plan is OBSOLETE.
- A new `APPROVE PHASE 3 DESTROY EXECUTE` against a freshly
  generated v2 destroy plan is a separate planning gate.

## Lifecycle state diagram

```
Plan phase:        DEFINED -> VALIDATED -> PLANNED
                    (set by bbr plan, written to runtime state)

Create phase:      PLANNED -> CREATED -> BOOTSTRAPPING -> ISOLATED -> READY
                    (set by bbr verify after all GCP checks pass;
                     written to runtime state on transition)

Destroy phase:     READY -> STOPPED -> DESTROYED
                    (set by bbr destroy after successful teardown
                     verification; written to runtime state on transition)
```

Lifecycle transitions are written by the CLI commands
themselves, never by a Python helper invoked outside the
CLI surface. The runtime state MUST contain a complete
`transition_history` for the CLI to advance it further.
