# DIRECTIVE.md gate clarification (additive)

## 21. Plan approval vs execution approval

The platform operator's `APPROVE PHASE N` phrase covers the
**plan only**. The plan includes:

- The Phase N report documenting the resources to be
  created, modified, or destroyed.
- The expected cost.
- The acceptance criteria.
- The list of required inputs.

The plan does **not** authorise `terraform apply`,
`gcloud projects create`, or any other GCP-mutating
command.

A separate phrase is required before any GCP action:

```
APPROVE PHASE N EXECUTE
```

The platform must reject any non-read-only operation
between the plan approval and the execution approval.

For Phase 1 the plan-approval phrase is `APPROVE PHASE 1`
(already issued 2026-07-25) and the execution-approval
phrase is `APPROVE PHASE 1 EXECUTE`. The execution
approval has not yet been issued.