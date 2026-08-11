"""BugBountyRange network allocator — Phase 3.

Deterministic subnet allocator for per-lab /24 subnets inside the
shared BBR VPC (10.200.0.0/16). The control-plane subnet
(10.200.0.0/24) is reserved. Allocation starts at 10.200.1.0/24
and walks up to 10.200.254.0/24. The allocator never reuses an
in-use CIDR and never reallocates the control-plane subnet.

The allocator is intentionally simple:

  - In-use CIDRs are read from local runtime state files in
    `state/<lab-id>.json` plus a read-only GCP query against
    `compute.networks.subnets`.
  - The control-plane CIDR (10.200.0.0/24) is always excluded.
  - The hard cap on simultaneous active labs is taken from
    `ACTIVE_LAB_LIMIT` (default 1, hard max 2).
  - The next free /24 is returned as the allocation.

This module is product-agnostic. It returns a string CIDR.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

CONTROL_PLANE_CIDR = "10.200.0.0/24"
ALLOCATION_POOL_START = "10.200.1.0/24"
ALLOCATION_POOL_END = "10.200.254.0/24"
DEFAULT_ACTIVE_LAB_LIMIT = 1
HARD_CAP_ACTIVE_LABS = 2


class AllocationError(RuntimeError):
    """Raised when the allocator cannot assign a CIDR."""


@dataclass(frozen=True)
class AllocationResult:
    cidr: str
    active_lab_count: int
    in_use_cidrs: list[str]


def _cidr_to_int(cidr: str) -> int:
    prefix = cidr.split("/", 1)[0]
    octets = prefix.split(".")
    return (
        (int(octets[0]) << 24)
        | (int(octets[1]) << 16)
        | (int(octets[2]) << 8)
        | int(octets[3])
    )


def _all_pool_cidrs() -> list[str]:
    start = _cidr_to_int(ALLOCATION_POOL_START)
    end = _cidr_to_int(ALLOCATION_POOL_END) + 256  # inclusive end
    cidrs = []
    for n in range(start, end, 256):
        cidrs.append(
            f"{(n >> 24) & 0xff}.{(n >> 16) & 0xff}.{(n >> 8) & 0xff}.{n & 0xff}/24"
        )
    return cidrs


def list_local_state_cidrs(state_dir: Path) -> list[str]:
    """Read every <lab-id>.json in state_dir and return the lab_subnet_cidr field."""
    if not state_dir.is_dir():
        return []
    out: list[str] = []
    for f in sorted(state_dir.glob("*.json")):
        try:
            d = json.loads(f.read_text())
            cidr = d.get("lab_subnet_cidr")
            if cidr:
                out.append(cidr)
        except (json.JSONDecodeError, OSError):
            continue
    return out


def list_gcp_subnet_cidrs(project_id: str, network: str | None = None) -> list[str]:
    """Read-only GCP query: list every subnet CIDR in the given project (optionally filtered by network)."""
    cmd = [
        "gcloud",
        "compute",
        "networks",
        "subnets",
        "list",
        f"--project={project_id}",
        "--format=value(ip_cidr_range)",
    ]
    if network:
        cmd.append(f"--network={network}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as exc:
        raise AllocationError(
            f"failed to list GCP subnets for project {project_id}: {exc.stderr}"
        ) from exc
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def list_active_labs(state_dir: Path) -> list[str]:
    """Return lab-ids whose local runtime state is not in DESTROYED."""
    if not state_dir.is_dir():
        return []
    out: list[str] = []
    for f in sorted(state_dir.glob("*.json")):
        try:
            d = json.loads(f.read_text())
            if d.get("state", "DESTROYED") != "DESTROYED":
                out.append(d["lab_id"])
        except (json.JSONDecodeError, OSError, KeyError):
            continue
    return out


def allocate_cidr(
    state_dir: Path,
    project_id: str,
    network: str | None = None,
    active_lab_limit: int = DEFAULT_ACTIVE_LAB_LIMIT,
) -> AllocationResult:
    """Allocate the next free /24 in the BBR pool.

    Raises AllocationError if the active lab limit is reached or
    if no free CIDR is available in the pool.
    """
    if active_lab_limit < 1 or active_lab_limit > HARD_CAP_ACTIVE_LABS:
        raise AllocationError(
            f"active_lab_limit={active_lab_limit} outside the allowed range "
            f"[1, {HARD_CAP_ACTIVE_LABS}]"
        )

    active = list_active_labs(state_dir)
    if len(active) >= active_lab_limit:
        raise AllocationError(
            f"active lab limit reached: {len(active)} >= {active_lab_limit}. "
            f"destroy an existing lab before allocating a new one."
        )

    in_use = set(list_local_state_cidrs(state_dir))
    in_use.update(list_gcp_subnet_cidrs(project_id, network))
    in_use.add(CONTROL_PLANE_CIDR)

    for cidr in _all_pool_cidrs():
        if cidr not in in_use:
            return AllocationResult(
                cidr=cidr,
                active_lab_count=len(active),
                in_use_cidrs=sorted(in_use),
            )

    raise AllocationError(
        f"no free CIDR available in pool {ALLOCATION_POOL_START}..{ALLOCATION_POOL_END}"
    )


def release_cidr(state_dir: Path, lab_id: str) -> bool:
    """Mark the lab state file as DESTROYED. Returns True if a state file existed."""
    path = state_dir / f"{lab_id}.json"
    if not path.is_file():
        return False
    try:
        d = json.loads(path.read_text())
        d["state"] = "DESTROYED"
        d["updated_at"] = _now_iso()
        path.write_text(json.dumps(d, indent=2, sort_keys=True))
        return True
    except (json.JSONDecodeError, OSError):
        return False


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def in_pool(cidr: str) -> bool:
    """True if cidr is inside the allocation pool (not control-plane)."""
    if cidr == CONTROL_PLANE_CIDR:
        return False
    if cidr == ALLOCATION_POOL_END:
        return True
    try:
        n = _cidr_to_int(cidr)
    except (IndexError, ValueError):
        return False
    return (
        _cidr_to_int(ALLOCATION_POOL_START) <= n <= _cidr_to_int(ALLOCATION_POOL_END)
        and cidr.endswith("/24")
    )