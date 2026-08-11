---
name: info-disclosure-hunter
description: Find sensitive data exposed through serialization, logs, public artifacts, cross-origin resources, and unsafe file processing. Load when responses, build output, JSON variants, uploads, or dynamic JavaScript may reveal data beyond the requesting user's intended view. Triggers — Information Disclosure, secret or PII exposure, public CI log or repository leak, JSON response contains hidden fields.
---

# Information-Disclosure Hunter

Test only authorized assets. Treat the disclosure as proven only when the response contains a field or artifact that the test identity should not receive; never validate a leaked credential with destructive or write-capable calls.

## Method

1. Inventory representations of the same resource: HTML, `.json`, GraphQL, download/export, print, preview, mobile API, service worker, and cached/CDN variants.
2. Establish a public or low-privilege baseline, then request the same object through each representation. Diff field names, not merely byte length.
3. Trace where secrets are produced: CI logs, generated repositories, source maps, document previews, image converters, support exports, and dynamically generated JavaScript.
4. Classify the exposed material before testing: public profile data, private metadata, PII, session material, API token, configuration, or cross-tenant content.
5. Confirm the least-invasive consequence. For a token, prefer a read-only identity endpoint and redact it immediately. For PII, use two controlled accounts.

## Recon signals

- Suffixes and content negotiation: `/<object>/<id>.json`, `.xml`, `?format=json`, `Accept: application/json`, exports and print views.
- GraphQL operations that return `email`, `phone`, `reporter`, `owner`, `billing_*`, `secret`, `token`, `internal`, or nested `user` objects.
- Public logs named `live.log`, build logs, artifacts, source maps, environment dumps, and debug endpoints.
- Public Git repositories created by bots, triage accounts, CI jobs, or reproduction workflows; search filenames and commit history for target hostnames and secret-shaped keys.
- Upload/preview pipelines for SVG, PDF, office files, or images processed by native libraries.
- Same-origin-exempt script loads such as `sw.js` whose body varies with authentication cookies.
- Public cloud object listings or configuration JSON with credentials, bucket names, internal URLs, or identity-provider metadata.

## Test recipes

### Serialization drift

Start from an object visible in the UI, then request its JSON representation unauthenticated and authenticated. One report found a report JSON route serializing internal reporter attributes; another found private fields returned by a GraphQL collaborator operation.

```http
GET /reports/<CONTROLLED_REPORT_ID>.json HTTP/1.1
Host: <TARGET>
Accept: application/json
```

Search the parsed response for field names such as `email`, `phone`, `backup`, `secret`, `token`, `internal`, and unexpected nested account objects. Do not include any discovered value in the final PoC; show redacted keys and type/length.

### Public artifact and log sweep

Use known project/account names, not broad credential harvesting. Inspect current and historical CI artifacts, public logs, bot repositories, and commits.

```bash
curl -fsS 'https://<CI_HOST>/<CONTROLLED_JOB>/logs/live.log' \
  | rg -n -i 'authorization:|token|secret|api[_-]?key|password'
```

If a candidate token appears, test only an approved read-only identity/list endpoint:

```bash
curl -sS 'https://<API_HOST>/api/v1/account' \
  -H 'Authorization: Bearer <REDACTED>'
```

Stop after identity/scope confirmation; request rotation.

### Cross-origin dynamic script

Compare a JavaScript resource with and without a controlled authenticated cookie. A report pattern used a service worker containing an authenticated `userId`; classic script inclusion bypassed normal fetch read restrictions.

```html
<script src="https://<TARGET>/sw.js"></script>
<script>
  // Read only a documented global populated by the script.
  console.log(self.__INITIAL_STATE__?.userId ?? "not exposed");
</script>
```

Positive: an unrelated origin can recover a stable controlled-user identifier. A resource merely loading cross-origin is normal.

### Parser/preview isolation

Upload a benign crafted file that encodes a unique canary, then fetch only the resulting preview. A high-signal report used an SVG/native conversion memory bug that emitted unrelated server memory. Do not loop for hours or seek real secrets.

