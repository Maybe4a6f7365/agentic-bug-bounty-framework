---
name: business-logic-hunter
description: Hunt business-logic failures by modeling workflow invariants, limits, one-time actions, confirmations, normalization, and concurrency. Load when every individual request is valid but an unexpected sequence or value violates product rules. Triggers — Business Logic Errors, business logic bypass, race condition or limit bypass, workflow invariant failure, coupon or quota abuse.
---

# Business-Logic Hunter

Use sandbox accounts and reversible, zero-value actions. Do not create real orders, consume inventory, sign transactions, spam users, or exploit monetary promotions.

## Convert product rules into invariants

For each workflow, write the rule in machine-checkable form:

- one-time: `redemptions(user, offer) <= 1`;
- bounded: `1 <= rating <= 5`;
- ownership: `attachment.parent == form_visible_to(actor)`;
- confirmation: `signing requires fresh user approval`;
- domain policy: `canonical(email.domain) not in denylist`;
- sequence: only allowed state transitions occur;
- concurrency: parallel requests preserve the same invariant as serial requests.

Capture the normal request/response and authoritative read-back. Change one dimension: value, identity, order, repetition, canonical form, client-controlled security flag, offline state, or concurrency.

## Recon signals

- OTP/change flows, coupons, free entitlements, referrals, ratings, quotas, and trials.
- Body fields such as `rating`, `role`, `plan`, `enableAuthorize`, `confirmed`, `meta`, `scope_id`, `context_type`, or client-calculated totals.
- Hidden confirmation/security booleans that default insecurely when false or omitted.
- Unicode-sensitive email/domain restrictions and case/normalization checks.
- Endpoints accepting a parent/context ID for an upload or action.
- Transactions that can be replayed in parallel or after state changes/offline mode.
- The server trusts UI sequencing, disables buttons, or enforces limits only in a preliminary request.

## Test recipes

### Boundary and type mutation

From a controlled completed workflow, change only a bounded value. A report sent `{"rating":55}` to a ride review endpoint that expected 1–5.

```http
POST /api/v1/reviews/ride/<CONTROLLED_RIDE>/driver HTTP/1.1
Authorization: Bearer <CONTROLLED_TOKEN>
Content-Type: application/json

{"message":"logic-canary","rating":55}
```

Positive: authoritative profile/read-back incorporates the out-of-range value. `200` alone is not proof.

### Fixed/default verification value

In a phone/email change on controlled identities, submit a single known-invalid code such as `0000`. Never brute-force. Positive: the new identifier is committed and usable without the delivered OTP.

### Parent/context swap

For uploads or child actions, use A's session with B's controlled form/scope ID. One report uploaded to a pentest scoping form by setting `context_type` and a foreign scope ID. Verify B sees the harmless canary; remove it.

### Race a one-time action

Establish a serial control, then send a small synchronized batch (2, then at most 5) to a disposable free entitlement. Keep idempotency fields constant unless the client normally varies them.

```python
with ThreadPoolExecutor(max_workers=2) as pool:
    results = list(pool.map(lambda _: redeem_once(), range(2)))
```

Positive: authoritative state grants more than the documented limit. Multiple `200`s with one committed grant are safe behavior.

### Unicode canonicalization

Configure a controlled denylist domain, prove ASCII is blocked, then substitute a confusable/case-normalization character such as `İ` in the domain. Use a mailbox/domain you control. Positive: server stores or delivers to the canonical blocked domain, not merely a visually similar different domain.

### Client-controlled authorization flag

Search signing/approval requests for booleans like `enableAuthorize`. Toggle or omit them in a controlled no-value message signing flow.

```json
{"enableAuthorize":false,"typedDataMessage":{"domain":"<CONTROLLED>"},"address":"<CONTROLLED>"}
```

Positive: a signature/action is produced without the mandatory confirmation. Never sign a transaction transferring assets.

### Replay one-time promotion

