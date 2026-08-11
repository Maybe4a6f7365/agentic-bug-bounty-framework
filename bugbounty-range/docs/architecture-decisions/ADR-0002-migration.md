# ADR-0002 — Migration from the existing WordPress lab

## Status

Accepted, 2026-07-25.

## Context

`labs/wordpress-cve-2026/` is a complete, working Phase-0
lab for WordPress 6.9.4 vs 6.9.5. It contains:

- A 719-line authoritative directive.
- Twelve Terraform skeleton files.
- Five provisioning shell scripts.
- Two Compose stacks (vulnerable + patched).
- Eight operational scripts.
- A complete cost estimate based on a 245 EUR credit budget.
- A documented procedure for dynamic-IP workstations.

The platform needs at least one real product pack as proof
of generality. WordPress is the natural first pack because
the existing lab already demonstrates the topology,
network model, and security invariants.

## Decision

`packs/wordpress-wp2shell/` reproduces the existing
WordPress topology entirely as a lab pack, using only
generic platform primitives. No WordPress-specific code is
added to the platform core. The existing
`labs/wordpress-cve-2026/` directory remains in place as
reference specification until the new pack demonstrates
full parity, then is archived.

## Parity requirements

The WordPress pack must preserve every property of the
existing lab. Specifically:

| Property | Existing lab | Pack |
|---|---|---|
| WordPress versions | 6.9.4 vs 6.9.5 | pinned by digest in pack manifest |
| PHP version | 8.3 | pinned by digest |
| MariaDB version | 10.11 | pinned by digest |
| Auto-update | disabled | enforced by `wp-config.php` setting baked into fixture |
| Public application access | none | enforced by `runtime_egress_policy.default = deny` and absence of any ingress rule |
| Public VM IPs | only the bastion | enforced by absence of `access_config` blocks in compute-node module |
| Runtime internet egress | denied after `bbr isolate` | enforced by `bootstrap_egress_policy.remove_after_bootstrap = true` |
| Application-consistent snapshots | yes | snapshot hooks for `compose_vm` flush and stop before snapshot |
| Deterministic restoration | yes | restoration hooks for `compose_vm` |
| Direct private communication to each target | yes | exposed_private_services on each node, destination_ref only |
| Raw response and side-effect comparison | yes | evidence engine captures full response bodies, hashes, sizes, timings |
| Synthetic fixtures | 1 admin, 2 authors, 10 posts | bundled in pack |
| Forbidden automatic update | yes | enforced by configuration baked into the Compose top-level args |

## Migration phases

1. **Phase 0 (now).** Ship the WordPress pack as a manifest
   that validates against `schemas/lab-pack.schema.json`.
   The Compose files from the existing lab move into the
   pack under `packs/wordpress-wp2shell/compose/`.
2. **Phase 1 + 2.** Provision the foundation and the
   per-lab segments. The WordPress pack is not yet ready to
   run because the platform's `compose_vm` driver is not
   implemented.
3. **Phase 3.** Implement `compose_vm`. Run the
   `smoke-compose` pack to prove the driver is generic.
4. **Phase 4.** Implement the differential engine. Run
   `smoke-compose` against `bbr diff`.
5. **Phase 5.** Run the WordPress pack against the
   differential engine and verify parity against the
   `labs/wordpress-cve-2026/` reference outputs.
6. **Phase 6.** Mark `labs/wordpress-cve-2026/` as
   `superseded`. Move the directory to `archive/`.

## Consequences

- The existing lab continues to be the canonical reference
  for the WordPress CVE-2026-63030 / CVE-2026-60137 work.
- Until parity is demonstrated, the WordPress pack is
  **not** a substitute for the existing lab.
- The WordPress pack is the first pack that uses
  `compose_vm`. Subsequent packs (`smoke-vm`,
  `smoke-compose`) exercise other parts of the platform.

## Alternatives considered

- **Cut over immediately.** Replace the existing lab with
  the new pack in Phase 1. Rejected because the platform
  is not yet proven generic; a cutover would lose the
  existing well-tested lab as a reference.
- **Skip the existing lab.** Ship the platform without a
  real product pack. Rejected because the platform needs a
  non-trivial pack to prove generality.