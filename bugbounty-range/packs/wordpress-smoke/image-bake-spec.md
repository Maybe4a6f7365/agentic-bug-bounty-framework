# WordPress bootstrap-tools image bake specification

This document specifies a later, separately gated image build. No custom image
is created during the Phase-4A correction loop.

- Base image: `debian-12-bookworm-v20260721`
- Required baked tools: `bash`, `curl`, `sha256sum`, `minisign`, `jq`, `tar`,
  `unzstd`, and `ca-certificates`
- Tracked offline inputs:
  [`bootstrap-image-inputs.json`](bootstrap-image-inputs.json)
- The image contains only this bootstrap toolchain and its OS dependencies.
  WordPress, nginx, PHP-FPM, MariaDB, WP-CLI, and all other application-runtime
  content remain exclusively in the signed release artifact.
- Minisign 0.12 is installed from the locally verified pinned archive, never
  from a Debian repository package.
- Final image name: `bbr-debian-12-bootstrap-tools-20260727-v2`
- Intended self-link:
  `projects/your-lab-name-your-researcher-handle/global/images/bbr-debian-12-bootstrap-tools-20260727-v2`

## Verification gate

Create a temporary VM from the candidate image, connect over SSH, and run:

```bash
for tool in bash curl sha256sum minisign jq tar unzstd; do
  command -v "$tool"
done
```

Only after every lookup succeeds, write `BBR_BAKE_COMPLETE` to the VM serial
port output. A separate acceptance test must confirm that the final image exists
before any create/apply gate can use it.
