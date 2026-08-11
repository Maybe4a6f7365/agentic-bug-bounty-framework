# ADR-0009 — Generic Single-Lab Lifecycle (hardened v2)

Status: Accepted, Phase 3 vertical slice.

## Context

Phase 0–2 established the BBR shared access plane (bbr-shared-vpc,
bbr-bastion, WireGuard overlay, foundation outputs in GCS).
Phase 3 introduces the generic single-lab lifecycle vertical
slice.

Phase 3 v2 hardens the v1 design after the v1 review:

  - the v1 readiness marker was written by `post-create.sh` SSH
    (an out-of-plan mutation). v2 renders the readiness marker
    via `metadata_startup_script` (templatefile) inside the
    Terraform plan. The plan is the SOLE source of truth.
  - v1 allowed the lab subnet to carry a `prevent_destroy = true`
    guard. That guard prevented the explicit destroy gate from
    completing. v2 removes the guard.
  - v1 used a `state/` gitignore pattern that also matched the
    `src/bbr/state/` source module. v2 anchors the rule with
    `/state/` to match only the repo-root runtime directory.
  - v1 used `PHASE3_SMOKE_CYCLE_LIMIT_EUR * 2 = 2.00 EUR` as the
    cost guard. v2 uses exactly `1.00 EUR`.
  - v1 fixed internal IP via an optional default. v2 fixes
    internal IP at `10.200.1.10` for the smoke plan and
    validates it.
  - v1 implemented `bbr create` with two flags. v2 requires
    `--plan-file --expected-sha256 --expected-commit` AND
    checks HEAD, working tree, origin/main, runtime state,
    backend prefix, plan SHA, plan shape.

## Decisions (v2)

1. **Independent Per-Lab Terraform Root.** Phase 3 introduces
   `terraform/lab/`, a fully independent Terraform root that
   reads the foundation outputs via
   `data "terraform_remote_state" "foundation"` and never
   manages foundation resources directly. Foundation and
   lab-lifetime state live in separate GCS prefixes:
   `foundation/` and `labs/<lab-id>/`.

2. **GCS State Prefix Per Lab.** Each lab's Terraform state is
   stored under `gs://bbr-state-<project>/labs/<lab-id>/`. The
   backend is configured at `terraform init` time via
   `-backend-config`; no backend interpolation in HCL.

3. **Local Runtime State.** Every lab has a local
   `state/<lab-id>.json` file that records:
     - lab_id, pack_id, version
     - current lifecycle state
     - allocated CIDR
     - internal IP
     - backend prefix
     - planfile path and SHA-256
     - source commit
     - operator identity
     - TTL deadline
     - node list
     - transition history (DEFINED -> VALIDATED -> PLANNED)
   The runtime state file is product-agnostic. Phase 3 forbids
   committing real runtime state for `smoke-vm-001`. The CLI
   writes the state atomically (tmp + rename + fsync) only
   AFTER every validation step has succeeded; a failed plan
   leaves no state file.

4. **Deterministic Subnet Allocation.** The allocator walks
   `10.200.1.0/24..10.200.254.0/24` and returns the first CIDR
   not in use by local runtime state files or existing GCP
   subnets. `10.200.0.0/24` (control plane) is excluded. Active
   lab limit is 1 (hard cap 2). Re-use of an active CIDR is
   forbidden.

5. **Fixed Internal IP.** Phase 3 lab VMs are configured with
   `network_ip = var.internal_ip`. The smoke pack hard-codes
   `10.200.1.10` and the CLI rejects any other IP for that pack.
   The IP must be inside the per-lab subnet and not be the
   network or broadcast address.

6. **No External IP.** Phase 3 lab VMs have no `access_config`
   block, no external IPv4, and `can_ip_forward = false`.
   Inbound access is restricted to:
     - WireGuard overlay (10.254.0.0/24) for SSH/ICMP
     - Google IAP range (35.235.240.0/20) for SSH
   No public ingress from `0.0.0.0/0`.

7. **Default-Deny Egress.** A dedicated
   `google_compute_firewall` with `direction = "EGRESS"`,
   `priority = 65000`, `destination_ranges = ["0.0.0.0/0"]`,
   and `deny { protocol = "all" }` is attached to the lab node
   via target tags. Priority 65000 is higher than the implied
   allow-egress at default priority 65534.

8. **Plan-Embedded Readiness Marker.** The readiness marker at
   `/var/lib/bbr/ready` is written by a Terraform-rendered
   `metadata_startup_script` (templatefile). The script uses
   ONLY local operating-system utilities (no apt-get, no curl,
   no wget, no git clone, no pip install, no npm install, no
   docker, no podman). The script and its output are part of
   the reviewed plan file. There is no out-of-band SSH write.

9. **Ephemeral Lab Subnet — no `prevent_destroy`.** The lab
   subnet does NOT carry a `prevent_destroy` guard. The
   destroy gate (`APPROVE PHASE 3 DESTROY EXECUTE`) is the
   authoritative authorization. A `prevent_destroy` on the lab
   subnet would make the audited destroy impossible.

10. **Strict Apply Gates.** `bbr create` requires all three
    flags (`--plan-file`, `--expected-sha256`,
    `--expected-commit`). Before invoking `terraform apply`,
    the CLI verifies:
      - plan file exists
      - plan SHA matches the argument exactly
      - HEAD == origin/main
      - HEAD == --expected-commit
      - working tree is clean
      - runtime state exists and is in state PLANNED
      - lab_id matches the positional argument
      - backend_prefix is `labs/smoke-vm-001`
      - runtime state plan_file and plan_sha256 match the
        arguments provided on the command line
      - terraform show -json reports exactly 7 creates,
        0 updates, 0 deletes, on the expected addresses only
      - no `access_config`, no foundation resources, no NAT,
        no VPC peering, no public ingress
    Any mismatch aborts the apply path.

