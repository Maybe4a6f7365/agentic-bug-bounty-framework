# BugBountyRange Phase 1 — Closeout Report

**Date:** 2026-07-26 (Europe/Berlin)
**Operator:** your-researcher-handle
**Phase status:** CLOSED (Phase 1 complete)
**Remote HEAD at start:** `7fd1ee778f2917f3cc286d9de3f6b016ac0afdbf`
**Phase-1 closeout content commit:**
`5c7037f3f6187e62cab28a1910ead767374d3ef4`

**Subsequent report-metadata commits:**
`25a34a0a81f35e5bca8699c478d9aacafefe1c51`
`758387b9d86d7b8157d33c5c8a71d9b530e1c29c`
`7e5437cc4b34c4ad67ab950387efe306b48bd64e`

The authoritative final repository state is identified by
the annotated Git tag `bbr-phase1-closed`, created after
this report cleanup. A commit cannot truthfully embed its
own SHA because changing the file changes the commit hash.

---

## 1. Project identifiers

| Field | Value |
|---|---|
| `GCP_PROJECT_ID` | `your-lab-name-your-researcher-handle` |
| `GCP_PROJECT_NUMBER` | `699562887886` |
| `GCP_ORGANIZATION_ID` | `871355342313` (`kontakt-org`) |
| `GCP_REGION` | `europe-west3` |
| `GCP_ZONE` | `europe-west3-a` |
| `BILLING_ACCOUNT_ID` | `012073-B3D05B-0BFF74` |
| `STATE_BUCKET_NAME` | `bbr-state-your-lab-name-your-researcher-handle` |

Folder verification (`gcloud resource-manager folders list --organization=871355342313`):
**0 active folders.** No `google_folder` resource was created.

## 2. Phase 1 execution sequence

Phase 1 was executed in two applies because the initial
plan failed on `google_billing_budget.platform`. Each
step was gated by an explicit `APPROVE PHASE 1 EXECUTE`
phrase and proceeded with the pre-validated plan file.

### 2.1 Initial apply (`APPROVE PHASE 1 EXECUTE`)

- Initial plan file: `/tmp/bbr-phase1-final.tfplan`
- SHA-256: `4d1da9adbb9d2eba86ad23f8ce731d1711be8de242ccbf6ec6a537283ab01712`
- Resource count: `10 to add, 0 to change, 0 to destroy`
- Outcome: **partial apply**
  - 9 resources created successfully
  - 1 resource failed: `google_billing_budget.platform`

### 2.2 Failure analysis

Error:

```
googleapi: Error 403: Your application is authenticating
by using local Application Default Credentials. The
billingbudgets.googleapis.com API requires a quota
project, which is not set by default.

ErrorInfo:
  domain: googleapis.com
  metadata:
    consumer: projects/32555940559
    service: billingbudgets.googleapis.com
  reason: SERVICE_DISABLED
```

Key finding: the **Consumer project number** in the error
(`32555940559`) does **not** match the new project number
(`699562887886`). The `billingbudgets.googleapis.com` API
was correctly enabled on the new project, but the budget
request was routed through the local ADC quota project
(`redroid-research`) rather than the new project.

### 2.3 Remediation

- Remediation commit SHA on `origin/main`:
  `7fd1ee778f2917f3cc286d9de3f6b016ac0afdbf`
- Remediation diff (2 files, +18 / -0):
  - `platform/your-lab-name/terraform/foundation/providers.tf`
    (added `provider "google" { alias = "billing", user_project_override = true, billing_project = var.gcp_project_id }`)
  - `platform/your-lab-name/terraform/foundation/billing.tf`
    (added `provider = google.billing` to the budget resource)
- Remediation plan file: `/tmp/bbr-phase1-remediation.tfplan`
- SHA-256: `093082adaa06b9a0ff6b1f821b31eafb82a93a0c8292e22aa245fe7846d43bd1`
- Resource count: `1 to add, 0 to change, 0 to destroy`
  (only `google_billing_budget.platform`)
- Outcome: budget created in
  `billingAccounts/012073-B3D05B-0BFF74/budgets/9013317b-eb31-4698-9649-b389913c422d`

## 3. Final state (10 resources)

```
google_billing_budget.platform
google_project.bbr
google_project_service.foundation["billingbudgets.googleapis.com"]
google_project_service.foundation["cloudbilling.googleapis.com"]
google_project_service.foundation["cloudresourcemanager.googleapis.com"]
google_project_service.foundation["compute.googleapis.com"]
google_project_service.foundation["iam.googleapis.com"]
google_project_service.foundation["iap.googleapis.com"]
google_project_service.foundation["storage.googleapis.com"]
google_storage_bucket.state
```

(7 `google_project_service.foundation[*]` resources are
shown by `terraform state list` as 7 separate addresses but
are stored in the state file as 1 resource type with 7
instances.)

## 4. State-bucket safety flags

From `terraform state show google_storage_bucket.state`:

| Flag | Value |
|---|---|
| `uniform_bucket_level_access` | `true` |
| `public_access_prevention` | `"enforced"` |
| `versioning.enabled` | `true` |
| `force_destroy` | `false` |
| `location` | `EU` |
| Labels | `platform=your-lab-name`, `operator=your-researcher-handle`, `owner=your-researcher-handle` |
| Lifecycle rule | `num_newer_versions = 5 → Delete` |

## 5. Compute / network / firewall absence

| Check | Command | Result |
|---|---|---|
| Networks | `gcloud compute networks list --project=your-lab-name-your-researcher-handle` | `Listed 0 items.` |
| Subnets | `gcloud compute networks subnets list --project=your-lab-name-your-researcher-handle` | `Listed 0 items.` |
| Firewalls | `gcloud compute firewall-rules list --project=your-lab-name-your-researcher-handle` | empty |
| Instances | `gcloud compute instances list --project=your-lab-name-your-researcher-handle` | empty |
| Project auto_create_network | `google_project.bbr.auto_create_network` | `false` |

