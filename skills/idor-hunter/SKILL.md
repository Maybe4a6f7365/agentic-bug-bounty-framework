---
name: idor-hunter
description: Hunt object-level authorization failures in REST and GraphQL using two controlled principals, ownership swaps, nested IDs, and read-after-write evidence. Load when requests contain numeric, UUID, global, attachment, report, invoice, model, or conversation identifiers. Triggers — Insecure Direct Object Reference, IDOR, BOLA, cross-tenant object access, object ID can be changed. Prefer access-control-hunter when no object identifier is attacker-supplied.
---

# IDOR Hunter

Use only controlled objects. The invariant is: changing an object reference must not let principal A read or mutate an object owned exclusively by principal B.

## Prepare a two-principal ledger

Create `A` and `B`, preferably in separate tenants. For each, record token/cookie, tenant/workspace, object ID, parent ID, and visibility. Capture A-on-A and B-on-B requests first. Never guess live users' IDs when a second controlled account can provide a valid foreign reference.

Build an object graph, not a flat ID list: organization → report → summary → attachment; shop → invoice → download job; project → model → version; workspace → conversation. Authorization is often checked on the parent but missed on a nested child or alternate renderer.

## Recon signals

- Numeric IDs in paths and fields: `/reports/{id}`, `/statuses/{id}/hearts`, `attachment_ids[]`, `comment_id`.
- GraphQL global IDs such as `gid://<APP>/<TYPE>/<NUMBER>` and variables named `id`, `modelId`, `modelVersionId`.
- Search/list endpoints accepting `organization_id`, `text_query`, filters, or all lifecycle substates.
- Preview, summary, download, reaction, export, archive, or delete endpoints that consume IDs created elsewhere.
- Responses returning nested owner/tenant fields, `_links`, download jobs, or child IDs.
- Frontend permission gates without matching server checks.

## Test recipes

### Horizontal read

Replay A's valid request with B's object ID and keep A's credential, parent, headers, and operation unchanged.

```http
GET /api/w/<A_WORKSPACE>/assistant/conversations/<B_OBJECT_ID> HTTP/1.1
Cookie: <A_SESSION>
```

Positive: `200` plus B-specific title, owner, content, or metadata. `200` with A's object, empty data, or a generic envelope is not proof.

### Nested/renderer ID swap

Reports showed attachments denied in a normal report body but accepted by a summary renderer. Test the same child ID across every consumer.

```http
PUT /reports/<A_REPORT>/summaries/<A_SUMMARY> HTTP/1.1
Content-Type: application/json
Cookie: <A_SESSION>

{"content":"canary","attachment_ids":["<B_ATTACHMENT_ID>"],"action_type":"publish"}
```

Use B's benign canary file and a draft. Positive: A's preview renders or returns B's file, and B remains owner.

### GraphQL global-ID swap

Keep the operation and selection set minimal. Swap one ID at a time, including child IDs returned by the first response.

```json
{"operationName":"getModel","variables":{"id":"gid://<APP>/Model/<B_ID>"},"query":"query getModel($id: ID!){ model(id:$id){ id name owner { id } } }"}
```

Then test paired parent/child consistency: B parent + B child, A parent + B child. A disclosed billing pattern also returned another tenant's invoice data and download job when only the invoice ID changed.

### State-changing object test

Use a reversible mutation first (rename, pin, add a test tag). If only destructive behavior exists, stop and document the missing safe validation path.

```http
PATCH /api/<RESOURCE>/<B_ID> HTTP/1.1
Authorization: Bearer <A_TOKEN>
Content-Type: application/json

{"title":"IDOR_CANARY"}
```

Verify with B, then restore. One report showed an account-destroy request bound to attacker session but victim body credentials; do not reproduce irreversible deletion outside disposable test accounts.

### Enumeration/search oracle

Do not brute-force. Use one controlled organization ID and a precise controlled report title. Test whether a low-privilege search endpoint returns protected fields when filters include all substates. Prove with A/B objects only.

## Detection signals

Require ownership evidence inside the response or a read-after-write from B. Strong indicators:

- B's canary, email, owner ID, private title, model metadata, or invoice fields under A's session;
- a mutation response plus B observing the changed/deleted controlled object;
- a nested child accepted under the wrong parent;
- predictable numeric/global IDs matter only after unauthorized access is proven.

Compare A→A, A→B, unauthenticated→B, and invalid-ID controls. Record status, response schema, object owner, and side effect.

After completing these checks, explore adjacent object-reference surface the checklist did not
cover — the skill is a floor, not a ceiling.

## Stop conditions (verified negatives)

Each stop condition below carries one of the 12 categories from [`skills/references/negative-control-taxonomy.md`](../references/negative-control-taxonomy.md). Apply ALL applicable labels. Never file a finding that triggers any category below.

