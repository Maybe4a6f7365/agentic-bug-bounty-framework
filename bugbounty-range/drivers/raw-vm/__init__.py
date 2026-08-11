"""raw_vm driver skeleton — Phase 0.

The driver creates a private Compute Engine VM from an
allowlisted base image and executes lab-pack-supplied
provisioning and lifecycle hooks. The driver must not
contain product-specific behaviour.

Phase 0 ships only the skeleton. Phase 1+ implements:

- validate(node_spec, node_payload)
- plan(node_spec, node_payload)
- create(node_spec, node_payload)
- bootstrap(node_spec, node_payload)
- isolate(node_spec, node_payload)
- verify(node_spec, node_payload)
- snapshot(node_spec, node_payload)
- restore(node_spec, node_payload)
- stop(node_spec, node_payload)
- start(node_spec, node_payload)
- destroy(node_spec, node_payload)
"""

from __future__ import annotations

from dataclasses import dataclass


DRIVER_ID = "raw_vm"
DRIVER_VERSION = "0.0.0-phase0"
DRIVER_CAPABILITIES = (
    "systemd",
    "package_install",
    "filesystem_hash",
    "process_state",
    "pre_snapshot_hook",
    "post_snapshot_hook",
    "pre_destroy_hook",
    "post_destroy_hook",
)


@dataclass(frozen=True)
class DriverContract:
    driver_id: str = DRIVER_ID
    version: str = DRIVER_VERSION
    capabilities: tuple[str, ...] = DRIVER_CAPABILITIES


__all__ = [
    "DRIVER_CAPABILITIES",
    "DRIVER_ID",
    "DRIVER_VERSION",
    "DriverContract",
]