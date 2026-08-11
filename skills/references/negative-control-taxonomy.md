---
source_type: negative-control-taxonomy
last_updated: 2026-07-22
priority: P1
reliability: high
---

# Negative-Control Taxonomy (shared stop-condition reference)

## What this is

The single, shared vocabulary every hunt-skill uses to decide **when to stop and not
file**. Each per-CWE hunt skill (`idor-hunter`, `path-traversal-hunter`, …) links here
from its `## Stop conditions (verified negatives)` section instead of redefining the
categories inline. When a candidate finding matches a category below, it is a
**verified negative** — a reason a real triager said "no" — and must not be submitted
on its own.

The point is precision. The documented LLM failure mode for bug-bounty triage is
**over-acceptance of invalid reports** (arXiv 2511.18608). A fixed category set turns
"this feels weak" into an explicit, auditable stop condition.

## The 12 categories

| category | definition | typical evidence signal | example tag-pattern in H1 closing comments |
|---|---|---|---|
| `technically_not_vulnerable` | The code path is safe; the claimed flaw is a misread. | Server enforces the check; PoC never crosses a boundary. | "working as designed", "the request is rejected server-side", "false positive — not reproducible" (arXiv 2511.18608 *Technical Issues* / *Not Applicable*) |
| `expected_product_behavior` | The resource is intentionally public/shared. | Object is public, disclosed, or explicitly shared. | "this content is public", "intended to be shareable" |
| `control_exists_elsewhere` | A compensating control on another layer neutralizes it. | Signed/expiring URL, WAF, per-tenant scoping upstream. | "protected by signed URL", "requires an unexpired token" |
| `missing_attacker_control` | Attacker cannot actually influence the vulnerable input. | Value is server-derived, not attacker-supplied. | "you cannot control this value", "no cross-user input" |
| `out_of_scope_asset` | Real bug, but on an asset the program excludes. | Host/app/domain outside the bounty policy scope. | "out of scope", reporter self-marks "I know this is OOS" |
| `prohibited_test_method` | Impact only shown via a banned technique. | Automated scan, brute force, DoS, real-user data. | "automated scanning is prohibited", "no brute forcing allowed", "testing against real user data violates our policy" (arXiv 2511.18608 *Scope/Policy Issues* + *Special Scenarios*; spam-quality anchor H1 `460642`, `[study-cited; not in local corpus]`) |
| `missing_security_boundary` | No authz boundary was ever supposed to exist here. | Endpoint public by design; feature needs no login. | "does not require users to login", "public endpoint" |
| `theoretical_without_oracle` | No evidence the impact actually occurred. | Cached/self data mistaken for victim data; no B-read. | "cannot reproduce", "no proof of cross-account access" |
| `vulnerable_third_party_but_target_not_affected` | A dependency is flawed but the target doesn't reach it. | CVE in a lib the target doesn't invoke on that path. | "we don't use that code path", "the vulnerable component is behind our own access-control layer", "outside program control" (arXiv 2511.18608 *Third-party Related Issues*) |
| `patched_version` | Fixed in the version the program actually runs. | Target on/above the `fixed` boundary (OSV/GHSA). | "already patched in vX.Y", "not present on current build", "fixed in a prior release" (arXiv 2511.18608 *Technical Issues* — known / already-resolved) |
| `duplicate_root_cause` | Same underlying cause as a prior/known report. | Team already tracks it; another report shares the fix. | "duplicate of #…", "we were already aware of this issue" |
| `real_but_below_program_impact_threshold` | Genuine bug, impact under the reward bar. | Low-sensitivity data; existence-only oracle; no PII. | "informative", "does not meet our severity bar" |

## The 3 independent labels — never collapse them

A finding carries **three separate yes/no answers**. They are orthogonal; a real bug
can still be unsubmittable on any one of them.

- `technically_vulnerable` — is the code actually exploitable?
- `in_scope` — does the program's bounty policy cover this asset?
- `program_reportable` — does the demonstrated impact meet the program's threshold?

They belong apart because the failure modes differ: conflating them is exactly how an
agent files an out-of-scope-but-real bug, or a technically-real-but-informative one.
`yes/yes/no`, `yes/no/yes`, and `yes/no/no` are all common and all **do not submit**.
(Source 08 names the scope label `program_in_scope`; skills may use the shorter
`in_scope` — same label.)

## The study (structure, not verbatim data)

- **arXiv `2511.18608`** — "From Reviewers' Lens: Understanding Bug Bounty Report
  Invalid Reasons with LLMs" (IEEE Xplore document `11402236`, accepted version). 9,942 disclosed reports incl. 1,400 invalid; SOTA
  LLMs over-accept; a rejection-reason taxonomy in a RAG framework improves invalidity
  detection.
