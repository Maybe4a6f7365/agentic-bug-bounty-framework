# ADR-0001 — BugBountyRange platform exists

## Status

Accepted, 2026-07-25.

## Context

The lab owner operates in a long-running bug-bounty research
program. Validating behavioural hypotheses against
vulnerable-versus-patched stacks requires a reproducible,
isolated local lab. The existing
`labs/wordpress-cve-2026/` directory is a single-purpose
WordPress 6.9.4-versus-6.9.5 lab built around an
authoritative directive.

The next research cycle will require additional stacks
(WordPress again with new CVEs, GitLab, Nginx, Node.js
services, Java services, and any other technology that
becomes relevant). A second single-purpose lab per stack
would duplicate infrastructure code, drift in style, and
silently reintroduce the same mistakes in every copy.

## Decision

Introduce **BugBountyRange** as a generic, product-agnostic
GCP lab platform. The platform is described in
`DIRECTIVE.md` and built around three properties:

1. **Product-agnostic core.** No WordPress, GitLab, Nginx, or
   other product-specific code in the control plane, the
   Terraform modules, the lifecycle state machine, the
   network isolation model, or the evidence engine.
2. **Lab packs.** A new stack is added by creating a
   `packs/<pack-id>/` directory containing only declarative
   manifests, Compose files, provisioning scripts, fixtures,
   readiness checks, snapshot hooks, and test scenarios.
3. **Enforced isolation.** Isolation is enforced by GCP cloud
   controls (firewall, routing, service accounts, IAP),
   not by Python CLI behaviour alone.

## Consequences

- The existing `labs/wordpress-cve-2026/` directory remains
  untouched as reference material until the
  `packs/wordpress-wp2shell/` pack demonstrates full parity
  (see ADR-0002).
- Phase 0 produces the platform directive, threat model,
  schemas, and skeletons only. No GCP resource is created
  in Phase 0.
- Phase 1 introduces the foundation: project, billing
  guardrails, single bastion, shared access VPC, runtime
  state bucket.
- Phase 2 introduces per-lab Terraform modules and the
  isolation model.
- The first three lab packs (`smoke-compose`, `smoke-vm`,
  `wordpress-wp2shell`) gate the platform's first release.

## Alternatives considered

- **Status quo.** Continue adding single-purpose labs under
  `labs/<stack>/<cve>/`. Rejected because each new lab would
  duplicate infrastructure code and would not enforce shared
  isolation invariants.
- **Product-specific framework.** Build one giant
  `wp2shell-framework` with adapter classes per stack.
  Rejected because it embeds the wrong assumption that
  WordPress is the central product.
- **Kong / Tyk / Terraform Cloud / Spacelift as the
  orchestration plane.** Rejected because these add a
  dependency on a SaaS that the platform cannot audit.