Use a test coupon specifically issued for sandbox use. Apply twice to two zero-value carts and verify redemption counters, not just displayed totals. Stop before checkout.

## Detection signals

Always query authoritative state after the variant: account identifier, aggregate rating, membership, attachment list, entitlement count, signature audit, or coupon redemption count. Compare expected invariant, serial control, mutated request, and cleanup result.

After completing these checks, explore adjacent business-logic surface the checklist did not
cover — the skill is a floor, not a ceiling.

## Stop conditions (verified negatives)

Each stop condition below carries one of the 12 categories from [`skills/references/negative-control-taxonomy.md`](../references/negative-control-taxonomy.md). Apply ALL applicable labels. Never file a finding that triggers any category below.

**Decision split (apply separately, never collapse):**
- `technically_vulnerable`: is the workflow invariant actually exploitable?
- `in_scope`: does the program cover this asset and workflow?
- `program_reportable`: does the durable business impact meet its threshold?
A finding can be yes/yes/no, yes/no/yes, etc. A UI anomaly or excluded workflow is not submit-worthy on `technically_vulnerable` alone.

- `[expected_product_behavior]` Coupons, invitations, resume/download behavior, or delegated actions intentionally permit the observed reuse. Empirical: H1 `2859735` (N/A — "curl --continue-at confusion").
- `[control_exists_elsewhere]` A provisional success is rolled back, deduplicated, or rejected by the authoritative ledger/job. `[technical_placeholder]`
- `[missing_attacker_control]` The transition requires a trusted operator/config value rather than attacker workflow input. Empirical: H1 `3473182` (N/A — "A logic error in detect_proxy caused truncation of environment variable names for long protocol schemes.").
- `[theoretical_without_oracle]` UI state changes, but no second redemption, entitlement, balance change, or forbidden action occurs. Empirical: H1 `2792484` (informative — "When curl uses Schannel as TLS backend, it fails to enforce TLS 1.3 cipher suite selections correctly").
- `[real_but_below_program_impact_threshold]` A bounded protocol/UI inconsistency causes no durable security or monetary impact. Empirical: H1 `3480039` (informative — "WebSocket Logic Error: Control Frame (PING/PONG) Starvation causes Connection Drop (DoS) during large transfers") and `2213366` (informative — "captcha bypass leads to register multiple user with one valid captcha").
- `[duplicate_root_cause]` The same workflow flaw/fix is already tracked. Empirical: H1 `2571981` (duplicate — "Business Logic error leads to bypass 2FA requirement ") and `1841064` (duplicate — "Ability to getting Twitter Blue verified badge without purchase it").
- `[technically_not_vulnerable]` Display rounding differs while the ledger is correct, or paired replay creates only one durable object. `[technical_placeholder]`

## Anti-patterns

- Do not infer rules from personal expectations; establish product evidence.
- Do not use large concurrency batches, real purchases, rewards, rides, or phone numbers.
- Do not bypass confirmations on value-bearing operations.
- Do not mutate several fields at once.
- Do not stop at HTTP status; prove committed invariant violation and restore state.

## Minimal reproducer

```python
import os, requests

base = os.environ["TARGET_BASE"].rstrip("/")
token = os.environ["TEST_TOKEN"]
path = os.environ.get("TEST_PATH", "/api/<CONTROLLED_WORKFLOW>")
for value in [5, 55]:
    r = requests.post(base + path,
        headers={"Authorization": f"Bearer {token}"},
        json={"rating": value, "message": "logic-canary"}, timeout=15)
    print(value, r.status_code, r.text[:200])
# Follow with an authoritative GET and clean up test state.
```

## Evidence basis and limits

Derived from seven full reports: H1 `2588329`, `2450215`, `2125049`, `2616045`, `2033005`, `3507241`, and `3426839`. Patterns cover invalid OTP acceptance, context swaps, numeric bounds, races, Unicode normalization, client-controlled approval, and one-time coupon reuse.

