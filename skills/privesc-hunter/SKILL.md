---
name: privesc-hunter
description: Hunt vertical privilege escalation through alternate APIs, role parameters, capabilities, invitation revocation, privileged actions, and local service boundaries. Load when a low-privilege identity may perform an admin-only or higher-role operation. Triggers — Privilege Escalation, vertical privilege escalation, regular user can perform admin action, role or capability bypass. Vertical only; use idor-hunter or access-control-hunter for same-privilege horizontal access.
---

# Privilege-Escalation Hunter

Use controlled low/admin accounts and reversible actions. Distinguish vertical privilege escalation from IDOR: the decisive fact is that the actor gains or exercises a capability reserved for a higher role, even if no foreign object ID changes.

## Build a capability matrix

List roles and concrete actions, not labels: invite admin, pin comment, manage conversation, submit while restricted, enable capability, change role, restore quarantine, write protected file. Capture the admin request and low-user denial. Identify whether the restriction lives in UI, route middleware, object policy, background job, invitation lifecycle, runtime capability declaration, or local service permissions.

## Recon signals

- Admin UI controls absent for low users while endpoints remain visible in JavaScript/network history.
- Parameters `role`, `permission`, `capability`, `admin`, `visibility`, `comment_id`, `bbp-forums-role`, or feature flags.
- Alternate API keys, REST routes, GraphQL mutations, mobile APIs, or background workers for the same action.
- Pending admin invitations and what happens when the inviter is removed/demoted.
- Capability manifests checked at upload/install time but not at execution time.
- State-changing endpoints protected only by `login_required`, without role/ownership predicates.
- Privileged local services operating on attacker-controlled file paths, quarantine files, DLL search paths, or cleanup targets.

## Test recipes

### UI-to-endpoint parity

As admin, capture a harmless reversible action. Replay as low user with a controlled object. A report showed pin/unpin buttons hidden by frontend permissions while `/pin-comment/` and `/unpin-comment/` accepted any logged-in user.

```http
POST /pin-comment/ HTTP/1.1
Cookie: <LOW_USER_SESSION>
X-CSRFToken: <LOW_USER_CSRF>
Content-Type: application/x-www-form-urlencoded

comment_id=<CONTROLLED_COMMENT_ID>
```

Positive: read-back shows the low user performed the privileged action. Restore by unpinning.

### Alternate credential/channel

Place a controlled user into a restricted state and prove UI/direct calls return `403`. Replay the equivalent sandbox action through an API key or alternate route. Positive: the protected action commits despite the same actor restriction.

### Role parameter injection

Inspect registration/invitation/update forms for client-controlled role fields. One report used `bbp-forums-role=bbp_keymaster` in a registration request triggered under an admin session. Test only a disposable local/admin-controlled instance and a test user.

```http
POST /register HTTP/1.1
Content-Type: application/x-www-form-urlencoded

user_login=<TEST_USER>&user_email=<CONTROLLED_EMAIL>&role=<ADMIN_EQUIVALENT>
```

Positive: authoritative role API/database shows elevated capability, not merely a reflected field.

### Invitation authority revocation

Admin A invites controlled B as admin; root admin removes A before B accepts. Test whether the pending grant survives and whether product policy requires revocation. Positive only if B becomes admin contrary to documented revocation semantics. Do not assume all delegated invitations must die with inviter removal.

### Capability declaration versus runtime

In a local test chain/plugin sandbox, remove a declared `requires_*` marker while retaining code that invokes the capability. If upload succeeds, invoke a harmless controlled capability. Positive: runtime dispatch occurs although the environment did not enable it. This pattern requires both admission and runtime evidence.

### Privileged object methods

For endpoints that let a regular user read/edit/delete admin-owned conversations, first test a harmless title change on a controlled admin conversation. Although cross-object access overlaps IDOR, classify as privesc when the core capability is admin conversation management available to regular users.

## Detection signals

