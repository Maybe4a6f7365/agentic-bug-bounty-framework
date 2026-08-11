---
name: dynamic-poc-validation
description: Promote a candidate finding from observation/hypothesis to a dynamically-proven vulnerability by executing the Dynamic PoC Readiness Gate — two-principal setup, authoritative-outcome capture through an independent channel, negative control, and clean-state re-run — then emit the manifest qualification block. Load after any hunter produces a candidate hit, before writing a report. Triggers — validate a candidate finding, dynamic PoC, does this survive the readiness gate, promote observation to qualified, prove impact before report.
---

# Dynamic PoC Validation

Validate only in-scope assets, with the least privilege that reproduces the outcome. The
invariant: **a candidate is a vulnerability only when a separately-verified authoritative
outcome crosses a security boundary under attacker control.** "Endpoint returned 200,"
"handler was invoked," and "callback received a request" are not proof. This skill does not
calibrate severity (that comes after) and never fills `duplicate_preflight` (human-only).

## Method

- **Input:** a candidate carrying `record_kind: observation | hypothesis` and a static trace
  produced by a hunter skill.
- **Output:** an updated `record_kind` + `research_state` and a populated `qualification`
  block (manifest-aligned, see below), or a parked/closed record with a reason.
- **Source of truth:** this operationalizes the gate in
  [`METHODOLOGY.md`](../../METHODOLOGY.md) `## Dynamic PoC Readiness Gate` — it **executes**
  the 15 mandatory criteria as agent steps rather than restating them. Governance and field
  ownership follow [`CONTRACT.md`](../../CONTRACT.md); the schema is `OPEN_CONTRACT.yaml`.

## Validation procedure

Run in order. Each step names the `METHODOLOGY.md` `## Additional failure modes to detect`
it defends against.

1. **Confirm scope and method.** The asset and technique are in the program's policy
   allowlist (guards *the policy-boundary failure*).
2. **Establish principal separation.** Two controlled accounts/tenants/tokens; label every
   object, session, and token by owner. "Whose authorization produced the result?"
   (guards *the self-test artifact* and *the victimless impact claim*).
3. **Show attacker control.** State the exact attacker-controlled input and the minimum
   privilege required (guards *the privilege-equivalence problem*).
4. **Trigger runtime execution** against the live in-scope path — not a static trace and not a
   sandbox generalized to production (guards *the environmental overgeneralization* and
   *the reachability-to-impact leap*).
5. **Capture the authoritative outcome through an independent channel** — never the initiating
   response (guards *the downstream-control blind spot*). Fallback order: separate
   authenticated fetch as the victim principal → server-side audit/access log → admin-panel
   state query → timing/side-channel differential. Use the first channel that provides
   authoritative evidence the boundary was crossed.
6. **Run the negative control.** A nearby non-exploit case must fail as expected, proving the
   success is meaningful (guards *the defense-in-depth confusion*).
7. **Test the primary and downstream controls.** Name the actual authorization/trust boundary
   and show it fails; confirm no server-side validation, token check, or final consumer
   blocks the outcome.
8. **Clean-state re-run, ≥2 reproductions.** Repeat from a fresh state to exclude a self-test
   artifact — the exact failure that sank `PL-F01` (a forged token accepted only because the
   attacker was also the subject).
9. **Bound impact.** Separate the proven result from the theoretical maximum (guards *the
   chain-of-assumptions problem* — build the assumption ledger for multi-step chains).
10. **Preserve redacted evidence.** Requests, responses, timestamps, versions/hashes, and
    cleanup steps; replace tokens, PII, and internal hosts with `<REDACTED>`.

## Gate verdict → manifest output

Map the five `### Gate result` outcomes to v5 manifest transitions
(`record_kind_enum`, `research_state_enum`, `closure_reason_enum`):

| Gate result | `record_kind` | `research_state` | Extra |
|---|---|---|---|
| Pass | `vulnerability` | `qualifying` → `report_ready` only if authoritative outcome **and** impact are verified | populate `qualification` |
| Conditional pass | `vulnerability` | `qualifying` | document the inapplicable criterion |

A submittable proven finding is always `record_kind: vulnerability` — that is the only kind
`OPEN_CONTRACT.yaml` counts toward submission. `positive_verification` is a
confirmation/reproduction record kind and is listed in `excluded_record_kinds`; it never counts
as a submission, so it is not the Pass output here.
| Fail—continue research | `hypothesis` | `research` | record the missing runtime evidence |
| Fail—close | (unchanged) | `closed` | `closure_reason` from enum (`control_held`, `intended_behavior`, `no_impact`, `privilege_equivalent`, `version_mismatch`, `out_of_scope`) |
| Parked | (unchanged) | `parked` | `unblock_condition` (never a `closure_reason`) |

On Pass, write the `qualification` block (all seven `qualification_required_fields`):

```json
"record_kind": "vulnerability",
"research_state": "qualifying",
"qualification": {
  "state": "qualified",
  "strongest_proven_claim": "As B's tenant, a GET issued with A's token returned B's private object",
  "affected_principal": "principal B (separate tenant)",
  "primary_control": "object-level authorization on GET /api/v1/orgs/{id}/records",
  "authoritative_result": "independent re-fetch as B confirmed A's object was mutated",
  "negative_controls": ["random non-owned id returns 403", "unauth request returns 401"],
  "dynamic_reproductions": 2
}
```

