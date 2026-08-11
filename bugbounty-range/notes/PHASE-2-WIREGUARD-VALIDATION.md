# Phase 2 — WireGuard End-to-End Data Path Validation

This report records a separate, end-to-end validation
of the BugBountyRange Phase 2 WireGuard data path. It
complements the Phase 2 closeout (tag
`bbr-phase2-closed`, commit `3d398a5755`).

The Phase 2 closeout proved the **active server service**
and the **peer configuration** on the bastion. This
separate test proves, for the first time, the
**actual end-to-end handshake and data path** from the
Hermes operator to the bastion through the shared
WireGuard tunnel.

No Terraform action and no GCP mutation occurred. The
Hermes private key remained in its permanent,
operator-controlled store and was never copied,
exported, or written to a new configuration file.

## 1. Pre-flight checks

- Hermes private key file readable, mode 0600 — PASS
- `bbr0` interface did not exist on Hermes — PASS
- Hermes egress IPv4 `91.99.86.45` matched
  `vpn_allowed_static_cidrs[0]` — PASS
- Bastion server public key (44 base64, ending `=`)
  loaded into a temporary test variable — PASS

## 2. Test setup

A transient WireGuard interface bbr0 was created on
the Hermes operator host using the existing Hermes
WireGuard operator private key. The interface address
was `10.254.0.2/32`, MTU 1420, with one peer (the
bastion server public key) configured for `allowed-ips
10.254.0.1/32,10.200.0.0/16` and a `persistent-keepalive`
of 25 seconds.

No default route was added. No `0.0.0.0/0` was routed
through WireGuard. The interface was scheduled for
teardown via a shell trap and was deleted at the end
of the test.

## 3. Test parameters

| Parameter | Value |
|---|---|
| Test time (UTC) | `2026-07-26T07:02:40.048272Z` |
| Hermes egress IPv4 | `91.99.86.45` |
| Bastion WireGuard endpoint | `35.207.110.97:51820` |
| Bastion server public key | `kA2iGM2sdvvalf1Vc6HT6zwf3MzN/RIazXWNSzK9bkA=` |
| Client interface address | `10.254.0.2/32` |
| Client interface MTU | 1420 |
| Server interface address (rendered) | `10.254.0.1/24` |
| Bastion internal VPC address | `10.200.0.10` |
| WireGuard listen port (bastion) | UDP/51820 |
| Persistent keepalive | 25 seconds |

## 4. Data-path tests

| Test | Result |
|---|---|
| `ping -c 3 -W 3 10.254.0.1` (bastion WireGuard address) | **PASS** — 3/3 received, ~6 ms |
| `ping -c 3 -W 3 10.200.0.10` (bastion VPC address via tunnel) | **PASS** — 3/3 received, ~6 ms |
| `timeout 5 bash -c '</dev/tcp/10.200.0.10/22'` (SSH port via tunnel) | **PASS** |

All three data-path tests succeeded. The reachable
VPC address proves that IP forwarding on the bastion
is functional and that the return route
`10.254.0.0/24` (untagged, applies to the whole VPC)
is correctly installed.

## 5. Client-side handshake and transfer

| Metric | Value |
|---|---|
| Latest handshake (Unix timestamp) | `1785049295` |
| Latest handshake (UTC ISO) | `2026-07-26T07:01:35Z` |
| Bytes received (client view) | `1276` |
| Bytes sent (client view) | `1396` |
| Bytes transferred (client view, total) | `2672` |
| Server persistent keepalive | every 25 seconds |

Handshake > 0: PASS. Transfer > 0: PASS.

## 6. Server-side handshake and transfer

| Metric | Value |
|---|---|
| Latest handshake (Unix timestamp) | `1785049295` |
| Latest handshake (UTC ISO) | `2026-07-26T07:01:35Z` |
| Bytes received (server view) | `2972` |
| Bytes sent (server view) | `2676` |
| Bytes transferred (server view, total) | `5648` |

Client and server counters were sampled at different
times and include WireGuard handshake, keepalive, and
encrypted transport overhead. They are therefore not
expected to be byte-identical. Both sides recorded
non-zero transfer and the same latest handshake
timestamp.

Handshake > 0: PASS. Transfer > 0: PASS.
`net.ipv4.ip_forward = 1` on the bastion: PASS.

## 7. Local teardown

After the tests, the temporary `bbr0` interface was
deleted along with its routes. Verified:

- `/sys/class/net/bbr0` does not exist — PASS
- `ip link show | grep wireguard` empty — PASS
- `ip route show dev bbr0` reports `Cannot find device` — PASS
- The operator-controlled private-key file remained mode 0600 — PASS
- No persistent local WireGuard configuration created — PASS
- No new file under `/etc/wireguard/` on Hermes — PASS

## 8. Private key handling

The Hermes private key was referenced exclusively via
its existing permanent, operator-controlled location
during the test. It was never written to a new file,
never embedded in a script, and never transmitted
through the WireGuard tunnel or any other channel. The
WireGuard kernel module reads the key in memory on
wg set; nothing persistent was left behind.

## 9. No Terraform or GCP mutation

This validation produced zero Terraform actions and
zero GCP mutations. The repository was not modified by
the test; this report is the only side effect, and it
is appended to the working tree as a documentation
file.

## 10. Terminology correction

The Phase 2 closeout confirmed the **active WireGuard
server** and the **peer configuration** on the bastion.
This separate test is the first document that confirms
the **actual end-to-end handshake and data path** from
the Hermes operator to the bastion. The two reports
are complementary; neither alone is sufficient as an
end-to-end proof.