**Decision split (apply separately, never collapse):**
- `technically_vulnerable`: is the code actually exploitable?
- `in_scope`: does the program's bounty policy cover this asset?
- `program_reportable`: does the demonstrated impact meet the program's threshold?
A finding can be yes/yes/no, yes/no/yes, etc. Do not submit on `technically_vulnerable` alone.

- `[expected_product_behavior]` Public profiles, public models, disclosed reports, shared workspace objects, or intentionally unlisted resources.
- `[control_exists_elsewhere]` Signed URLs intentionally bearer-accessible and unexpired; assess the design contract before labeling IDOR.
- `[missing_attacker_control]` A `200` GraphQL response with `data: null` and authorization errors.
- `[theoretical_without_oracle]` Cached A data mistaken for B data — no genuine cross-principal read to prove it was B's data.
- `[missing_security_boundary]` Mutations queued but rejected asynchronously — the UI says yes, the server says no; the control exists, it is only enforced late.
- `[real_but_below_program_impact_threshold]` Existence oracle (`403` vs `404`) without unauthorized data or action, unless existence itself is sensitive and demonstrated. Empirical: H1 `3382343` (informative — BOLA reads any user's out-of-office/absence data) and H1 `2618486` (informative — reveals any user's unpinned achievement badges); both are genuine IDORs closed below the reward bar.
- `[out_of_scope_asset]` A valid IDOR in an asset the program's bounty policy explicitly excludes. Structural example: H1 `273377`, where the reporter self-marks the finding out of scope ("I know that its out of scope … but I thought I should tell you about it"). That report is path traversal, not IDOR — included only for the reporter-driven out-of-scope-marker structure, to show related CWEs belong in stop conditions too.
- `[duplicate_root_cause]` Same underlying cause as a report the team already tracks. Empirical: H1 `2944357` (duplicate — team summary: "we were already aware of this issue"; the reservation-cancel endpoint required no login by design, so it doubles as `[missing_security_boundary]`).
- `[missing_security_boundary]` Endpoints that are public by design carry no authorization boundary — even when they embed object IDs. An object ID in the path is not an IDOR if no principal was ever meant to be separated there.
- `[vulnerable_third_party_but_target_not_affected]` A library the target depends on (its ORM, auth middleware, object-store SDK, or API gateway) carries a known IDOR/BOLA-class flaw, but the target's endpoint never routes through the vulnerable code path, so no cross-tenant object read/write is actually reachable on the target. Detection: the IDOR weakness lives in a dependency's GHSA/CVE advisory, not in the target's own handler; the target wraps the call behind its own ownership check, disables the affected method by config, or simply never invokes it — A-on-B returns `403`/`data: null` on the target while the dependency PoC only works standalone. Example closings: "we don't use that code path", "the vulnerable component sits behind our own access-control layer", "not exploitable here — that method isn't reachable in our stack". Source: arXiv 2511.18608 "Third-party Related Issues" ("issues caused by external dependencies or third-party services outside program control") + generic dependency-reachability reasoning. No local IDOR negative in this exact category yet; still `[technical_placeholder]` for a curated local example.
- `[technically_not_vulnerable]` The object reference can be changed, but the server re-checks ownership on that exact path, so principal A never reads or mutates B's object — the "IDOR" is a misread of a `200` that only ever returns A's own data or an authorization error. Detection: A-on-B returns `200` with A's data, an empty envelope, or an authz error rather than B's canary; tenant/owner is derived from the session, not from the supplied ID; both parent and child ownership are re-validated. Example closings: "working as designed", "the request is rejected server-side", "authorization is enforced — you only see your own record". Source: arXiv 2511.18608 "Technical Issues" (false positives / not reproducible) + "Not Applicable" status + ESEM 2021 false-positive reason. No local IDOR negative in this exact category yet; still `[technical_placeholder]`.
- `[patched_version]` The object-level authorization gap existed in an earlier build, but the version the program actually runs already enforces the ownership check, so the live endpoint is on or above the fix. Detection: A-on-B succeeds against a stale/staged artifact but returns `403` on production; a patch diff or changelog shows the ownership check being added. Caveat: IDOR is application-logic bound and normally carries a null version boundary (see "Version boundaries" below), so this label applies only when a specific deploy demonstrably shipped the authz fix — not as a generic "upgrade the framework" claim. Example closings: "already patched in vX.Y", "not present on current build", "this was fixed in a prior release". Source: arXiv 2511.18608 "Technical Issues" (known / already-resolved) + generic patch-diff reasoning. No local IDOR negative in this exact category yet; still `[technical_placeholder]`.
- `[prohibited_test_method]` The cross-object access is only demonstrable via a technique the program bans — ID brute-force/enumeration, automated scanning, or reading a real (non-controlled) user's object — so the PoC itself is out-of-policy even if a boundary is crossed. Detection: the only "proof" iterates through production IDs, runs a scanner, or reads a live user's object instead of a controlled B canary; no two-principal controlled reproduction exists. Example closings: "automated scanning is prohibited", "no brute forcing allowed", "testing against real user data violates our policy". Source: arXiv 2511.18608 "Scope/Policy Issues" ("reports … violating disclosure policies") + "Special Scenarios" + ESEM 2021 out-of-scope/policy reason; reinforced by this skill's own Anti-patterns. Cross-CWE spam anchor: H1 `460642`, an HTTP-PUT report closed as Spam for reusing a disclosed demo (`[study-cited; not in local corpus]`). No local IDOR negative in this exact category yet; still `[technical_placeholder]`.

