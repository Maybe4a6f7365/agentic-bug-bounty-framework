#!/usr/bin/env bash
# post-create hook for smoke-vm pack. Phase 3: read-only.
# In Phase 3 the readiness marker is written by the VM's
# egress-free startup script (templatefile), which is part
# of the Terraform plan. This hook performs read-only
# verification only: it checks that /var/lib/bbr/ready exists
# on the VM via IAP-tunneled SSH. It does NOT write anything.
set -euo pipefail
LAB_ID="${BBR_LAB_ID:?LAB_ID not provided}"
NODE_NAME="${BBR_NODE_NAME:?NODE_NAME not provided}"
PROJECT="${BBR_GCP_PROJECT:?BBR_GCP_PROJECT not provided}"
ZONE="${BBR_GCP_ZONE:?BBR_GCP_ZONE not provided}"

echo "post-create (read-only): ${LAB_ID} node=${NODE_NAME}"

gcloud compute ssh "${NODE_NAME}" \
  --project="${PROJECT}" \
  --zone="${ZONE}" \
  --tunnel-through-iap \
  --command='test -f /var/lib/bbr/ready && cat /var/lib/bbr/ready'