# packs/smoke-vm — generic single-lab lifecycle vertical slice

This pack is the Phase 3 vertical slice. It exercises the
per-lab Terraform root, the GCS state prefix, the
lifecycle state machine, the local runtime state file,
the network allocator, the locked transition checks,
and the CLI commands `bbr validate`, `bbr plan`,
`bbr create`, `bbr verify`, `bbr list`, and
`bbr destroy`.

The pack contains **no** product code and **no**
WordPress-specific configuration. It is fully generic.

## Topology

A single raw-vm node `smoke-vm-001` running Debian 12
(pinned by Self-Link, not by family) with OS Login,
IAP-tunneled SSH, WireGuard admin access from the BBR
overlay, default-deny egress, and a deterministic local
readiness marker at `/var/lib/bbr/ready`.

## Bootstrap

The startup script uses only local operating-system
utilities (no `apt-get`, `curl`, `wget`, `docker pull`,
`git clone`, `pip install`, `npm install`). It writes
the readiness marker once and exits.

## Out of scope (Phase 4 and later)

- WordPress
- Docker Compose
- External image or package downloads
- Cloud NAT
- External IPs for lab VMs
- Snapshots
- Multiple active labs

## Review Plan

For this Phase 3 commit, the reviewed plan is
`/tmp/bbr-phase3-smoke-create-v1.tfplan`. It produces
exactly seven resources: one subnet, one service
account, one service-account IAM member, one VM, three
firewall rules. Foundation resources are not touched.