## Anti-patterns

- Do not increment through production IDs or mass-download objects.
- Do not delete accounts, invoices, certifications, conversations, or files except disposable controls.
- Do not change multiple IDs, cookies, and parents in one request; preserve causal evidence.
- Do not claim IDOR solely because identifiers are sequential.
- Do not expose real object contents in the PoC; use controlled canaries and placeholders.

## Minimal reproducer

```python
import os, requests

base = os.environ["TARGET_BASE"].rstrip("/")
token = os.environ["PRINCIPAL_A_TOKEN"]
own, foreign = os.environ["A_OBJECT_ID"], os.environ["B_OBJECT_ID"]
path = os.environ.get("PATH_TMPL", "/api/objects/{id}")
for label, oid in [("own", own), ("foreign", foreign)]:
    r = requests.get(base + path.format(id=oid),
        headers={"Authorization": f"Bearer {token}"}, timeout=15)
    print(label, r.status_code, len(r.content), r.text[:300])
# Assert B's unique canary/owner field, not status alone.
```

## Evidence basis and limits

Derived from seven full reports: H1 `2122671`, `2442008`, `2487889`, `3154983`, `2207248`, `2541962`, and `2528293`. Concrete patterns cover GraphQL mutations/global IDs, attachment renderers, organization search, session/body misbinding, invoice downloads, reaction endpoints leaking hidden content, and nested ML model versions.

Negatives in this skill are partly empirical (3 disclosed non-accepted IDOR reports in the local corpus) and partly structural from arXiv 2511.18608 (IEEE Xplore document `11402236`, accepted version) / ESEM 2021 — see `skills/references/negative-control-taxonomy.md` for provenance.

**Why this matters for IDOR:** arXiv 2511.18608 cites curl founder Daniel Stenberg's 2025-07 blog as an example of AI-slop triage burden. The local H1 corpus contains 298 curl reports, its highest single-program volume, making curl its richest program-level observation set for the paper's over-acceptance failure mode.

## Web-Verification Augment (2026-07-22)

- Direct arXiv fetch and local lookup: of cited H1 `460642`, `226514`, `2215434`, `688546`, `832593`, only `2215434` is in the corpus (`resolved`; Information Disclosure); the other four are absent. The JSONL's disclosure window starts 2023-05-10, but it does not expose a collection policy, so the exact exclusion reason is not provable.
- IEEE Xplore document `11402236` identifies the accepted version. ESEM 2021 DOI `10.1145/3475716.3484193`: Shafigh, Benatallah, Rodríguez, Al-Banna (UNSW, Australia), 12 Oct 2021; citation extracted from the arXiv references and conference record.
- Local JSONL count: 298 reports with program handle `curl`.

## AI-assisted augment (NahamSec seed)

Transferable techniques from Ben Sadeghipour (NahamSec), public PlexTrac "Homework for
Hackers" webinar (`Ue-OIJoM0bA`). Guardrail: model output is a hypothesis, not evidence —
confirm every candidate with a two-principal read-after-write oracle and the shared
[negative-control taxonomy](../references/negative-control-taxonomy.md); never paste
unsanitized target data into an unapproved model
(`nahamsec-ai-sanitize-before-sharing`, CWE-200).

- **Neighbor object-route / param ideas (`nahamsec-ai-neighbor-path-ideas`).** From one
  observed identifier pattern (`/api/v1/orgs/{id}/members`, an attachment or invoice route),
  ask an approved model for likely sibling routes, nested-ID variants, and `include=`/expand
  parameters that widen the object graph; probe slowly against nonexistent controls, then
  test each with the second principal.
- **Second-look on unfamiliar identifier encodings (`nahamsec-ai-context-second-look`).** Use
  a model to hypothesize how an opaque ID is composed (base64 tuple, UUIDv1 timestamp,
  HMAC-tagged); confirm control by successfully swapping to principal B's object, never by
  the model's guess.

## Version boundaries

null — IDOR is an application-logic class bound to authorization checks, not to component versions. A vulnerable endpoint does not become safe by upgrading the framework. The `introduced`/`fixed` model from GHSA/OSV does not apply; rely on patch diffs in `case-bundle-builder` instead.
