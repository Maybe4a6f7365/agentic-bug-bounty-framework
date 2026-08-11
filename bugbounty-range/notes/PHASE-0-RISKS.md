# Phase 0 — Unresolved Risks

Historical Phase-0 risk register referenced by `PHASE-0-REPORT.md`.
Later phase reports and ADRs are authoritative for resolutions.

| ID | Phase-0 unresolved decision | Required treatment |
|---|---|---|
| R-01 | The symbolic WireGuard private-key input had no control-plane reader in the Phase-0 skeleton. | Implement only after the relevant human gate; never persist key material in Git, state, metadata, or logs. |
| R-02 | The active-lab cap existed in the lock layer but lacked a stable CLI rejection contract. | Add a fail-closed CLI boundary and regression tests before lifecycle execution. |
| R-03 | The architecture SVG depended on an external Mermaid rendering tool. | Keep a checked-in SVG and its architecture description reviewable. |
| R-04 | The state-bucket output contains the project identifier and was marked sensitive. | Preserve least disclosure in Terraform output and operator logs. |

No item authorizes a Foundation mutation. Current resolution evidence belongs
in the later phase reports and architecture decisions.
