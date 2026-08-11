# terraform/modules/compute-node — generic VM module

Creates a single Compute Engine VM with:

- A pinned Debian 12 base image (or an allowlisted image).
- A user-supplied machine type.
- A user-supplied disk type and size.
- Shielded VM options (Secure Boot, vTPM, Integrity
  Monitoring).
- OS Login enabled, project-wide SSH keys blocked.
- A user-supplied runtime service account.
- **No public IPv4 address.**
- The 11 lifecycle hook entrypoints the driver will use.

The module is generic. No product-specific defaults.

Inputs:

- `node_id`: lowercase identifier.
- `subnet_self_link`: where to attach the VM.
- `machine_type`, `disk_type_gb`: hardware.
- `base_image_digest` OR `base_image_family`: pin by digest
  when available.
- `runtime_service_account_email`: which SA the VM uses.
- `network_tags`: for firewall targeting.
- `lifecycle_hooks`: 11 hook entries, recorded into
  metadata for the driver to consume.
- `driver_payload`: opaque payload forwarded to the driver.

Outputs:

- `private_ip`
- `self_link`
- `lifecycle_hooks_path` (where the driver writes hook
  status)