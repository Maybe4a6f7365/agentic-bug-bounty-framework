---
name: access-control-hunter
description: Hunt generic access-control failures across alternate interfaces, invitations, identity lifecycle, and tenant boundaries. Load for REST/GraphQL/API parity checks, password-reset binding, SCIM/SSO provisioning, or features whose UI restriction may not be enforced server-side. Triggers — Improper Access Control Generic, broken access control, alternate API bypasses a UI restriction, invitation or provisioning authorization. Prefer idor-hunter when the request carries an attacker-changeable object identifier, and privesc-hunter when the goal is reaching a higher role.
---

# Generic Access-Control Hunter

Use only on assets and accounts explicitly authorized for testing. This skill targets authorization-policy gaps that are broader than a single object ID: a restriction exists in one channel or lifecycle state but disappears in another.

## Build the authorization matrix

Create two controlled users in separate tenants where possible: `LOW_A` and `ADMIN_B`. Record each user's cookies, bearer/API credentials, tenant, verified-email state, role, and suspension state. For every sensitive action, capture the normal request and write its expected predicate, for example:

`may_accept(invitee, invitation) = email_verified && invitation.email == user.email && inviter.active`

Then vary one predicate at a time. Prioritize mismatches between:

- browser UI and REST/GraphQL/API-key endpoints;
- active, invited, suspended, removed, and password-reset states;
- SSO/SCIM fields such as `username`, `email`, verified domain, and immutable subject;
- client-side plan or role gates and the backing mutation;
- primary host and trusted redirect/proxy/helper subdomains.

Do not collapse this class into IDOR. If only an object reference changes, load `idor-hunter`. Here, hunt missing policy enforcement across interfaces or state transitions.

## Recon signals

- Duplicate actions exposed as `/graphql`, `/api/v1/...`, mobile endpoints, API-key routes, imports, webhooks, and admin UI forms.
- Requests containing `role`, `visibility`, `trusted`, `verified`, `email`, `username`, `organization_id`, `team_handle`, `redirectUrl`, or SCIM `userName`/`emails`.
- Invitation acceptance, password reset, account recovery, SAML/SSO and SCIM provisioning.
- UI buttons hidden for banned, free-plan, member, or unverified accounts while a request remains discoverable in history or JavaScript.
- Reverse proxies whose routing changes with `Host`, `X-Forwarded-Host`, path prefixes, or alternate ports.
- Responses that include a reset JWT, authorization code, or internal resource before the user proves the corresponding identity.

## Test recipes

### 1. Channel-parity test

Perform a harmless action through the UI, then replay its equivalent with another credential type or endpoint. A disclosed pattern allowed a submission-restricted user to call an API-key route even though browser and direct requests returned `403`. Use a draft or sandbox object; never send test content to a real third party.

```http
POST /api/v1/<RESOURCE> HTTP/1.1
Authorization: Basic <REDACTED_API_CREDENTIAL>
Content-Type: application/json

{"tenant":"<SANDBOX>","title":"access-control-probe"}
```

Positive: the restricted identity creates the sandbox object and it appears in a subsequent read. A different status alone is not enough.

### 2. Invitation and identity-binding test

Create an invitation to a controlled victim address. Attempt acceptance from an account that merely claims that address but has not verified it. Also remove or demote the inviter before acceptance and retest. A real report pattern showed an owner invitation accepted by an unverified account; another showed identity provisioning where keeping the original SCIM `username` while replacing `email` moved password recovery to attacker control.

```json
{
  "userName": "<VICTIM_IMMUTABLE_ID>",
  "emails": [{"value": "<ATTACKER_VERIFIED_EMAIL>", "primary": true}]
}
```

Require proof that the protected membership, email, or recovery destination actually changed. Stop before resetting a real user's password.

### 3. Password-reset context binding

Start resets for two controlled accounts. Compare which transaction values bind the OTP, reset JWT, browser telemetry/session object, and final password update. Substitute only one cross-account value per request.

```http
POST /orchestrator/v1/password_reset/<STEP> HTTP/1.1
Content-Type: application/json

{"reset_context":"<VICTIM_CONTEXT>","otp":"<ATTACKER_OTP>","new_password":"<TEST_VALUE>"}
```