## 6. GCS backend migration

Performed with explicit `APPROVE PHASE 1 EXECUTE`
approval:

- Edit: `terraform/foundation/providers.tf` added
  `backend "gcs" {}` (partial block, no variable
  interpolation).
- Migration command:

  ```
  terraform init -migrate-state -force-copy \
    -backend-config="bucket=bbr-state-your-lab-name-your-researcher-handle" \
    -backend-config="prefix=foundation"
  ```

- Outcome: `Successfully configured the backend "gcs"`.
- Remote state object: `gs://bbr-state-your-lab-name-your-researcher-handle/foundation/default.tfstate`
- Local pre-migration backup:
  `/tmp/bbr-phase1-local-state-before-gcs.json` (mode 0600)
- Local post-migration read:
  `/tmp/bbr-phase1-remote-state-after-gcs.json` (mode 0600)

Note: the local-vs-remote state files differ in the
`serial` field (local=13, remote=14) because Terraform
re-serialised the state when re-writing to the GCS
backend. All 4 resource entries (10 addresses) and the
`lineage` value are unchanged.

No state file was committed to the repository. No
state file was written into the working tree.

## 7. Idempotency plan

After the GCS backend migration, a fresh plan with
`-refresh=true` was generated against the GCS backend.

- Plan file: `/tmp/bbr-phase1-idempotency.tfplan`
- SHA-256: `db7e21f3773e55379f0810387c332347c792a054d70d2dade5615f81d1f01b35`
- Output: `No changes. Your infrastructure matches the configuration.`
- 0 to add, 0 to change, 0 to destroy.

The plan file is not committed (per Operator directive).

## 8. Budget verification (gcloud, independent path)

```
gcloud \
  --billing-project=your-lab-name-your-researcher-handle \
  billing budgets list \
  --billing-account=012073-B3D05B-0BFF74 \
  --filter='name:9013317b-eb31-4698-9649-b389913c422d'
```

Yields:

```yaml
name: billingAccounts/012073-B3D05B-0BFF74/budgets/9013317b-eb31-4698-9649-b389913c422d
displayName: BugBountyRange monthly alert budget
budgetFilter:
  projects:
  - projects/699562887886
amount:
  specifiedAmount:
    currencyCode: EUR
    units: '245'
```

The `gcloud billing budgets list` without
`--billing-project=...` correctly fails with
`SERVICE_DISABLED` against the ADC quota project
(`redroid-research`), which confirms that the Terraform
provider's `billing_project` routing is necessary and
correct.

## 9. Cost status

| Item | Cost |
|---|---|
| GCP project | €0.00 |
| 7 enabled APIs (in new project) | €0.00 |
| `google_storage_bucket.state` (empty in Phase 1) | < €0.01 / month (bucket-metadata overhead, not strictly €0.00) |
| `google_billing_budget.platform` | €0.00 (alert mechanism, not a hard cap) |

Total Phase 1 GCP cost: ~€0.00.
Internal platform stop cap (default €120) is unchanged
and not enforced in Phase 1.

## 10. Secret scan

The scan checked for private-key material, key-generation
commands, API-token assignments, private-key filenames,
concrete operator secret paths, and Hermes-internal cache
paths.

Result for the scanned Phase-1 configuration and plan
artifacts: `total findings: 0`.

The report intentionally does not reproduce the literal
patterns or concrete paths, so that the report itself
does not create false positives in future repository
scans.

The only WireGuard-secret reference in the platform tree
is the symbolic `BBR_WG_PRIVATE_KEY_FILE` environment
variable name. No concrete private-key path or
private-key content is committed anywhere in the
platform tree.

## 11. Deviations from the Phase 1 plan

- **Two-step apply** (initial plan + remediation plan)
  was required because the budget resource failed with
  `SERVICE_DISABLED` for `billingbudgets.googleapis.com`
  on the first apply. Root cause: the default Google
  provider routed the budget API call through the local
  ADC quota project (`32555940559`) rather than the new
  project (`699562887886`). The fix is the new
  `provider "google" { alias = "billing", billing_project = var.gcp_project_id }`
  block. After the fix, exactly 1 resource was added.
- The label value `your-researcher-handle` is documented as a
  stable operator-alias, not a GCP, Cloud-Identity, or
  IAM identity. It is used exclusively as a label value
  for organisation, filtering, and cost attribution.
- `gcloud billing budgets list` without explicit
  `--billing-project` cannot access the budget because
  the ADC quota project lacks the API enablement. This
  is a known limitation of `gcloud` against budgets, not
  a configuration defect.

No other deviations. No Compute, Network, Firewall, VPC,
Subnet, Bastion, or Public-IP resources were created
beyond the 10 planned Phase 1 resources.

## 12. Stopping point

**Phase 1 is closed.** No `terraform apply` runs after
this report is committed. No GCP resources are created,
modified, or destroyed.

The next required human phrase for Phase 2 is:

```
APPROVE PHASE 2
```

This phrase is not yet issued. Phase 2 work does not
start without it.

---

## Closing notes

- Original working tree (`/home/admin/Research-Repo`)
  was **not** touched at any point.
- Worktree used: `/home/admin/Research-Repo-phase1-clean`.
- Terraform version: `v1.9.8`.
- All Phase-1 implementation and closeout edits were limited to:
  - `terraform/foundation/providers.tf`
  - `terraform/foundation/billing.tf`
  - `notes/PHASE-1-REPORT.md`
