---
name: auth-bypass-hunter
description: Hunt improper authentication in OTP/2FA, OAuth, bot keys, sessions, and supposedly private API routes. Load when identity proof, token issuance, trusted-device state, or authentication middleware may be missing or bound to the wrong subject. Triggers — Improper Authentication Generic, authentication bypass, 2FA or OTP bypass, unauthenticated private endpoint. Prefer this over privesc-hunter when the failure is proving identity at all rather than exceeding an already-held role.
---

# Authentication-Bypass Hunter

Use two disposable accounts and authorized endpoints. Separate authentication from authorization: this skill asks whether the server establishes the claimed identity without completing the required proof.

## Model the authentication state machine

Write states and accepted transitions: anonymous → password-verified → OTP-pending → fully authenticated; OAuth request → consent → code → token; invited → email-verified → active. Record every cookie, transaction ID, token subject, and expiry at each state. Then attempt only one illegal edge at a time.

## Recon signals

- OTP values or verification flags in API responses; four-digit defaults such as `0000`.
- Session cookies issued before OTP completion, especially refresh/trust-device cookies.
- Email/phone change endpoints that preserve trusted-device status or active sessions.
- OAuth app fields `trusted`, scopes, `redirect_uri`, duplicate parameters, and authorization endpoints usable from an image/link.
- Composite bot/API credentials parsed with delimiters, e.g. `<id>-<token>`, where an empty component may become `null`.
- Documentation labels such as `USER OPERATION`/private and sibling endpoints that require HMAC/bearer credentials.
- Same endpoint succeeding with missing, malformed, fake, expired, or another account's authentication fields.

## Test recipes

### OTP secrecy and acceptance

Request an OTP for a controlled account. Inspect the response body, headers, and follow-up transaction; never brute-force. Submit one known-invalid value such as `0000` only if rate/scope rules permit.

```http
POST /api/auth/otp/request HTTP/1.1
Content-Type: application/json

{"phone":"<CONTROLLED_PHONE>"}
```

Positive: response includes the OTP, or an invalid value advances to authenticated state. A generic success acknowledging delivery is normal.

### Pre-2FA session promotion

Log in with valid controlled credentials and stop at OTP. Capture cookies, delete or alter one cookie at a time, then request a page/API that requires full authentication. A report pattern removed a refresh cookie and the server treated the remaining session as complete.

```bash
curl -i 'https://<TARGET>/account' \
  -H 'Cookie: <OTP_PENDING_SESSION_WITH_ONE_COOKIE_REMOVED>'
```

Positive: protected user data or a server-authenticated identity, not merely a redirect or page shell.

### Identity-change/trusted-device binding

Mark an attacker-controlled device trusted, then change the account email/phone to a second controlled identity. Check whether trust remains attached to the browser session when it should attach to the verified identity and whether old sessions are revoked.

Positive: login/impersonation as the new identity without its OTP or verification. Restore the address.

### OAuth trust and consent

Create an app in an authorized sandbox. Test duplicated or conflicting trust parameters only against your two accounts.

```text
trusted=0&trusted=1
GET /login/oauth/authorize?client_id=<CONTROLLED_CLIENT>&redirect_uri=https://<CONTROLLED_HOST>/cb&scope=<MINIMAL_SCOPE>
```

Positive: the second controlled user receives no consent screen and the resulting authorization code can be exchanged for a token whose subject is that user. Redact client secret and token.

### Null component in composite credentials

If a bot key parses as `id-token`, test `<CONTROLLED_USER_ID>-` with no session.

```http
POST /rooms/<CONTROLLED_ROOM>/<CONTROLLED_USER_ID>-/messages HTTP/1.1
Content-Type: text/plain

AUTH_CANARY
```

Positive: the canary is attributed server-side to that controlled user. An error difference is not enough.

### Missing middleware by sibling comparison

Send no credentials, then deliberately fake credentials, to a documented private endpoint and two sibling private endpoints.

