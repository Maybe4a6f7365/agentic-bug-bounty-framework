---
name: scope-policy-qualification
description: Resolve the two non-technical gates — in_scope (asset + technique authorized) and program_reportable (impact meets the program's threshold and is not achieved via an excluded method) — by reading the live program policy and the target contract.yaml, building the in-scope allowlist, setting required identification headers and the rate budget, and gating handoff. Load at target entry (before recon/testing) and again immediately before submission. Triggers — scope check, is this in scope, policy qualification, program_reportable, can I test this asset, pre-submission policy re-review.
---

# Scope & Policy Qualification

The live published program policy governs; the target `contract.yaml` mirrors it and the live
policy wins whenever it is newer or stricter (see
[`SECURITY-RESEARCH-POLICY.md`](../../SECURITY-RESEARCH-POLICY.md) "Authorization and scope
precedence"). **Public reachability is not permission.** If scope, ownership, authorization, or
policy interpretation is uncertain, stop until a human confirms it. This skill resolves *scope*
and *reportability* — not technical exploitability (that is
[`dynamic-poc-validation`](../dynamic-poc-validation/SKILL.md)) and not novelty (that is
[`duplicate-preflight`](../duplicate-preflight/SKILL.md)).

## Method

This skill owns two of the three independent labels from
[`skills/references/negative-control-taxonomy.md`](../references/negative-control-taxonomy.md):
`in_scope` and `program_reportable`. It runs at two points:

- **Target entry (before recon/testing):** Gate 1 — is the asset **and** the technique
  authorized?
- **Before `report_ready` / handoff, and again immediately before submission:** Gate 2 — does
  the demonstrated impact meet the program's threshold, and is it *not* achieved through an
  excluded method? Re-read the live policy (it may have changed).

`contract.yaml` owns scope, policy, and authorization (`OPEN_CONTRACT.yaml`
`field_ownership.target_contract`). This skill reads it and refreshes only the policy-freshness
snapshot in `pre_scan.yaml`.

## Scope qualification (Gate 1 — target entry)

1. **Read the live program policy and `contract.yaml` `program_scope`** (`in_scope` /
   `out_of_scope`). Where they disagree, the live policy wins if newer or stricter; if the
   difference is material or unclear, stop for a human.
2. **Build the in-scope allowlist** — the exact assets and the permitted techniques. A host or
   endpoint surfaced by [`recon`](../recon/SKILL.md) is *not* authorized until it matches this
   allowlist.
3. **Set the required identification headers** from the program's engagement rules (see the
   "HackerOne engagement rules" table in the repo root `README.md`; each program specifies its
   own, e.g. `X-Bug-Bounty` / `X-HackerOne-Handle` / researcher `User-Agent`) and the rate
   budget (≤1–2 aggregate req/s, ≥1s between API calls, no concurrency, kill switch).
4. **Record the exclusions** relevant to the classes you will hunt: prohibited methods
   (DoS/stress/social-engineering), no third-party/cloud/adjacent-infra pivot, data
   minimization.
5. **Refresh policy freshness in `pre_scan.yaml`** — update `policy_last_reviewed` and
   `policy_changes_since_review` only. Never touch `asset_fingerprint` or
   `known_findings_count` (contract-bound to the manifest).

## Reportability qualification (Gate 2 — before report_ready / handoff)

- Confirm the **demonstrated** impact meets the program's severity/reward threshold (a VDP may
  accept a valid report without paying; an informational bar may exclude it).
- Confirm the asset **and** technique are still covered, and the impact is not obtained via an
  excluded method (automated scanning, brute force, DoS, real user data).
- Gate the handoff on `contract.yaml` `handoff_policy.pre_flight_required_for_handoff`
  (`grading_complete`, `policy_re_reviewed`, `duplicate_preflight_completed` all true) and
  `who_may_submit_to_h1`.
- Set `policy_re_reviewed: true` only after the final live-policy re-read.

## Output (contract / manifest alignment)