Positive: attacker OTP authorizes the victim reset context or the final account identity follows a client-controlled field rather than the reset transaction.

### 4. Proxy and trusted-host boundary

For a proxy/helper endpoint, keep the destination path constant and replace only the authority-routing input. One report used an exposed HTTPS proxy with an internal hostname in `Host`.

```bash
curl -sk 'https://<PROXY_HOST>:<PORT>/<ROUTE>' \
  -H 'Host: <INTERNAL_TEST_HOST>'
```

Use only an in-scope internal hostname supplied by the program. Positive evidence is internal-only content or a backend-specific marker, not merely a TLS or gateway error.

## Detection and evidence

Demand a three-part proof:

1. Control: the same action is denied through the documented path or for an intentionally unauthorized state.
2. Variant: exactly one channel, lifecycle, or binding changes.
3. Consequence: a read-after-write, audit entry, membership list, token subject, or resource body proves unauthorized access.

Strong signals include `200/201` plus a protected object, a reset token whose subject is the other controlled user, an invitation accepted after revocation, or a server-side role/visibility change. Record request IDs and restore state.

After completing these checks, explore adjacent authorization surface the checklist did not
cover — the skill is a floor, not a ceiling.

## Stop conditions (verified negatives)

Each stop condition below carries one of the 12 categories from [`skills/references/negative-control-taxonomy.md`](../references/negative-control-taxonomy.md). Apply ALL applicable labels. Never file a finding that triggers any category below.

**Decision split (apply separately, never collapse):**
- `technically_vulnerable`: is the authorization boundary actually crossed?
- `in_scope`: does the program's bounty policy cover this asset?
- `program_reportable`: does the demonstrated capability meet its threshold?
A finding can be yes/yes/no, yes/no/yes, etc. Do not submit on `technically_vulnerable` alone.

- `[expected_product_behavior]` The endpoint/action is public or deliberately delegated to all authenticated team members. Empirical: H1 `2569993` (informative — "Reports submitted by a non 2fa setupped user account can be transferred to a 2fa require submission program ").
- `[control_exists_elsewhere]` `200` queues an action later rejected by the authoritative permission check. `[technical_placeholder]`
- `[missing_attacker_control]` The identity/verb transition requires trusted proxy or administrator configuration. Empirical: H1 `3475613` (N/A — "HAProxy Connection Reuse leads to IP Spoofing and mTLS Context Smuggling").
- `[theoretical_without_oracle]` UI restriction changes, but no forbidden read, write, or durable state change follows. Empirical: H1 `2679108` (informative — "Bypass comment restriction").
- `[real_but_below_program_impact_threshold]` A low-impact account-state action crosses a boundary without takeover or sensitive data. Empirical: H1 `2088808` (informative — "Disavowed an email without any authentication").
- `[duplicate_root_cause]` The same authorization/reset cause is already tracked. Empirical: H1 `2492631` (duplicate — "Reset the 2FA of the user which can lead to Account Takeover") and `3016540` (duplicate — "Enable 2FA without verifying the email").
- `[technically_not_vulnerable]` The server returns an error/empty object or derives the authorized subject from session, not supplied identity. `[technical_placeholder]`

## Anti-patterns

- Do not test with real victim addresses, transfer funds, accept real invitations, or complete account takeover.
- Do not brute-force IDs, internal hosts, OTPs, or reset tokens.
- Do not treat HTTP-vs-HTTPS reset links, open redirects, XSS, or IDOR as generic access control unless a distinct authorization-policy mismatch is demonstrated.
- Do not infer impact from client-side code; verify server state with controlled accounts.
- Do not reuse real tokens from reports. Use `<REDACTED>` placeholders in notes and PoCs.

## Minimal reproducer

```python
import os, requests

base = os.environ["TARGET_BASE"].rstrip("/")
restricted = os.environ["RESTRICTED_TOKEN"]
path = os.environ.get("TEST_PATH", "/api/v1/<SANDBOX_RESOURCE>")

r = requests.post(base + path,
    headers={"Authorization": f"Bearer {restricted}"},
    json={"name": "access-control-probe"}, timeout=15)
print(r.status_code, r.headers.get("content-type"), r.text[:500])
# Add a harmless GET to prove or disprove durable state; clean up if created.
```

