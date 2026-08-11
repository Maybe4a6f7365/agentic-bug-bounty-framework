# Setup folder

Mobile dynamic-testing setup. The single process is the **cloud AVD rig**.

## Contents

- **`gcp-avd/`** — the mobile dynamic-testing process: a rooted Android 14 emulator
  on a GCP VM with Frida + Caido. See
  [`gcp-avd/README.md`](./gcp-avd/README.md) for provisioning and
  [`gcp-avd/RESEARCHER-GUIDE.md`](./gcp-avd/RESEARCHER-GUIDE.md) for the testing
  workflow, access, and TLS-interception steps. `gcp-avd/bringup.sh` is the
  idempotent bring-up script.

Keep local-only artifacts (Frida scripts with target data, Caido configs/CA material,
APKs, tokens, captures) out of Git — see `.gitignore` and the research policy.
