# ADR-0003 — Network isolation model

## Status

Accepted, 2026-07-25.

## Context

The platform runs sensitive workloads on GCP. Each lab must
be reachable only from the bastion, must not reach the
public internet after bootstrap, and must not reach other
labs. The platform must enforce these properties through
GCP cloud controls, not through Python CLI behaviour alone.

## Decision

The platform uses **one shared access VPC** and **one
isolated subnet per active lab**.

### Shared access VPC

A single VPC holds the WireGuard bastion and the operator
admin tunnel. The bastion is the only VM with a public IPv4
address; that address accepts WireGuard UDP/51820 from a
source-restricted allowlist (`VPN_ALLOWED_STATIC_CIDRS`)
plus, after a runtime operator step, from a dynamic-IP
operator's current IPv4 (see
`docs/architecture-decisions/ADR-0004-secrets.md` and the
operating procedure in `DIRECTIVE.md`).

### Per-lab subnet

Every active lab receives:

- A dedicated subnet `10.<lab-id>.<lab-index>.0/24`
  allocated from a documented platform range.
- A dedicated network tag and a dedicated runtime service
  account, both used to target the lab's firewall rules.
- A default-deny ingress rule from any other lab's subnet
  and from the public internet.
- A default-deny egress rule, except for the explicit
  bootstrap allowlist (used during `bbr bootstrap`).
- No public IPv4 address on any lab VM.
- An independently removable firewall and routing policy.

### Active-lab cap

The default maximum number of active labs is **one**. The
hard configurable maximum for v1 is **two**. The platform
rejects `bbr create` once the cap is reached.

### Enforcement layer

The platform enforces isolation through:

- VPC firewall rules (allow / deny per protocol).
- Subnet routing (custom routes only as required by the
  driver).
- Service-account-based egress filtering.
- IAP TCP forwarding for SSH access to the bastion and lab
  VMs.
- Shielded VM options on every lab VM.

The Python CLI is **not** the enforcement layer. A
misbehaving scenario script, a bug in the control plane, or
a malicious pack cannot relax the isolation because the
firewall rules live in GCP, not in the CLI.

## Consequences

- Operators reach lab VMs via IAP SSH from the bastion, not
  via direct internet routes.
- A dynamic-IP operator temporarily adds their current
  public IPv4 to the bastion's firewall allowlist and
  removes it on disconnect.
- Adding a new lab does not require changes to the bastion
  firewall.
- Destroying a lab does not disturb another lab's network
  state.

## Alternatives considered

- **Per-lab VPC.** Each lab gets its own VPC. Rejected for
  v1 because it would double the VPC quota usage and add
  cross-VPC routing complexity. A future version may
  revisit.
- **Single VPC, no subnets.** Rejected because it would
  force all labs onto the same broadcast domain and break
  the isolation guarantees.
- **Mesh WireGuard.** Each lab VM has its own WireGuard
  peer. Rejected because the bastion already provides
  single-point access and a mesh would multiply the key
  management surface.