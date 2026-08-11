# drivers/raw-vm

The `raw_vm` driver creates a private Compute Engine VM
from an allowlisted base image and executes lab-pack-
supplied provisioning and lifecycle hooks. The driver is
designed for software that requires systemd, native
packages, custom operating-system configuration, or
cannot run correctly in containers.

The driver must not contain product-specific behaviour.

## Inputs

The driver receives the validated lab pack node spec plus
the pack's `driver_payload` field, which describes
packages, systemd units, and provisioning scripts.

## Capabilities

| Capability          | Description                              |
|---------------------|------------------------------------------|
| systemd             | Manage systemd units.                    |
| package_install     | Install OS packages.                     |
| filesystem_hash     | Capture before/after filesystem hashes.  |
| process_state       | Inspect process state during scenarios.  |
| pre_snapshot_hook   | Flush state before snapshot.             |
| post_snapshot_hook  | Resume after snapshot.                   |
| pre_destroy_hook    | Stop services and remove packages.       |
| post_destroy_hook   | Cleanup logs and ephemeral state.        |

## Output

The driver returns the node's private IPv4, the systemd
unit states, and the list of evidence paths.

## Pack manifest reference

A pack that uses this driver declares:

```yaml
driver: raw_vm
driver_payload:
  packages: [pkg1, pkg2, ...]
  systemd_units: [unit1, unit2, ...]
  provisioning_scripts: [scripts/prep.sh, ...]
```

The driver never inspects the product names. It treats
the document as opaque.