#!/usr/bin/env bash
# pre-destroy hook for smoke-vm pack. Runs on the operator host
# before `terraform destroy`. Read-only.
set -euo pipefail
LAB_ID="${BBR_LAB_ID:?LAB_ID not provided}"
echo "pre-destroy: ${LAB_ID}"
# Nothing to do at this point in Phase 3.