"""Per-lab network allocator and firewall rule builder.

Phase 0. The allocator picks a /24 subnet from the
documented platform range (10.200.1.0/24 through
10.200.254.0/24), avoiding the reserved control-plane
subnet (10.200.0.0/24). The allocator is deterministic and
collision-free against the active-lab list.

ADR-0003 reserves the bastion's WireGuard client range
separately at 10.254.0.0/24. That range is NOT under the
per-lab pool.

Decisions captured from the platform operator (2026-07-25):

- platform VPC range:        10.200.0.0/16
- control-plane subnet:      10.200.0.0/24  (reserved, never allocated to a lab)
- per-lab subnet pool:       10.200.1.0/24 through 10.200.254.0/24
- WireGuard overlay:         10.254.0.0/24

The existing the reference target reference lab (labs/the reference target-cve-2026/)
uses 10.77.0.0/24 and is therefore not affected by this range.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass


PLATFORM_VPC_CIDR = ipaddress.ip_network("10.200.0.0/16")
RESERVED_SUBNETS = (
    ipaddress.ip_network("10.200.0.0/24"),  # control-plane subnet
)
PER_LAB_POOL_START = ipaddress.ip_network("10.200.1.0/24")
PER_LAB_POOL_END = ipaddress.ip_network("10.200.254.0/24")
WIREGUARD_OVERLAY_CIDR = ipaddress.ip_network("10.254.0.0/24")

HARD_MAX_ACTIVE_LABS = 2
DEFAULT_MAX_ACTIVE_LABS = 1


@dataclass(frozen=True)
class LabSubnet:
    lab_id: str
    cidr_block: ipaddress.IPv4Network


class ActiveLabLimitExceeded(Exception):
    """Raised when the active-lab limit is exceeded."""


class SubnetPoolExhausted(Exception):
    """Raised when no /24 is free in the per-lab pool."""


def assert_within_active_lab_limit(
    active_count: int,
    *,
    hard_max: int = HARD_MAX_ACTIVE_LABS,
) -> None:
    if active_count >= hard_max:
        raise ActiveLabLimitExceeded(
            f"active lab count {active_count} reaches hard max {hard_max}"
        )


def assert_cidr_in_pool(cidr: ipaddress.IPv4Network) -> None:
    if cidr in RESERVED_SUBNETS:
        raise ValueError(f"{cidr} is reserved for the control plane")
    if not cidr.subnet_of(PLATFORM_VPC_CIDR):
        raise ValueError(f"{cidr} is outside platform VPC {PLATFORM_VPC_CIDR}")


def enumerate_pool() -> list[ipaddress.IPv4Network]:
    """Return all /24 subnets in the per-lab pool, in order."""
    pool_start = int(PER_LAB_POOL_START.network_address)
    pool_end = int(PER_LAB_POOL_END.network_address)
    out: list[ipaddress.IPv4Network] = []
    for addr_int in range(pool_start, pool_end + 1, 256):
        net = ipaddress.ip_network((addr_int, 24))
        assert isinstance(net, ipaddress.IPv4Network)
        out.append(net)
    return out


def allocate_subnet(
    lab_id: str,
    used_cidrs: list[ipaddress.IPv4Network],
) -> LabSubnet:
    """Allocate the next free /24 in the per-lab pool.

    Phase 0: deterministic allocation using enumeration order.
    Phase 1+: real allocator with active-lab awareness and
    collision detection against GCP subnet list.
    """
    assert_cidr_in_pool(PER_LAB_POOL_START)
    used = set(used_cidrs)
    for net in enumerate_pool():
        if net not in used:
            return LabSubnet(lab_id=lab_id, cidr_block=net)
    raise SubnetPoolExhausted(
        f"no free /24 in pool {PER_LAB_POOL_START} to {PER_LAB_POOL_END}"
    )


__all__ = [
    "DEFAULT_MAX_ACTIVE_LABS",
    "HARD_MAX_ACTIVE_LABS",
    "LabSubnet",
    "PER_LAB_POOL_END",
    "PER_LAB_POOL_START",
    "PLATFORM_VPC_CIDR",
    "RESERVED_SUBNETS",
    "WIREGUARD_OVERLAY_CIDR",
    "ActiveLabLimitExceeded",
    "SubnetPoolExhausted",
    "allocate_subnet",
    "assert_cidr_in_pool",
    "assert_within_active_lab_limit",
    "enumerate_pool",
]