Sets the two non-technical flags in `METHODOLOGY.md` `## Final submission contract`:
`scope_confirmed`, `testing_method_permitted`, and `policy_re_reviewed`. Refreshes the
`pre_scan.yaml` policy fields above. It does **not** set `technically_vulnerable` (owned by
`dynamic-poc-validation`) or `duplicate_preflight` (human-only — `duplicate-preflight`).

## Stop conditions (verified negatives)

Each stop condition below carries one of the 12 categories from
[`skills/references/negative-control-taxonomy.md`](../references/negative-control-taxonomy.md).
Apply ALL applicable labels. Never advance a candidate that triggers any category below.

**Decision split (apply separately, never collapse):**
- `technically_vulnerable`: is the code actually exploitable? *(not this skill — see dynamic-poc-validation)*
- `in_scope`: does the program's policy + `contract.yaml` cover this asset **and** technique?
- `program_reportable`: does the demonstrated impact meet the program's threshold?
A finding can be yes/yes/no, yes/no/yes, etc. A real bug that is `in_scope: no` or
`program_reportable: no` is **not** submittable.

- `[out_of_scope_asset]` The asset is outside the allowlist (or a subdomain/acquisition the
  policy does not list). Do not test or submit. `[technical_placeholder]`
- `[prohibited_test_method]` The impact is only demonstrable via a banned technique
  (automated scan, brute force, DoS, real-user data). `[technical_placeholder]`
- `[real_but_below_program_impact_threshold]` A genuine bug whose demonstrated impact is under
  the reward bar, or a VDP that accepts without paying. `[technical_placeholder]`
- `[missing_security_boundary]` / `[expected_product_behavior]` The endpoint is public by
  design and requires no authorization. `[technical_placeholder]`

These entries are `[technical_placeholder]`: this is a methodology-seeded process skill, so the
taxonomy is their source of authority until curated negatives back them.

## Anti-patterns

- Never treat public reachability, a platform listing, or an in-scope asset's reachability into
  another system as authorization for every subdomain or technique.
- Never expand testing beyond program authorization to strengthen impact (*the policy-boundary
  failure* in `METHODOLOGY.md`).
- Never skip the pre-submission policy re-review; the live policy may have changed since entry.
- Never overwrite `pre_scan.yaml` `asset_fingerprint` or `known_findings_count`; refresh only
  the policy fields.
- Never set `scope_confirmed` / `testing_method_permitted` true when the live policy and
  `contract.yaml` disagree — stop for a human.

## Evidence basis and limits

Methodology-seeded, not corpus-mined: [`SECURITY-RESEARCH-POLICY.md`](../../SECURITY-RESEARCH-POLICY.md)
(authorization/scope precedence, rate/identity, third-party, prohibited testing, emergency
stops), [`METHODOLOGY.md`](../../METHODOLOGY.md) (`## The "should I report this?" decision
tree`, the policy-boundary failure mode, `## Final submission contract`), and the target
`contract.yaml` `program_scope` + `handoff_policy`. Authorization is always subordinate to the
live program policy.

## AI-assisted augment (NahamSec seed)

Transferable technique from Ben Sadeghipour (NahamSec), public PlexTrac "Homework for Hackers"
webinar (`Ue-OIJoM0bA`); see
[`knowledge-sources/creators/03-nahamsec.md`](../../knowledge-sources/creators/03-nahamsec.md).
Guardrail: the published policy is the authority — the model may misread scope, and a platform
listing alone may not authorize every asset or technique. Never paste confidential program
terms into an unapproved model (`nahamsec-ai-sanitize-before-sharing`, CWE-200).

- **Read the policy and build an allowlist before touching the target
  (`nahamsec-authorized-real-world-practice`).** Use an approved model only to help parse a long
  policy into a structured allowlist + exclusion list (assets, permitted methods, rate limits,
  required headers) — then verify every entry against the published policy text before it gates
  any testing. The model accelerates parsing; it never grants authorization.

## Version boundaries

Null — this is a process skill, not version-bound.