```text
Upload: avatar.svg containing CANARY_<RANDOM>
Fetch: preview as PNG using a cache-busting filename
Inspect: strings output for data not present in the upload
```

Positive: repeated previews contain unrelated request headers, configuration fragments, or other users' canaries. Random image corruption alone is not disclosure.

## Detection signals

- A protected field exists in JSON/GraphQL but is absent from the authorized UI contract.
- Public CI/repository content contains an active-looking secret plus a read-only response proving its subject or scope.
- Authenticated and unauthenticated representations differ in an unintended way, or two controlled users receive each other's fields.
- A cross-origin script exposes a user-specific identifier to the embedding origin.
- A generated preview contains bytes never supplied by the tester.

Record status, content type, cache headers, field paths, and a redacted excerpt. Repeat once with a fresh controlled object to exclude stale cache.

After completing these checks, explore adjacent information-exposure surface the checklist did
not cover — the skill is a floor, not a ceiling.

## Stop conditions (verified negatives)

Each stop condition below carries one of the 12 categories from [`skills/references/negative-control-taxonomy.md`](../references/negative-control-taxonomy.md). Apply ALL applicable labels. Never file a finding that triggers any category below.

**Decision split (apply separately, never collapse):**
- `technically_vulnerable`: is the code actually exploitable?
- `in_scope`: does the program's bounty policy cover this asset?
- `program_reportable`: does the demonstrated impact meet the program's threshold?
A finding can be yes/yes/no, yes/no/yes, etc. Do not submit on `technically_vulnerable` alone.

- `[expected_product_behavior]` The audit file, repository metadata, user directory, or disclosure is intentionally public. Empirical: H1 `3272982` (N/A — "Vulnerability Report: Public Exposure of Security Audit File"), `2853023` (N/A — "Information Disclosure at : https://curl.se/.mailmap"), and `2915426` (N/A — "Git repository found").
- `[control_exists_elsewhere]` A reset token is redacted/expired and unusable, or redirects strip credentials before transmission. `[technical_placeholder]`
- `[missing_attacker_control]` The value belongs only to the requesting account or requires an operator opt-in to forward it. Empirical: H1 `3595764` (N/A — "CURLOPT_UNRESTRICTED_AUTH Dangerous Default Documentation Gap").
- `[theoretical_without_oracle]` A path suggests leakage, but the controlled receiver records no secret, cookie, token, or cross-user bytes. Empirical: H1 `376004` (informative — "Potential IP revealing using UNC Path in Windows File Picker").
- `[technically_not_vulnerable]` A `200` is an error envelope or the returned identifier grants no access. Empirical: H1 `268221` (informative — "No Confirmation Email For Email Change").
- `[real_but_below_program_impact_threshold]` Only usernames, filenames, generic metadata, or public program facts are exposed. Empirical: H1 `2981756` (informative — "Wordpress users Disclosure") and `3331764` (N/A — "Confirmed Security Misconfigurations on curl.se (BREACH, Missing Security Headers, ETag Info Disclosure)").
- `[duplicate_root_cause]` The same disclosure/auth failure is already tracked. Empirical: H1 `2486086` (duplicate — "Two-factor authentication bypass lead to information disclosure about the program and all hackers participate") and `2404415` (duplicate — "View any user email using the Team's audit log section").

## Anti-patterns

- Do not enumerate other users' report IDs, phone numbers, buckets, or documents.
- Do not deploy, delete, bill, transfer, or change settings with a discovered credential.
- Do not reproduce memory leakage at volume; one or two canary-based samples suffice.
- Do not publish real tokens, cookies, emails, internal hosts, or PII. Replace with `<REDACTED>`.
- Do not call any difference in HTML/JSON a leak; tie it to an explicit authorization expectation.

## Minimal reproducer

