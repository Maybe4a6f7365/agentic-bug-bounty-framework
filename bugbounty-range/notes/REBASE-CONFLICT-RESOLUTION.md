# Rebase conflict resolution

The active rebase of the three local commits onto `origin/main` was resolved
file by file. `HEAD` in the conflict entries was the newer remote rebase base;
the incoming side was local commit `8ea2271`.

| Conflict file | Resolution |
|---|---|
| `.gitignore` | Combined both Python/runtime-state ignore sets and removed duplicate `__pycache__` and `*.pyc` entries. Remote-only `*.pyo` and `/state/` protections were retained. |
| `DIRECTIVE.md` | Retained the newer remote directive in full because it already contains the local split plan/execute gate and extends it with the authoritative Phase 2/3 lifecycle, verify/destroy idempotency, acceptance matrix, and later amendments. The local amendment remains separately preserved in `DIRECTIVE-AMENDMENT-21.md`. |
| `notes/PHASE-1-PLAN.md` | Used the corrected, newer remote plan, including the unapproved-parent warning, seven-API set, local-state bootstrap, and idempotent second plan. Added the still-valid local acceptance checks for absence of default networking, budget verification, cost recording, secret-path exclusion, and report commit SHA. |
| `terraform/foundation/apis.tf` | Preserved the remote `for_each` service resource and centralized its API set in the local `locals.tf`, avoiding a duplicate local block. The union includes all remote APIs plus `billingbudgets.googleapis.com`, so the complete seven-API acceptance requirement remains enforceable. |
| `terraform/foundation/bastion.tf` | Retained the current remote Phase-2 bastion implementation: pinned image, Shielded VM, OS Login, blocked project SSH keys, locally generated WireGuard private key, dedicated service account, and least-privilege IAM. The local Phase-1 comment-only stub was obsolete and added no hardening beyond those controls. |
| `terraform/foundation/billing.tf` | Retained the newer billing provider, numeric project-number filter, forecast thresholds, and explicit API dependencies. Added the local clarification that a GCP budget is an alert and lifecycle stop-cap enforcement is separate; the remote monthly configuration was preferred over the local misleading credit-expiry calendar claim. |
| `terraform/foundation/firewall.tf` | Retained remote's restrictive implemented rules: WireGuard UDP/51820 only from approved CIDRs, SSH only through the IAP CIDR, firewall logging, and the single WireGuard return route. The local Phase-1 stub was superseded by these stricter real resources. |
| `terraform/foundation/network.tf` | Retained remote's custom-mode regional VPC and control-plane subnet with flow logs and Private Google Access, plus the documented reserved ranges and absence of NAT/peering/per-lab allocation. Local naming/range locals were preserved once in `locals.tf` to avoid duplicate declarations. |
| `terraform/foundation/outputs.tf` | Kept every remote Phase-2 project, budget, network, bastion, and WireGuard output. Added the valid local hardened-bucket self-link, enabled-API inventory, and budget display-name outputs, with sensitive infrastructure identifiers still marked sensitive. |
| `terraform/foundation/project.tf` | Retained remote's exactly-one organization/folder parent support, GCP-compatible `expires_on` normalization, `auto_create_network = false`, and `prevent_destroy`. These are safer than the local fixed-organization assumption, raw hyphenated label date, and missing destroy guard. |
| `terraform/foundation/providers.tf` | Retained the remote bootstrap-safe default provider and dedicated billing provider with quota-project override, together with the literal partial GCS backend. This preserves the local no-interpolation backend rule while keeping the newer billing-routing hardening. |
| `terraform/foundation/state-bucket.tf` | Preserved all shared controls: no force destroy, uniform bucket-level access, enforced public-access prevention, versioning, five-newer-version retention, owner/operator labels, and dependency on the storage API. The precise remote dependency was chosen over the broader local all-services dependency. |
| `terraform/foundation/variables.tf` | Retained all remote validations, nullable exactly-one parent inputs, safer `europe-west3-a` default, neutral owner default, and Phase-2 bastion inputs. Added the local WireGuard intent as an enforced valid `/32` CIDR validation; less restrictive local variants were rejected. |

No conflict was resolved with a repository-wide strategy or a file-level
`ours`/`theirs` checkout. The two later commits rebased without conflicts.
