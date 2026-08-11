#!/usr/bin/env bash
# pre-create hook for smoke-vm pack. Runs on the operator host
# (not on the lab VM). No external dependencies. Read-only.
set -euo pipefail
LAB_ID="${BBR_LAB_ID:?LAB_ID not provided}"
echo "pre-create: ${LAB_ID}"
# Nothing to do at this point in Phase 3.