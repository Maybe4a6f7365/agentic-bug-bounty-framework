# BugBountyRange — Threat Model

This document records the threat model the platform must
satisfy in v1. It is referenced from `DIRECTIVE.md` Section 8
and Section 15.

## Trust boundaries

```
┌─────────────────────────────────────────────────────────────┐
│  Operator workstation(s)                                   │
│   - Workstation A (static IPv4 baked into VPN_ALLOWED_     │
│     STATIC_CIDRS)                                          │
│   - Workstation B (dynamic IPv4, runtime firewall update)  │
│   - Hermes worker (91.99.86.45/32)                         │
│   - Max's Hermes agent (178.104.89.75/32)                  │
└──────────────────────────────────┬──────────────────────────┘
                                   │ WireGuard / UDP 51820
                                   │ source-restricted
                                   ▼
┌─────────────────────────────────────────────────────────────┐
│  GCP project (dedicated)                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Shared access VPC                                    │  │
│  │  - 1 bastion VM with public IPv4                     │  │
│  │  - WireGuard listener UDP/51820                      │  │
│  │  - IAP TCP forwarder for OS Login SSH                │  │
│  └─────────────┬───────────────────────┬────────────────┘  │
│                │ per-lab segment         │                  │
│  ┌─────────────▼────────┐ ┌─────────────▼────────┐         │
│  │ Lab subnet A         │ │ Lab subnet B (≤2)    │         │
│  │ - node 1             │ │ - node 1             │         │
│  │ - node 2             │ │ - node 2             │         │
│  │ - default-deny       │ │ - default-deny       │         │
│  │   ingress/egress     │ │   ingress/egress     │         │
│  │ - per-lab SA         │ │ - per-lab SA         │         │
│  └──────────────────────┘ └──────────────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

## Threat actors

| Actor | Capability | Mitigation |
|---|---|---|
| Compromised operator workstation | Holds a WireGuard private key | Key is per-lab; revocation = re-issue the lab pack; no other lab is exposed because every lab has its own WireGuard peer entry. |
| Compromised scenario script inside a lab | Can make any request the network allows | Network isolation: default-deny ingress from anywhere, default-deny runtime egress, no public addresses. The lab cannot reach the internet, the operator workstation, or any other lab's subnet. |
| Compromised lab VM | Root on the VM | VM has no public IP, no SSH ingress except via IAP, no internet egress after `bbr isolate`. VM-side firewall rejects metadata-server access via the DOCKER-USER chain. |
| Compromised bastion | Holds WireGuard server key | Server key lives only in `/etc/wireguard/`, mode `0600`, owner `root`. Bastion has no public IP except the WireGuard UDP/51820 listener. SSH is IAP-only. |
| Compromised GCP credentials | Can issue gcloud commands | Platform operator identity is the only authority. The control plane never accepts commands from anonymous sources. |
| Compromised Terraform state | Could reveal subnet / IP allocations | State bucket is private, uniform-bucket access, versioned, lifecycle-cleaned, no public access. |
| Compromised control plane (this Python) | Could be made to misbehave by a malicious pack | Packs are validated against a JSON Schema; the control plane refuses to load Python code from outside the platform repository; the network isolation layer is the final enforcement boundary. |
| Replayed or forged lab pack | Could attempt to add product-specific branches | Schema validation rejects unknown fields; the platform refuses to call any product-specific adapter. |
| Insider threat (operator) | Has all credentials | Out of scope — the operator is trusted. |

## Out-of-scope threats

- Nation-state level attacks against GCP itself.
- Physical access to the GCP data centre.
- Side-channel attacks on a lab VM's CPU or memory.
- Social-engineering of GCP support.
- Quantum attacks on WireGuard's Curve25519.

## Critical security invariants

1. **No lab VM ever has a public IP.**
2. **No lab VM can reach the public internet after `bbr isolate`.**
3. **No lab VM can reach another lab's subnet.**
4. **The WireGuard listener only accepts source IPs from `VPN_ALLOWED_STATIC_CIDRS`.**
5. **Operator SSH into the bastion or any lab VM uses IAP TCP forwarding.**
6. **Container access to the GCP metadata server is blocked at the VM firewall level.**
7. **The control plane refuses to load Python code from outside the platform repository.**
8. **The pack schema rejects unknown top-level fields.**
9. **Secrets never appear in Terraform variables, Terraform state, the lab manifest, or scenario output.**
10. **Image digests are pinned. Mutable tags are not permitted.**

These invariants are checked at every lab phase by
`scripts/verify-isolation.sh` (driver-supplied). The check
fails closed: any invariant violation halts the platform.