```bash
curl -sS -X POST 'https://<TARGET>/api/<PRIVATE_OPERATION>'
curl -sS -X POST 'https://<TARGET>/api/<PRIVATE_OPERATION>' \
  -d 'clientId=999&nonce=1&signature=<FAKE>'
```

Positive: the candidate returns protected data while siblings return a consistent authentication error, and fake auth is ignored.

## Detection and false positives

Positive proof is an authenticated identity (`/me`), protected data, token subject, or action attributed to the controlled victim without the required proof. Compare missing, malformed, invalid, pending, and valid authentication.

Reject these false positives:

- A route documented as private but returning intentionally public/static data.
- Cookies created pre-OTP but blocked on protected endpoints.
- OAuth code that cannot be exchanged or yields the attacker's own subject.
- OTP echoed only in an explicitly non-production test environment.
- `200` containing `error:true`, an anonymous page shell, or no durable action.
- Username/email enumeration without identity establishment.

After completing these checks, explore adjacent authentication surface the checklist did not
cover — the skill is a floor, not a ceiling.

## Stop conditions (verified negatives)

Each stop condition below carries one of the 12 categories from [`skills/references/negative-control-taxonomy.md`](../references/negative-control-taxonomy.md). Apply ALL applicable labels. Never file a finding that triggers any category below.

**Decision split (apply separately, never collapse):**
- `technically_vulnerable`: is authentication actually bypassed?
- `in_scope`: does the program's bounty policy cover this asset?
- `program_reportable`: does the demonstrated account capability meet its threshold?
A finding can be yes/yes/no, yes/no/yes, etc. Do not submit on `technically_vulnerable` alone.

- `[expected_product_behavior]` A profile/reset landing page is intentionally public but still requires a valid secret before account change. Empirical: H1 `2213337` (informative — "access to profile & reset password page without authentication").
- `[control_exists_elsewhere]` A pre-2FA/leaked cookie cannot pass the private-route middleware or complete a privileged action. Empirical: H1 `2479622` (informative — "2FA Bypass via Leaked Cookies").
- `[missing_attacker_control]` Connection/auth reuse depends on the client supplying its own credentials or tokens. Empirical: H1 `3595753` (N/A — "Connection Reuse Ignores OAuth Bearer Token Mismatch") and `3786077` (N/A — "SOCKS5 no-auth accepted despite username/password-only authentication").
- `[theoretical_without_oracle]` A captured response or accepted-looking OTP produces no fresh authenticated session or protected read. Empirical: H1 `3120790` (informative — "Session Replay Attack Allows Authentication Bypass via Captured Login Responses Allowing Bypass of 429 Too many attempts for Multiple Failed Logins").
- `[real_but_below_program_impact_threshold]` OTP timing/reuse oddity yields no unauthorized account capability. Empirical: H1 `2588810` (informative — "TOTP Authenticator implementation Accepts Expired Codes").
- `[duplicate_root_cause]` The authentication flaw is already tracked under the same session/OTP cause. Empirical: H1 `3666576` (duplicate — "Negotiate Authentication Premature on Connection Reuse") and `2529780` (duplicate — "Improper Authentication - 2FA OTP Reusable").
- `[technically_not_vulnerable]` Alternate-path requests still reach the same server-side authentication gate. `[technical_placeholder]`

## Anti-patterns

- Do not brute-force OTPs, passwords, IDs, or composite keys.
- Do not request default credentials on third-party devices or mint broad OAuth scopes.
- Do not take over real accounts, retain tokens, or post messages as real users.
- Do not label missing authorization on one object as authentication bypass.
- Do not use open redirect or CORS alone as proof.

## Minimal reproducer

```python
import os, requests

base = os.environ["TARGET_BASE"].rstrip("/")
path = os.environ.get("PRIVATE_PATH", "/api/<PRIVATE_OPERATION>")
cases = [("none", {}), ("fake", {"Authorization": "Bearer INVALID"})]
for name, headers in cases:
    r = requests.post(base + path, headers=headers, timeout=15)
    print(name, r.status_code, r.text[:300])
# Add a valid controlled request and compare authenticated subject/data fields.
```

## Evidence basis and limits

