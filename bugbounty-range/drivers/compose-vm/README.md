# drivers/compose-vm

The `compose_vm` driver deploys a Docker Compose topology
on a private Compute Engine VM. The driver is loaded by
name only. The driver must not contain product-specific
behaviour. Adding a new product means adding a new pack
that supplies a Compose manifest to this driver, not
editing this directory.

## Inputs

The driver receives the validated lab pack node spec plus
the pack's `driver_payload.composelist` field. The
composelist describes services, networks, volumes, restart
policies, security options, log rotation, and resource
limits.

## Capabilities

| Capability          | Description                              |
|---------------------|------------------------------------------|
| compose             | Deploy a Compose topology.               |
| filesystem_hash     | Capture before/after filesystem hashes.  |
| container_state     | Inspect container state during scenarios. |
| process_state       | Inspect process state during scenarios.  |
| pre_snapshot_hook   | Flush Compose-managed services.           |
| post_snapshot_hook  | Restart services after snapshot.         |
| pre_destroy_hook    | Stop services and remove volumes.        |
| post_destroy_hook   | Cleanup logs and ephemeral state.        |

## Output

The driver returns the node's private IPv4, the Compose
service states, and the list of evidence paths.

## Pack manifest reference

A pack that uses this driver declares:

```yaml
driver: compose_vm
driver_payload:
  composelist: <inline Compose YAML or path>
```

The driver never inspects the product names inside the
composelist. It treats the document as opaque.