```python
import os, requests

url = os.environ["TARGET_URL"]
headers = {"Authorization": f"Bearer {os.environ['LOW_TOKEN']}"} if os.getenv("LOW_TOKEN") else {}
r = requests.get(url, headers=headers, timeout=15)
print("status", r.status_code, "type", r.headers.get("content-type"))
if "json" in r.headers.get("content-type", ""):
    data = r.json()
    sensitive_names = {"email", "phone", "token", "secret", "backup_codes"}
    print("candidate keys", sorted(sensitive_names & set(map(str, data.keys()))))
# Print keys and redacted shapes, never raw secret values.
```

## Evidence basis and limits

Derived from six full reports: H1 `3000510`, `2032716`, `2107680`, `2937622`, `2915647`, and `2244229`. Patterns cover serialization drift, GraphQL leakage, native preview memory exposure, public reproduction repositories, CI-log tokens, and cross-origin dynamic JavaScript. Disclosed-report survivorship bias means this does not describe rejected false positives or closed ecosystems.

Negatives in this skill are partly empirical (19 disclosed non-accepted Information Disclosure reports in the local corpus) and partly structural from arXiv 2511.18608 / ESEM 2021 — see `skills/references/negative-control-taxonomy.md` for provenance.

## Web-Verification Augment (2026-07-22)

- Local negatives: 19 total (9 informative, 8 not-applicable, 2 duplicate); all IDs, titles, and substates were checked in the JSONL, with representative anchors above.
- Study-only taxonomy: unusable-token/redirect controls and no-receiver-oracle cases remain `[technical_placeholder]`; no body fetch was required.

## AI-assisted augment (NahamSec seed)

Transferable techniques from Ben Sadeghipour (NahamSec), public PlexTrac "Homework for
Hackers" webinar (`Ue-OIJoM0bA`), applied to CWE-200. Guardrail: model output is a
hypothesis, not evidence — confirm every candidate against a live target oracle and the
shared [negative-control taxonomy](../references/negative-control-taxonomy.md).

- **Sanitize before sharing — the disclosure discipline you are testing for
  (`nahamsec-ai-sanitize-before-sharing`).** When using a model on recon output, logs,
  responses, or draft reports, classify first and strip secrets, tokens, and PII; replace
  domains and identifiers with stable placeholders; prefer a local or contractually
  approved model. Redaction that preserves token *shape* still leaks structure, and
  screenshots, filenames, and model history can carry hidden identifiers. This is CWE-200
  applied to your own workflow.
- **Neighbor representation ideas (`nahamsec-ai-neighbor-path-ideas`).** From one leaky
  variant, ask an approved model for likely siblings — `.json`/`.xml` suffixes, export and
  print routes, CI artifact/log names, source-map paths — then diff each against a
  nonexistent control and against the authorized UI contract before claiming a leak.
- **Second-look on unfamiliar output (`nahamsec-ai-context-second-look`).** Use a model to
  hypothesize what an unfamiliar field, header, or serialized blob is; accept only when a
  low-privilege vs authorized diff on the target confirms it exposes data the identity
  should not receive.

## Version boundaries

| Package | OSV-verified affected range(s) | Advisory |
|---|---|---|
| Django | `2.2–<2.2.26`; `3.2–<3.2.11`; `4.0–<4.0.1` | `GHSA-8c5j-9r9f-c6w8` / `CVE-2021-45116` |
| Django | `1.7–<1.7.11`; `1.8a1–<1.8.7`; `1.9a1–<1.9rc2` | `GHSA-6wcr-wcqm-3mfh` / `CVE-2015-8213` |
| Django | `1.3–<1.3.6`; `1.4–<1.4.4` | `GHSA-r7w6-p47g-vj53` / `CVE-2013-0305` |
| Django | `1.11.8–<1.11.10`; `2.0a1–<2.0.2` | `GHSA-rf4j-j272-fj86` / `CVE-2018-6188` |
If no row matches, pivot to target-level logging configuration, error handlers, debug flags, exposed endpoints, and serializers; a package version alone neither proves nor disproves disclosure.