Negatives in this skill are partly empirical (11 disclosed non-accepted Business Logic Errors reports in the local corpus) and partly structural from arXiv 2511.18608 / ESEM 2021 — see `skills/references/negative-control-taxonomy.md` for provenance.

## Design invariants from real audits

Workflow invariants distilled from disclosed third-party audits — the state/order/limit class scanners miss. Full extraction, sources, and URLs: [`skills/references/audit-invariants.md`](../references/audit-invariants.md).

- **No cross-flow state replay.** Per-flow challenges/tokens must not live in a session slot a sibling or earlier flow can supply; each step re-derives its prerequisites. [source: Cure53 authentik ATH-01-014, 2023 — dropped auto-GET replays an earlier flow's challenge].
- **Canonicalize before deciding.** Normalize the path/URL once, then validate; a mitigation applied before a later normalization step is bypassable. [source: Ada Logics/OSTIF Express.js ADA-EXPJS-2024-1 / CVE-2024-43796, 2024 — trailing-slash re-craft yields XSS in `res.redirect`].
- **Deferred/async continuation re-checks authorization at execution.** An enqueue-time check does not carry to dequeue-time; the async handler re-verifies tenant/permission when it runs. [source: Trail of Bits Vanta multi-tenant review, 2025].
- **Auth fallbacks fail closed.** When the primary credential (token) mismatches, reject — never silently downgrade to a weaker trusted-header path. [source: Trail of Bits PyPI TOB-PYPI-12 "HTTP header silently trusted if token mismatches", 2023].
- **Authorization decisions fail closed.** An evaluation error, timeout, or missing policy yields deny, not allow. [source: Trail of Bits Cedar/Rego/OpenFGA assessment, 2024].
- **Pre-auth submission endpoints enforce per-source size AND count quotas.** A size cap without a count/rate cap is a durable invariant break. [source: Cure53 GlobaLeaks GL01-006, 2013 — size validated, upload count not].

## Web-Verification Augment (2026-07-22)

- Local negatives: 11 total (5 informative, 4 not-applicable, 2 duplicate); representative IDs and exact titles/substates are anchored above.
- Study-only taxonomy: authoritative rollback/deduplication and correct-ledger cases remain `[technical_placeholder]`; no body fetch was required.

## AI-assisted augment (NahamSec seed)

Transferable techniques from Ben Sadeghipour (NahamSec), with the indirect-content point
attributed to Mike Bell, public PlexTrac "Homework for Hackers" webinar (`Ue-OIJoM0bA`).
Guardrail: model output is a hypothesis, not evidence — confirm against a live target
oracle and the shared
[negative-control taxonomy](../references/negative-control-taxonomy.md); never send
unsanitized target data to an unapproved model (`nahamsec-ai-sanitize-before-sharing`,
CWE-200).

- **Treat an AI/agent trust chain as a workflow invariant surface
  (`nahamsec-ai-map-full-trust-chain`, `nahamsec-ai-indirect-content-boundary`).** When a
  workflow routes untrusted content (docs, tickets, email, retrieval stores) through an
  assistant that can call tools or act under a service identity, enumerate the chain as
  distinct trust boundaries and record which checks run before and after each model
  decision. The invariant to break: untrusted content should not be able to drive an action
  the initiating user could not authorize. Test with a benign canary instruction and a
  matched no-instruction control; a real, out-of-band-confirmed side effect is the oracle,
  not a chat transcript's claim. Reversible, self-scoped probes only; stop at the
  confirmation boundary and only where AI testing is authorized.
- **Variant matrix across similar workflows (`nahamsec-deep-one-weakness-family`).** Extract
  the invariant once (limit, one-time action, confirmation, normalization) and enumerate how
  sibling flows implement it; a benign/patched flow must stay negative.

## Version boundaries

null — Business-logic flaws are bound to application workflows, invariants, state transitions, and concurrency behavior, not library versions. The GHSA/OSV `introduced`/`fixed` model does not apply; bound fixes with application patch diffs and invariant tests instead.