11. **Cost Guard.** `PHASE3_SMOKE_CYCLE_LIMIT_EUR = 1.00 EUR`.
    The pack validation enforces this limit directly: a pack
    with `cost_limits.per_cycle_eur_limit > 1.00` is rejected
    by `bbr validate`. The conservative 8h smoke projection is
    ≈0.07 EUR.

12. **WordPress Deferred to Phase 4.** The Phase 3 vertical
    slice is fully generic. WordPress requires a controlled
    bootstrap / artifact pipeline and is deferred to Phase 4.

## Consequences

- The platform now has a complete lifecycle skeleton that any
  generic pack can use.
- Lab lifetime is bounded by 8h max and 30m idle, enforced by
  the runtime state machine (TTL field).
- A maximum of two labs can be active concurrently.
- The Plan file is the only artifact allowed to drive apply.
  Any mismatch in SHA, commit, or working-tree state aborts
  the apply path.

## Compliance

The Phase 3 vertical slice produces exactly seven GCP resources
(1 subnetwork, 1 service account, 1 service-account IAM member,
1 instance, 3 firewalls). Foundation resources are not managed
by the lab root.
## Plan path canonicalization (v3)

The CLI and the documentation must agree on a single plan
file path. Phase 3 v3 canonicalizes the path to
`/tmp/bbr-phase3-smoke-create-v3.tfplan`. The v2 plan file
is marked obsolete and is not applied. The runtime state
records this exact path and its SHA-256, so `bbr create`
can verify the on-disk plan matches the reviewed plan.

## Closeout corrections (v4)

After Phase 3 EXECUTE completed successfully, two attempts
to apply the v1 destroy plan failed. The root causes and
the corrections applied in v4 are documented here.

### Root cause 1: missing credential preflight

The first destroy attempt invoked `terraform apply`
without a valid `GOOGLE_OAUTH_ACCESS_TOKEN`. Terraform
rejected the call after touching its State. The State
serial advanced even though no resources changed, which
left the saved destroy plan bound to a now-divergent
State.

**Decision:** Every CLI command that may invoke
`terraform apply` MUST check `GOOGLE_OAUTH_ACCESS_TOKEN`
**before** invoking terraform. Missing or empty token
aborts the command with exit code 18 and a clear message;
no subprocess is spawned and the State stays unmutated.

### Root cause 2: stale plan binding

A second attempt against the same destroy plan file was
rejected by Terraform with `Saved plan is stale`. Per
Terraform semantics, a saved plan is bound to a specific
State version; once the State has moved, the plan cannot
be re-applied.

**Decision:** The CLI MUST detect this case BEFORE invoking
apply and refuse to start. The check compares the plan's
recorded State serial against the current lab State serial
(`terraform state pull`). On mismatch the command aborts
with exit code 19 and instructs the operator to re-plan.

### Decision 3: destroy plan overwrite protection

A silent overwrite of an existing destroy plan would mask
exactly this kind of mistake. After a failed destroy the
operator must rename the existing file to `.OBSOLETE` (or
the State must advance) before `bbr destroy` will produce
a fresh plan.

**Decision:** `bbr destroy` MUST refuse to silently
overwrite an existing destroy plan whose State serial
matches the current State. The operator gets exit code 10
and a message instructing them to mark the existing file
obsolete first.

### Decision 4: verify command hardening

`bbr verify` used `gcloud compute firewalls list
--filter=targetTags:smoke-vm-001`. The `firewalls`
subcommand is an obsolete alias and `targetTags:` is not
accepted as a list filter expression, so the call
returned zero rows and the verify command always failed
the firewall check. The verify also crashed with a
`KeyError` on `transition_history` when the runtime state
was incomplete.

**Decision:** `bbr verify` MUST use
`gcloud compute firewall-rules list --format=json` and
filter `targetTags` in Python. The runtime-state check
MUST also fail loudly (exit 13) when the state is
`PLANNED` but lacks `transition_history`, instead of
silently passing.

### WireGuard routing/NAT analysis — Hypothesis

Phase 3 EXECUTE established a transient WireGuard tunnel
from the operator to the bastion (`35.207.110.97`) using
the Phase 2 WireGuard overlay. The handshake succeeded and
the operator could reach `10.254.0.1` (bastion WG IP).
Neither `ping 10.200.1.10` nor `tcp/22` to the lab VM via
the tunnel succeeded. IAP-tunneled SSH to the same VM
worked, which proves the VM is reachable on tcp/22 and
that the readiness marker is correctly written.

**Hypothesis (NOT yet verified):** the bastion startup
script (`templates/bastion-startup.sh.tftpl`) installs a
MASQUERADE rule on the bastion that rewrites the source
of every packet leaving `ens4` from the WG overlay
(`10.254.0.0/24`) to the bastion's internal IP. Lab
firewall `bbr-lab-smoke-vm-001-wg-admin` accepts only
source range `10.254.0.0/24`; MASQUERADE means packets
arrive with the bastion's internal IP and are rejected.

**Status:** Working hypothesis only. **No Foundation
change will be made on this hypothesis alone.** Verification
via packet captures, `iptables -t nat -L`, and routing-table
inspection on the bastion is required before any fix is
proposed. See `notes/PHASE-3-PLAN.md` for the full evidence
inventory and alternative explanations.