`report_ready` requires `evaluation_gates.qualification`: a static trace is **not** dynamic
proof; report-ready needs an authoritative outcome and verified impact. After writing, run
`bash tools/validate-manifests.sh` to confirm schema compliance.

## Stop conditions (verified negatives)

Each stop condition below carries one of the 12 categories from
[`skills/references/negative-control-taxonomy.md`](../references/negative-control-taxonomy.md).
Apply ALL applicable labels. Never promote a candidate that triggers any category below.

**Decision split (apply separately, never collapse):**
- `technically_vulnerable`: does a separately-verified outcome actually cross a boundary?
- `in_scope`: does the program's policy cover this asset and method?
- `program_reportable`: does the demonstrated impact meet the program's threshold?
A finding can be yes/yes/no, yes/no/yes, etc. Do not promote on `technically_vulnerable` alone.

- `[theoretical_without_oracle]` No independent authoritative channel confirmed the outcome;
  the evidence is the initiating response only, or cached/self data mistaken for victim data.
  `[technical_placeholder]`
- `[technically_not_vulnerable]` The `200`/success is an error envelope or the returned
  identifier grants no access; the boundary was never crossed. `[technical_placeholder]`
- `[missing_attacker_control]` The value is server-derived; the attacker cannot influence the
  input that produced the outcome. `[technical_placeholder]`
- `[control_exists_elsewhere]` A downstream server-side control, signed URL, or token check
  neutralizes the outcome even though a client accepted the input. `[technical_placeholder]`
- `[expected_product_behavior]` The action is intended/shared functionality, not an
  authorization failure. `[technical_placeholder]`
- `[real_but_below_program_impact_threshold]` The outcome affects only attacker-owned data or
  exposes non-sensitive material — close or downgrade. `[technical_placeholder]`

These entries are `[technical_placeholder]`: this is a methodology-seeded process skill, not a
corpus-mined hunter, so the taxonomy is their source of authority until curated negatives back
them.

## Anti-patterns

- Never set `record_kind: vulnerability` / `research_state: report_ready` without an
  independent authoritative-outcome channel and ≥2 clean-state reproductions.
- Never fill `duplicate_preflight` — that field is human-only; hand off via
  [`duplicate-preflight`](../duplicate-preflight/SKILL.md).
- Never let two agents agreeing substitute for reproduction (*the AI consensus illusion*):
  prefer independent reproduction over textual agreement.
- Do not calibrate or inflate severity here — validation proves the claim; severity follows
  from the proven result in a later step.
- Do not skip the clean-state re-run to "save time"; it is the cheapest defense against a
  self-test artifact.

## Minimal reproducer

```python
import os, requests

# Two separated principals. A = attacker, B = victim (both controlled, in scope).
A = {"Authorization": f"Bearer {os.environ['A_TOKEN']}"}
B = {"Authorization": f"Bearer {os.environ['B_TOKEN']}"}
victim_obj = os.environ["B_OBJECT_URL"]      # object owned exclusively by B

# 1) Attacker attempts the cross-boundary action.
attack = requests.get(victim_obj, headers=A, timeout=15)

# 2) Authoritative check via an INDEPENDENT channel, as B — not the attack response.
truth = requests.get(victim_obj, headers=B, timeout=15)

crossed = attack.status_code == 200 and attack.json() == truth.json()
print("VERDICT:", "PASS (boundary crossed)" if crossed else "FAIL (no proof)")
# A 200 to the attacker alone is NOT proof; the independent B-side check is the oracle.
```

## Evidence basis and limits

Methodology-derived from [`METHODOLOGY.md`](../../METHODOLOGY.md) `## Dynamic PoC Readiness
Gate`, `## The "should I report this?" decision tree`, and `## Additional failure modes to
detect`; not corpus-mined. `PL-F01` is a real logged self-test-artifact failure
(`METHODOLOGY.md`). Manifest fields are authoritative from `OPEN_CONTRACT.yaml`.

## AI-assisted augment (NahamSec seed)

Transferable technique from Ben Sadeghipour (NahamSec), public PlexTrac "Homework for Hackers"
webinar (`Ue-OIJoM0bA`); see
[`knowledge-sources/creators/03-nahamsec.md`](../../knowledge-sources/creators/03-nahamsec.md).
Guardrail: model output is a hypothesis, not evidence — the target oracle decides; never paste
unsanitized target data, tokens, or evidence into an unapproved model
(`nahamsec-ai-sanitize-before-sharing`, CWE-200).

- **Adversarial second look — assign the model the role of disproof
  (`nahamsec-ai-context-second-look`).** Give an approved model the sanitized evidence and ask
  it to *break* the finding: enumerate alternative explanations, downstream controls that
  might still hold, self-test-artifact angles, and privilege-equivalence. Treat each as a
  hypothesis to test against the target, not a verdict. This operationalizes METHODOLOGY's
  "assign one reviewer the explicit role of disproof" and guards the AI consensus illusion —
  run one hunter and one killer, never two confirmers.

## Version boundaries

Null — this is a process skill, not version-bound. Before promoting, confirm the deployed
version matches what was tested (guards *the version mismatch*): link static artifacts to live
requests and re-test immediately before submission.