Derived from six full reports: H1 `2885636`, `1148364`, `2635315`, `3329310`, `2315420`, and `3676308`. Patterns cover trusted-device persistence after identity change, OAuth trusted-app tampering, OTP leakage, null-token bot impersonation, pre-2FA cookie state, and missing private-route middleware.

Negatives in this skill are partly empirical (10 disclosed non-accepted Improper Authentication - Generic reports in the local corpus) and partly structural from arXiv 2511.18608 / ESEM 2021 — see `skills/references/negative-control-taxonomy.md` for provenance.

## Web-Verification Augment (2026-07-22)

- Local negatives: 10 total (6 informative, 2 not-applicable, 2 duplicate); representative exact-title anchors are listed above.
- Study-only taxonomy: same-gate alternate-path rejection remains `[technical_placeholder]`; no body fetch was required.

## AI-assisted augment (NahamSec seed)

Transferable techniques from Ben Sadeghipour (NahamSec), public PlexTrac "Homework for
Hackers" webinar (`Ue-OIJoM0bA`). Guardrail: model output is a hypothesis, not evidence —
confirm every candidate against a live target oracle and the shared
[negative-control taxonomy](../references/negative-control-taxonomy.md); never paste
unsanitized target tokens, source, or data into an unapproved model
(`nahamsec-ai-sanitize-before-sharing`, CWE-200).

- **Neighbor route ideas for unauthenticated surfaces (`nahamsec-ai-neighbor-path-ideas`).**
  From one observed private/authenticated route, ask an approved model for likely sibling
  endpoints and undocumented auth/OTP/OAuth callback paths; probe slowly against nonexistent
  controls, then confirm which actually skip the identity check.
- **Second-look on unfamiliar token output (`nahamsec-ai-context-second-look`).** Use a model
  to hypothesize the structure of an unfamiliar JWT/OAuth/session artifact and which claim or
  signature step might be unverified; confirm the missing check dynamically (e.g. the altered
  token is accepted server-side), never from the model's reading alone.

## Version boundaries

Each row is a real, machine-readable OSV/GHSA entry bounding the JWT/SAML/OAuth verification surface for this class. Use it as a "what's already been fixed" filter — a target on or above the `fixed` boundary is not a bug candidate without independent reproduction.

| package (ecosystem) | GHSA / CVE | severity | introduced | fixed | summary |
|---|---|---|---|---|---|
| jsonwebtoken (npm) | GHSA-qwph-4952-7xr6 / CVE-2022-23540 | moderate | 0 | 9.0.0 | Signature bypass via insecure default alg in `jwt.verify()` |
| pyjwt (PyPI) | GHSA-r9jw-mwhq-wp62 / CVE-2017-11424 | high | 0 | 1.5.1 | RS256↔HS256 key-confusion |
| python-jose (PyPI) | GHSA-6c5p-j8vq-pqhj / CVE-2024-33663 | critical | 0 | 3.4.0 | Algorithm confusion with OpenSSH ECDSA keys |
| passport-saml (npm) | GHSA-m974-647v-whv7 / CVE-2022-39299 | high | 0 | 3.2.2 | SAML signature bypass via multiple root elements |
| nimbus-jose-jwt (Maven) | GHSA-f6vf-pq8c-69m4 / CVE-2019-17195 | critical | 0 | 7.9 | Improper check on unusual/exceptional JWT conditions |

**Usage:** when a target pulls in one of these at version `x`, check `x` against `introduced`/`fixed`. If `x >= fixed`, the library already pins the algorithm / rejects the forged signature — look at target-level `verify()` options and trust config instead. SEMVER `fixed` is exclusive (first safe version). Data from OSV.dev (`api.osv.dev/v1/query`) + GitHub Advisory DB, fetched 2026-07-22; full dataset in `knowledge-sources/engineering-sources/version-boundaries.md`.

**Caveat:** the table proves the package's *known* vulnerable range, not that the *target's* call site reaches it — a target may explicitly pass `algorithms:[...]` and defeat the default-alg bug even on an old version. Treat it as a **filter**, not a finding.
