# BugBountyRange Phase 1 — Corrected Foundation Plan

**Date:** 2026-07-26 (Europe/Berlin)
**Status:** configuration committed for review; no GCP mutation performed
**Execution gate:** `APPROVE PHASE 1 EXECUTE`

## Inputs

Confirmed:

- `GCP_PROJECT_ID=your-lab-name-your-researcher-handle`
- `BILLING_ACCOUNT_ID=012073-B3D05B-0BFF74`
- `GCP_REGION=europe-west3`
- `GCP_ZONE=europe-west3-a`
- `PLATFORM_OPERATOR_LABEL=your-researcher-handle`
- `LAB_OWNER_LABEL=your-researcher-handle`
- `ACTIVE_LAB_LIMIT=1`
- `BUDGET_EUR_EQUIVALENT=245`
- `CREDIT_EXPIRY_DATE=2026-09-27`

Still required before execution:

- exactly one existing parent: `GCP_ORGANIZATION_ID` or `GCP_FOLDER_ID`

The read-only discovery candidate `871355342313` is **not approved** and is not embedded in Terraform.

## Planned resources

The current configuration declares ten Phase-1 resources:

1. `google_project.bbr`
2. `google_billing_budget.platform`
3. `google_storage_bucket.state`
4. `google_project_service.foundation["billingbudgets.googleapis.com"]`
5. `google_project_service.foundation["cloudbilling.googleapis.com"]`
6. `google_project_service.foundation["cloudresourcemanager.googleapis.com"]`
7. `google_project_service.foundation["compute.googleapis.com"]`
8. `google_project_service.foundation["iam.googleapis.com"]`
9. `google_project_service.foundation["iap.googleapis.com"]`
10. `google_project_service.foundation["storage.googleapis.com"]`

No VM, VPC, subnet, firewall, external IP, load balancer, snapshot, or bastion resource is active.

## Corrections applied

- `auto_create_network = false` prevents GCP's default VPC, subnet, and firewall creation.
- Project placement requires exactly one existing organization or folder; this module creates no folder.
- Label values use only GCP-compatible characters.
- `expires_on` uses the operator-supplied date rather than `timestamp()`.
- The budget filter uses the project number.
- `billingbudgets.googleapis.com` is explicitly enabled.
- The budget is documented as a monthly alert budget, not a hard cap.
- The state bucket uses uniform bucket-level access, enforced public-access prevention, versioning, and retention of five newer versions.
- Backend interpolation was removed. Phase 1 bootstraps with local state and migrates only after the bucket exists.

## Backend bootstrap

The initial apply, when separately approved, uses local state. After the bucket exists, add a literal partial backend block:

```hcl
terraform {
  backend "gcs" {}
}
```

Then migrate using literal command-line configuration:

```bash
terraform init -migrate-state \
  -backend-config="bucket=bbr-state-your-lab-name-your-researcher-handle" \
  -backend-config="prefix=foundation"
```

A second plan must report no changes.

## Required pre-apply verification

Run from `terraform/foundation` after supplying the approved parent:

```bash
terraform fmt -check
terraform init -backend=false -input=false
terraform validate
terraform plan -input=false -no-color \
  -var='gcp_project_id=your-lab-name-your-researcher-handle' \
  -var='billing_account_id=012073-B3D05B-0BFF74' \
  -var='gcp_organization_id=<APPROVED_ORG_ID>' \
  -var='platform_operator_label=your-researcher-handle' \
  -var='lab_owner_label=your-researcher-handle' \
  -var='credit_expiry_date=2026-09-27'
```

The saved plan must be inspected to confirm:

- the exact resource count from Terraform itself;
- no compute instance, network, subnetwork, firewall, or address resource;
- no deletion or modification outside the foundation root;
- no secret or private-key path in configuration or output.

No successful Terraform plan is claimed by this document. The current execution environment used for this correction did not contain a Terraform binary, so execution remains blocked until the commands above run successfully.

## Acceptance criteria

Phase 1 is complete only when:

- an approved project parent is supplied;
- the real Terraform plan is reviewed and approved;
- apply succeeds without creating network or compute resources;
- billing linkage and all seven APIs are verified;
- the project has no default VPC, firewall rules, or subnets;
- the billing budget exists and its project-number filter is verified;
- the state bucket protections are verified;
- state is migrated to GCS and the second plan is idempotent;
- the post-apply cost is recorded and remains within the approved budget;
- configuration, plan, and outputs contain no secret or private-key path;
- the Phase-1 report records commands, redacted outputs, cost, deviations, and commit SHA.

## Stop

No `terraform apply`, GCP API mutation, project creation, billing change, service enablement, or bucket creation was performed while preparing this correction.

Do not execute until the parent is explicitly approved and the exact phrase below is issued after reviewing a real Terraform plan:

```text
APPROVE PHASE 1 EXECUTE
```
