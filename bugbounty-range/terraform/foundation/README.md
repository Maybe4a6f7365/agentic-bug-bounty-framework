# Terraform foundation skeleton — Phase 0

This directory ships the foundation root module for Phase 0
and later. No `resource` block is enabled until the
operator issues the exact phrase `APPROVE PHASE 1`.

The foundation provisions, in this order:

1. The dedicated GCP project (`terraform/foundation/project.tf`).
2. The billing budget (`terraform/foundation/billing.tf`).
3. The shared access VPC (`terraform/foundation/network.tf`).
4. The single bastion VM (`terraform/foundation/bastion.tf`).
5. The bastion ingress firewall (`terraform/foundation/firewall.tf`).
6. The runtime state bucket (`terraform/foundation/state-bucket.tf`).
7. Provider pinning (`terraform/foundation/providers.tf`).
8. Outputs for the control plane
   (`terraform/foundation/outputs.tf`).

The foundation applies once. Per-lab resources live in
`terraform/modules/*` and are consumed by the control
plane through separate Terraform root modules per lab.

Phase 0 ships only commented-out `resource` blocks plus
the version pinning, the variables, and the locals.