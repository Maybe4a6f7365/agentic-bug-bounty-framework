"""Driver loading skeleton.

Phase 0. Drivers are loaded by name only. The platform
refuses to load Python code from outside the repository.

Phase 1+ implementation will:

- Import drivers/drivers/<driver-id>/__init__.py dynamically.
- Validate the driver's manifest against
  schemas/driver-interface.schema.json.
- Surface the driver's 11 lifecycle methods to the control
  plane.

No product-specific code is permitted here.
"""

from __future__ import annotations

from dataclasses import dataclass


KNOWN_DRIVERS = ("compose_vm", "raw_vm")


@dataclass(frozen=True)
class DriverManifest:
    driver_id: str
    version: str
    capabilities: tuple[str, ...]


class DriverError(Exception):
    """Raised when a driver is unknown or fails to load."""


def is_known_driver(driver_id: str) -> bool:
    return driver_id in KNOWN_DRIVERS


__all__ = ["KNOWN_DRIVERS", "DriverError", "DriverManifest", "is_known_driver"]