- Low user's identity appears in audit log for an admin-only action.
- Authoritative membership/role endpoint shows elevation.
- A restricted action changes durable state and admin observes it.
- Runtime capability executes despite disabled capability declaration.
- Alternate channel succeeds while the same principal/action control is denied.

Use four controls: admin-success, low-denied normal path, low-variant path, and read-after-write. Capture role claims before and after.

After completing these checks, explore adjacent privilege-escalation surface the checklist did
not cover — the skill is a floor, not a ceiling.

## Stop conditions (verified negatives)

Each stop condition below carries one of the 12 categories from [`skills/references/negative-control-taxonomy.md`](../references/negative-control-taxonomy.md). Apply ALL applicable labels. Never file a finding that triggers any category below.

**Decision split (apply separately, never collapse):**
- `technically_vulnerable`: does a low principal gain a higher-role capability?
- `in_scope`: is the affected asset/runtime covered by policy?
- `program_reportable`: does the durable privilege gain meet the threshold?
A finding can be yes/yes/no, yes/no/yes, etc. A real escalation on an excluded runtime, or a label-only change, is not submit-worthy.

- `[expected_product_behavior]` The action is delegated to all authenticated users or the low user owns a non-role-restricted object. `[technical_placeholder]`
- `[control_exists_elsewhere]` `200` only queues a job later rejected by the authoritative role check. `[technical_placeholder]`
- `[missing_attacker_control]` Local escalation requires prior administrator control, debug mode, or attacker-created symlinks unavailable to the low principal. Empirical: H1 `1961655` (informative — "Renaming/aliasing relative symbolic links potentially redirects them to supposedly inaccessible locations").
- `[theoretical_without_oracle]` A role label changes but no higher-role read/write is proven. `[technical_placeholder]`
- `[real_but_below_program_impact_threshold]` Email/username disclosure plus hypothetical brute force does not establish admin capability. `[technical_placeholder]`
- `[out_of_scope_asset]` Escalation exists only in an excluded local Windows/runtime configuration. Empirical: H1 `2941920` (informative — "Elevation of Privileges (EoP) vulnerabilities related to the some easy_options on Windows").
- `[duplicate_root_cause]` The privileged action is the same access-control cause/fix already tracked. `[technical_placeholder]`
- `[technically_not_vulnerable]` Cross-user conversation access without acquisition of a higher role/capability is an access-control/IDOR claim, not privilege escalation. Empirical: H1 `3103849` (informative — "Privilege Escalation leads to Unauthorized Access to Private Conversations By any Regular user  [Read , Edit and Delete]"; full detail shows object access but no higher role).

## Anti-patterns

- Do not grant persistent admin rights to uncontrolled accounts.
- Do not delete conversations, users, files, or revoke real admins.
- Do not submit test content to real programs through a bypassed restriction.
- Do not run DLL/service/file-write LPE payloads on production; use disposable VMs and harmless canary files.
- Do not call every authorization failure privilege escalation; prove a higher-role capability.

## Minimal reproducer

```python
import os, requests

base = os.environ["TARGET_BASE"].rstrip("/")
low = os.environ["LOW_TOKEN"]
object_id = os.environ["CONTROLLED_OBJECT_ID"]
r = requests.post(base + "/api/<PRIVILEGED_ACTION>",
    headers={"Authorization": f"Bearer {low}"},
    json={"object_id": object_id, "value": "PRIVESC_CANARY"}, timeout=15)
print(r.status_code, r.text[:300])
# Verify with an admin read and immediately restore the controlled object.
```

## Evidence basis and limits

Derived from seven full reports: H1 `2081930`, `2450685`, `2930811`, `3303136`, `3103849`, `2999394`, and `3025797`. The PII-only report was retained as a negative boundary: disclosure plus hypothetical brute force is not privilege escalation. Positive patterns cover alternate APIs, runtime capabilities, invitation revocation, regular-user admin operations, role injection, and missing backend role checks.