## Evidence basis and limits

Derived from seven full disclosed reports: H1 `1888915`, `2967634`, `2831902`, `2312029`, `2885269`, `3178999`, and `3081691`. Their reusable patterns are channel mismatch, proxy routing, reset-context substitution, unauthenticated GraphQL fields, unverified invitation acceptance, SCIM identity rebinding, and trusted-subdomain token exposure. The corpus overrepresents Web/SaaS; use it as a hypothesis generator, not proof of coverage.

Negatives in this skill are partly empirical (8 disclosed non-accepted Improper Access Control - Generic reports in the local corpus) and partly structural from arXiv 2511.18608 / ESEM 2021 — see `skills/references/negative-control-taxonomy.md` for provenance.

## Trust boundaries and authorization matrices

Trust-boundary cross-checks distilled from disclosed third-party audits. Full extraction, sources, and URLs: [`skills/references/audit-invariants.md`](../references/audit-invariants.md).

- **Looked-up object re-binds to the acting subject.** A credential/device/record selected by an attacker-supplied ID must be verified to belong to the pending subject (`device.user == session.pending_user`), not trusted because the row exists. [source: Cure53 authentik ATH-01-010, 2023 — WebAuthn assertion validated against any device].
- **Tenant scoping holds at every tier.** Enforce isolation in GraphQL/REST resolvers, async job handlers, and internal service calls alike — never only at the front API. [source: Trail of Bits Vanta multi-tenant review, 2025].
- **Every route carries an explicit permission guard.** Enumerate routes; assert each names its ACL/permission rather than inheriting one by convention. [source: Trail of Bits PyPI TOB-PYPI-26 "Routes missing access controls", 2023].
- **Service-to-service identity binds to the transport, not a claim.** L4 authorization keys on the mTLS peer identity (SPIFFE `trust_domain`), never an application-layer header. [source: Trail of Bits/OSTIF Istio Ztunnel, 2025].
- **PEP calls the PDP for every access; a shared PDP isolates tenants.** In a multi-tenant policy engine one tenant's policies must not influence another's decision, and evaluation defaults to deny. [source: Trail of Bits Cedar/Rego/OpenFGA assessment, 2024].
- **Each role tier proves its own identity.** Distinct roles (e.g. whistleblower / receiver / admin) each require independent authentication; no tier inherits access from another. [source: Cure53 GlobaLeaks GL01-001 password-less receiver login, 2013].

## Web-Verification Augment (2026-07-22)

- Local negatives: 8 total (4 informative, 2 duplicate, 2 not-applicable); representative exact-title anchors are listed above.
- Study-only taxonomy: late authoritative rejection and session-derived-subject cases remain `[technical_placeholder]`; no body fetch was required.

## AI-assisted augment (NahamSec seed)

Transferable techniques from Ben Sadeghipour (NahamSec), with the trust-chain point drawn
from the AI-testing discussion, public PlexTrac "Homework for Hackers" webinar
(`Ue-OIJoM0bA`). Guardrail: model output is a hypothesis, not evidence — confirm every
candidate against a live target oracle and the shared
[negative-control taxonomy](../references/negative-control-taxonomy.md); never paste
unsanitized target data into an unapproved model
(`nahamsec-ai-sanitize-before-sharing`, CWE-200).

- **Neighbor alternate-interface ideas (`nahamsec-ai-neighbor-path-ideas`).** From one
  UI-restricted action, ask an approved model for the likely mobile-API, GraphQL, export,
  bulk, and legacy-versioned equivalents of the same operation; test each server-side
  against the authorization matrix rather than assuming the UI restriction is enforced.
- **Add AI/agent service identities to the authorization matrix
  (`nahamsec-ai-map-full-trust-chain`).** When an assistant or automation acts under a
  service identity broader than the caller, treat it as a distinct principal and check
  whether a low-privilege user can reach a restricted action through it. Confirm the crossing
  with a real, separately verified outcome; only where AI testing is authorized.

## Version boundaries

null — Generic access-control failures are application-logic flaws in policy code, middleware placement, endpoint guards, or identity-state transitions, not component-version flaws. Framework upgrades do not establish that every affected channel enforces the intended policy. Use target patch diffs and the authorization matrix to bound a fix.
