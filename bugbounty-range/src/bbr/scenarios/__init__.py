"""Scenario runner skeleton.

Phase 0. The runner validates every destination against
the active lab's registered network state (see DIRECTIVE.md
Section 11). Arbitrary external URLs, public IPs,
unregistered hostnames, redirect chains, production-target
hostnames, and credentials are rejected.

This skeleton exposes the surface area only. No HTTP client
or shell runner is wired in Phase 0.

`validate_destination` is the function the runner calls
before every HTTP or TCP step. It is fully implemented in
Phase 0 because the rule is simple and must be testable
offline.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from typing import Literal


StepKind = Literal[
    "http",
    "tcp",
    "shell",
    "readiness",
    "capture",
]


@dataclass(frozen=True)
class Step:
    kind: StepKind
    destination_ref: str | None = None
    method: str | None = None
    path: str | None = None
    body: str | None = None
    headers: dict[str, str] | None = None
    data: str | None = None
    script_ref: str | None = None
    args: list[str] | None = None
    node_ref: str | None = None


class ScenarioError(Exception):
    """Raised when a scenario step fails or is rejected."""


class DestinationRejected(ScenarioError):
    """Raised when a destination fails the registration check."""


# A URL with a scheme is rejected outright. The runner only
# accepts destinations inside the active lab.
_URL_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)

# Public IPv4 ranges that must never appear in a destination.
# Source: RFC 1918, RFC 5735, RFC 6890, plus loopback and
# link-local. RFC 6598 (100.64.0.0/10) is excluded because
# the platform does not use carrier-grade NAT.
_PUBLIC_IPV4_RANGES = (
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),  # overlap; ranges below are inside it
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("192.88.99.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("255.255.255.255/32"),
)


def is_public_ipv4(ip: ipaddress.IPv4Address) -> bool:
    """A destination is public if it falls outside any RFC
    1918 / RFC 5735 / link-local / loopback range.
    """
    return any(ip in r for r in _PUBLIC_IPV4_RANGES) is False and (
        ip.is_global or ip.is_reserved
    )


def _is_public_ipv4(addr: str) -> bool:
    try:
        ip = ipaddress.IPv4Address(addr)
    except ipaddress.AddressValueError:
        return False
    # Anything not in a private range is treated as public
    # for the purposes of destination rejection.
    private_ranges = (
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"),
    )
    if any(ip in r for r in private_ranges):
        return False
    if ip.is_loopback or ip.is_link_local or ip.is_multicast:
        return False
    return True


def validate_destination_ref(
    destination_ref: str,
    *,
    lab_state: dict,
) -> None:
    """Reject destinations that are not registered in the
    active lab's network state.

    `destination_ref` must be of the form `<node-id>:<service>`,
    where `<node-id>` is a registered node of the active lab
    and `<service>` is one of that node's exposed services.

    Rejects:

    - any value that contains a URL scheme;
    - any literal IPv4 address (public or private);
    - any literal hostname;
    - any value whose node-id is not registered in lab_state;
    - any value whose service is not in the node's
      exposed_private_services list;
    - empty strings.
    """
    if not destination_ref:
        raise DestinationRejected("destination_ref is required")
    if _URL_SCHEME_RE.match(destination_ref):
        raise DestinationRejected(
            f"destination_ref {destination_ref!r} contains a URL scheme"
        )
    if destination_ref.startswith("/"):
        raise DestinationRejected(
            f"destination_ref {destination_ref!r} is a path, not a service ref"
        )
    # Literal IPv4 anywhere in the ref is rejected.
    try:
        ipaddress.IPv4Address(destination_ref.split(":", 1)[0])
    except ipaddress.AddressValueError:
        pass
    else:
        raise DestinationRejected(
            f"destination_ref {destination_ref!r} is a literal IPv4 address"
        )
    if ":" not in destination_ref:
        raise DestinationRejected(
            f"destination_ref {destination_ref!r} must be of the form "
            "<node-id>:<service>"
        )
    node_id, service = destination_ref.split(":", 1)
    nodes = lab_state.get("topology", {}).get("nodes", [])
    registered = False
    service_list: list[dict] = []
    for n in nodes:
        if n.get("node_id") == node_id:
            registered = True
            service_list = n.get("exposed_private_services", [])
            break
    if not registered:
        raise DestinationRejected(
            f"destination_ref node_id {node_id!r} is not registered "
            f"in active lab state"
        )
    if not any(s.get("name") == service for s in service_list):
        raise DestinationRejected(
            f"destination_ref service {service!r} is not registered "
            f"on node {node_id!r}"
        )


def validate_destination(destination_ref: str, *, lab_state: dict) -> None:
    """Backward-compatible alias for validate_destination_ref."""
    validate_destination_ref(destination_ref, lab_state=lab_state)


__all__ = [
    "DestinationRejected",
    "ScenarioError",
    "Step",
    "is_public_ipv4",
    "validate_destination",
    "validate_destination_ref",
]