Negatives in this skill are partly empirical (3 disclosed non-accepted Privilege Escalation reports in the local corpus) and partly structural from arXiv 2511.18608 / ESEM 2021 — see `skills/references/negative-control-taxonomy.md` for provenance.

## Web-Verification Augment (2026-07-22)

- Local negatives: 3 total (3 informative): H1 `1961655`, `2941920`, `3103849`; IDs, titles, and substates verified in JSONL.
- Study-only taxonomy: delegated action, late role check, label-only change, below-threshold disclosure, and duplicate-root-cause cases are `[technical_placeholder]`; local full detail was consulted for H1 `3103849`.

## AI-assisted augment (NahamSec seed)

Transferable techniques from Ben Sadeghipour (NahamSec), with the trust-chain point drawn
from the AI-testing discussion, public PlexTrac "Homework for Hackers" webinar
(`Ue-OIJoM0bA`). Guardrail: model output is a hypothesis, not evidence — confirm every
candidate against a live target oracle and the shared
[negative-control taxonomy](../references/negative-control-taxonomy.md); never paste
unsanitized target data into an unapproved model
(`nahamsec-ai-sanitize-before-sharing`, CWE-200).

- **AI/agent service identity as a vertical-escalation surface
  (`nahamsec-ai-map-full-trust-chain`).** When an assistant or automation executes under an
  identity with broader capabilities than the invoking user, map what actions that identity
  can take; if untrusted input can steer it, a low-privilege user may reach an admin-only
  operation through it. Confirm the escalation with a separately verified privileged outcome;
  only where AI testing is authorized.
- **Neighbor privileged-endpoint ideas (`nahamsec-ai-neighbor-path-ideas`).** From one
  admin-only route, ask an approved model for likely sibling privileged operations and their
  role parameters/capability flags; test each from the low-privilege principal.

## Version boundaries

Each row is a real, machine-readable OSV/GHSA entry bounding the RBAC / admin-framework authorization surface for this class. Use it as a "what's already been fixed" filter — a target on or above the `fixed` boundary is not a bug candidate without independent reproduction.

| package (ecosystem) | GHSA / CVE | severity | introduced | fixed | summary |
|---|---|---|---|---|---|
| spring-security-core (Maven) | GHSA-hh32-7344-cg2f / CVE-2022-22978 | critical | 5.5.0 | 5.5.7 | Authorization bypass via RegexRequestMatcher |
| parse-server (npm) | GHSA-8xq9-g7ch-35hg / CVE-2024-47183 | high | 0 | 6.5.9 | Custom object ID → acquire role privileges |
| django (PyPI) | GHSA-m6gj-h9gm-gw44 / CVE-2020-24583 | high | 2.2a1 | 2.2.16 | Incorrect default permissions (file cache) |
| django (PyPI) | GHSA-p99v-5w3c-jqq9 / CVE-2021-33571 | high | 2.2a1 | 2.2.24 | Access-control bypass via URL-path validation |
| directus (npm) | GHSA-pmf4-v838-29hg / CVE-2025-24353 | moderate | 0 | 11.2.0 | Privilege escalation via the Share feature |

**Usage:** when a target pulls in one of these at version `x`, check `x` against `introduced`/`fixed`. If `x >= fixed`, the framework already enforces the role/permission check — look at target-level custom roles and endpoint guards instead. SEMVER `fixed` is exclusive (first safe version); Django's `2.2a1` introduced-bound means the 2.2 line before the patch release. Data from OSV.dev (`api.osv.dev/v1/query`) + GitHub Advisory DB, fetched 2026-07-22; full dataset in `knowledge-sources/engineering-sources/version-boundaries.md`.

**Caveat:** the table proves the package's *known* vulnerable range, not that the *target's* call site reaches it — the target's own authorization layer may sit in front of the affected component. Treat it as a **filter**, not a finding.