- **ESEM 2021** — Saman Shafigh, Boualem Benatallah, Carlos Rodríguez, Mortada Al-Banna
  (UNSW, Australia), "Why Some Bug-bounty Vulnerability Reports are Invalid?", 12 Oct
  2021, DOI `10.1145/3475716.3484193` (predecessor).

> **Provenance marker:** these studies supply the *structure* — that invalidity has a
> small, learnable set of reasons, and that the 3-label split matters. They do **not**
> supply the verbatim category strings or per-CWE counts below; those are our own
> transcription and our own local corpus mining. Cite the studies as structure only.

## How skills reference this file

Every hunt skill's stop-condition section opens with:

> "See `skills/references/negative-control-taxonomy.md` for the full 12-category
> taxonomy. Apply ALL applicable labels to every stop-condition entry below."

Each stop-condition entry is prefixed with its category tag in brackets, e.g.
`[expected_product_behavior]`. Entries with no matching local negative yet are marked
`[technical_placeholder]` and cite the taxonomy as their only source until a curated
negative from the target's H1 closing comments backs them.

## Local data landscape (verified via corpus script)

The local H1 corpus (`~/projects/h1-skills/details/`, 1,848 reports) holds **329
disclosed non-accepted** reports: 162 not-applicable, 139 informative, 21 duplicate,
7 spam. Sub-category by CWE (weakness field), as mined for the Block-B back-fill:

| CWE / skill | non-accepted | N/A | Informative | Duplicate |
|---|---|---|---|---|
| Information Disclosure | 19 | 8 | 9 | 2 |
| Path Traversal | 14 | 12 | 2 | 0 |
| Business Logic Errors | 11 | — | — | — |
| Improper Authentication | 10 | — | — | — |
| Improper Access Control | 8 | — | — | — |
| Privilege Escalation | 3 | — | — | — |
| IDOR | 3 | 0 | 2 | 1 |
| XSS Stored | 3 | — | — | — |
| SQL Injection | 1 | — | — | — |
| XSS Reflected | 0 | — | — | — |

Negatives are thin for exactly the skills that need them most (IDOR: 3; XSS reflected:
0). Where a category has no local example, the skill marks it `[technical_placeholder]`
rather than inventing a report ID.

## Honest ledger

- **Verified locally (corpus script):** the 329 total and its 162/139/21/7 split; the
  per-CWE sub-counts above; the 3 IDOR negatives (`2944357` duplicate, `3382343` /
  `2618486` informative) with their real closing text.
- **From the studies (structure only):** the over-acceptance failure mode and the
  RAG-taxonomy remedy (arXiv 2511.18608); the ESEM 2021 predecessor.
- **Draft / design (this doc):** the 12 exact category strings and the 3-label split
  are transcribed from source 08 / José's brief as our labeling contract.
- **Study-based (updated 2026-07-22):** the `example tag-pattern` strings for the four
  categories with no local IDOR negative — `technically_not_vulnerable`,
  `prohibited_test_method`, `vulnerable_third_party_but_target_not_affected`, and
  `patched_version` — are now derived from the arXiv 2511.18608 Information-Disclosure
  invalid-reason taxonomy (its *Technical Issues*, *Not Applicable*, *Third-party
  Related Issues*, *Scope/Policy Issues*, and *Special Scenarios* labels) plus ESEM 2021
  (out-of-scope / false-positive), not invented illustratively. They remain a plausible
  translation of the study's reason labels into H1 closing-comment phrasing, not verbatim
  quotes from a specific report; the parenthetical names the source label. The other
  eight rows' evidence columns stay illustrative. Validate all example patterns against
  real closing comments as curated negatives accrue.

## Web-Verification Augment (2026-07-22)

- Direct arXiv fetch and local lookup: of cited H1 `460642`, `226514`, `2215434`, `688546`, `832593`, only `2215434` is in the corpus (`resolved`; Information Disclosure; `security`); the other four are absent, so none is assigned to an unsupported taxonomy row. The JSONL starts at disclosure date 2023-05-10, but its collection policy is unavailable; the exact exclusion reason is therefore unknown.
- IEEE Xplore document `11402236` identifies the accepted version. ESEM 2021 DOI `10.1145/3475716.3484193`: Shafigh, Benatallah, Rodríguez, Al-Banna (UNSW, Australia), 12 Oct 2021; citation extracted from the arXiv references and conference record.
- Local JSONL count: 298 reports with program handle `curl`.
