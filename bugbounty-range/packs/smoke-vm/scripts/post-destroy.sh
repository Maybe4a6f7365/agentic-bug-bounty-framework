#!/usr/bin/env bash
# post-destroy hook for smoke-vm pack. Runs after `terraform
# destroy` reports success. Read-only with respect to the lab.
set -euo pipefail
LAB_ID="${BBR_LAB_ID:?LAB_ID not provided}"
echo "post-destroy: ${LAB_ID}"
# Nothing to do at this point in Phase 3.