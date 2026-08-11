---
name: ssrf-hunter
description: Hunt server-side request forgery in URL fetchers, webhooks, importers, link previews, PDF/screenshot renderers, media proxies, and SSO/metadata discovery; escalate reachable internal services and cloud metadata into credential and RCE chains. Load when the server makes an outbound request to an attacker-influenced URL, host, IP, or scheme. Triggers — Server-Side Request Forgery, SSRF, server fetches a user-supplied URL, webhook or importer or preview or renderer reaches an internal host.
---

# SSRF Hunter

Test only authorized assets. SSRF is proven only when a server-initiated request reaches a
destination the attacker chose and an **out-of-band receiver you control** records it, or the
response returns bytes from an internal-only resource the tester cannot reach directly. Prove
*reach*; never pull, store, or use real internal credentials, and never port-scan internal
ranges at volume. Redact collector logs, internal hostnames, IPs, and tokens before committing.

## Method

1. **Inventory every server-initiated fetch.** Webhooks and callbacks, "import from URL",
   link preview/unfurl, avatar/image-from-URL, PDF/HTML/screenshot renderers, media/image
   proxies, RSS/feed readers, OIDC/SAML metadata-URL discovery, XML/SVG/PDF parsers with
   external entities, and any integration that dereferences a user-supplied address.
2. **Stand up an out-of-band oracle.** Primary: Burp Collaborator. Fallback: `interactsh` →
   self-hosted DNS/HTTP callback server → `pipedream`/`webhook.site` (least control). Since we
   run Caido (which has no built-in Collaborator equivalent), our default out-of-band oracle is
   `interactsh`. Use a unique subdomain per test case. Baseline what the server fetches normally (User-Agent,
   source IP, headers) so you can attribute later hits.
3. **Establish attacker control per sink.** Determine whether you control scheme, host, port,
   and path, and whether the server follows redirects, honors DNS you control, and accepts
   non-HTTP schemes.
4. **Classify the primitive.** *Full-response* SSRF (fetched body is reflected to you) vs
   *blind* SSRF (only an OOB signal or timing oracle). Then determine internal reachability.
5. **Escalate to the least-invasive impactful target.** Cloud metadata, link-local/internal
   admin, or cross-tenant services — read-only, one or two samples, redacted. Map the chain to
   [`rce-chaining`](../rce-chaining/SKILL.md) (Chain 4: SSRF → metadata →
   credentials) but demonstrate reach and *explain* the escalation rather than weaponizing it.

## Recon signals

- **Fetcher parameters** (the `gf ssrf` family): `url=`, `uri=`, `dest=`, `destination=`,
  `redirect=`, `redirect_uri=`, `target=`, `u=`, `path=`, `continue=`, `next=`, `feed=`,
  `host=`, `port=`, `to=`, `image=`, `imageUrl=`, `callback=`, `webhook=`, `endpoint=`,
  `xml=`, `document=`, `source=`, `proxy=`.
- **Features** that fetch by design: webhooks, import-from-URL, link unfurling, avatar/logo
  by URL, PDF/HTML/screenshot rendering (headless browser), SVG/XML/PDF upload, OIDC/SAML
  `metadata_url`/JWKS, RSS/Atom readers, thumbnailers.
- **Response tells:** outbound-fetch latency differences, error messages leaking internal
  hostnames/IPs/ports, content-length variance between valid and invalid internal targets,
  and DNS lookups landing on your authoritative name server.

## Test recipes

### Out-of-band canary (the baseline oracle)

Point the sink at a unique collector subdomain and watch for an inbound request.

```http
POST /api/preview HTTP/1.1
Host: <TARGET>
Content-Type: application/json

{"url": "https://<UNIQUE>.<YOUR-COLLECTOR>/canary"}
```

Positive: your collector logs a request whose **source IP/User-Agent belongs to the target's
egress**, not your browser. A DNS-only hit still proves server-side name resolution.

### Filter/allowlist bypass classes

When a naive allowlist or IP filter blocks direct internal targets, test, in order of least
noise:

- **Redirect chain:** an allowlisted host you control replies `302` → internal target
  (chains an open redirect into SSRF).
- **DNS rebinding / TOCTOU:** a name you control resolves to an allowed IP at validation time
  and to a link-local IP at fetch time.
- **Address representation:** decimal/octal/hex IP, IPv6 (`[::1]`, `[::ffff:169.254.169.254]`),
  `0.0.0.0`, trailing dot, `user@host` userinfo, uppercase host, added ports.
- **Parser confusion:** discrepancies between the validating URL parser and the fetching
  client (Orange Tsai's canonical class) — verify against the *actual* library in use.

### Cloud metadata reach (read-only, one sample, redact)

Confirm reach to the instance metadata endpoint without harvesting live credentials:

```text
AWS IMDSv1:  GET http://169.254.169.254/latest/meta-data/            (no header)
AWS IMDSv2:  requires PUT .../latest/api/token with
             X-aws-ec2-metadata-token-ttl-seconds  → a plain GET failing here is a CONTROL,
             not a finding (IMDSv2 mitigates simple GET SSRF).
GCP:         GET http://metadata.google.internal/computeMetadata/v1/  header: Metadata-Flavor: Google
Azure IMDS:  GET http://169.254.169.254/metadata/instance?api-version=2021-02-01  header: Metadata:true
```

Positive: the response returns metadata structure that only an in-VPC request could obtain.
**Stop at proof-of-reach.** Do not request the `iam/security-credentials/<role>` leaf to pull
real keys; describe the escalation and cite the chain skill.

### Blind SSRF

With no reflected body, rely on the OOB oracle plus a response-timing differential (internal
IP that exists vs one that does not). Non-HTTP schemes (`gopher://`, `dict://`, `file://`,
`ftp://`) are only relevant if the client honors them — probe support, then explain rather
than execute internal writes.

## Detection signals

- Your collector receives a request that **only the server could have sent** (target egress
  IP/UA), tied to a unique canary you submitted.
- The reflected response contains bytes from an internal-only resource (metadata structure, an
  internal page, an error naming an internal host) unreachable from the tester's network.
- An internal/link-local target behaves measurably differently from a random external control,
  proving internal reach rather than a generic outbound fetch.

Record the sink, the exact attacker-controlled field, the canary, the collector hit
(source IP/UA/timestamp), and a redacted excerpt. Repeat once with a fresh canary to exclude
a stale or shared cache.

After completing these checks, explore adjacent fetcher surface the checklist did not cover —
the skill is a floor, not a ceiling.

## Stop conditions (verified negatives)

See [`skills/references/negative-control-taxonomy.md`](../references/negative-control-taxonomy.md)
for the full 12-category taxonomy. Apply ALL applicable labels to every entry below.

**Decision split (apply separately, never collapse):**
- `technically_vulnerable`: does an attacker-chosen server-side request actually occur?
- `in_scope`: does the program's policy cover this asset and SSRF testing?
- `program_reportable`: does the demonstrated reach meet the program's threshold?
A finding can be yes/yes/no, yes/no/yes, etc. Do not submit on `technically_vulnerable` alone.

- `[expected_product_behavior]` The feature is designed to fetch arbitrary user URLs from an
  isolated egress with no internal reach (e.g. a sandboxed link-preview worker). An external
  fetch alone is intended behavior. `[technical_placeholder]`
- `[technically_not_vulnerable]` The fetch is performed client-side, or the server rejects the
  attacker host before any request leaves. `[technical_placeholder]`
- `[control_exists_elsewhere]` An egress proxy, allowlist, or IMDSv2 blocks escalation; only a
  benign external fetch succeeds. `[technical_placeholder]`
- `[theoretical_without_oracle]` A URL parameter is reflected or accepted, but no OOB hit and
  no internal bytes are observed — no receiver oracle. `[technical_placeholder]`
- `[missing_attacker_control]` The fetched host is server-derived; the attacker cannot change
  scheme, host, or port. `[technical_placeholder]`
- `[real_but_below_program_impact_threshold]` Blind OOB reaches only a fully external endpoint
  with no internal reach and no metadata, and the program does not reward blind SSRF.
  `[technical_placeholder]`
- `[prohibited_test_method]` Showing impact would require volume port-scanning of internal
  ranges or pulling live credentials; stop at proof-of-reach. `[technical_placeholder]`
- `[duplicate_root_cause]` The same fetcher/sink is already tracked. `[technical_placeholder]`

These entries are `[technical_placeholder]` because this hunter is methodology-seeded (see
Evidence basis) rather than mined from the local H1 corpus; the taxonomy is their current
source of authority until curated SSRF negatives back them.

## Anti-patterns

- Do not exfiltrate or use real cloud credentials; prove reach to the metadata endpoint and
  redact. Never perform write/enumeration with a discovered role.
- Do not port-scan internal ranges at volume — a few targeted probes establish reach.
- Do not claim RCE from SSRF without a demonstrated chain; a reachable metadata endpoint is
  reach, not code execution (see the reachability-to-impact leap in
  [`METHODOLOGY.md`](../../METHODOLOGY.md)).
- Do not call a reflected `url=` parameter SSRF without an OOB hit or internal-only bytes.
- Do not publish collector logs, internal hostnames, IPs, or tokens; replace with `<REDACTED>`.

## Minimal reproducer

```python
import os, requests

sink = os.environ["SINK_URL"]        # in-scope endpoint that fetches a URL
collector = os.environ["COLLECTOR"]  # unique OOB subdomain you control
canary = os.urandom(4).hex()

r = requests.post(sink, json={"url": f"https://{canary}.{collector}/probe"}, timeout=20)
print("status", r.status_code)
# SSRF is confirmed OUT OF BAND: check the collector for an inbound request whose
# source IP/User-Agent is the target's egress and whose host contains `canary`.
# A 200 here alone is NOT proof.
```

## Evidence basis and limits

This hunter is **methodology-seeded from public canon**, not mined from the local H1 corpus:
Orange Tsai's SSRF/URL-parser-confusion research, the PortSwigger Web Security Academy SSRF
material, and the AWS/GCP/Azure instance-metadata documentation. The source-to-skill mapping
(Orange Tsai canonical + Collaborator/interactsh + `gf ssrf`) follows
[`knowledge-sources/INTEGRATION-RECOMMENDATIONS.md`](../../knowledge-sources/INTEGRATION-RECOMMENDATIONS.md).
Because no disclosed-report survivorship sample backs it yet, all stop-condition entries are
`[technical_placeholder]`; replace them with curated negatives (real closing comments) as an
SSRF corpus accrues.

## AI-assisted augment (NahamSec seed)

Transferable techniques from Ben Sadeghipour (NahamSec), public PlexTrac "Homework for
Hackers" webinar (`Ue-OIJoM0bA`); see
[`knowledge-sources/creators/03-nahamsec.md`](../../knowledge-sources/creators/03-nahamsec.md).
Guardrail: model output is a hypothesis, not evidence — confirm every candidate against the
out-of-band oracle and the shared
[negative-control taxonomy](../references/negative-control-taxonomy.md); never paste
unsanitized target source, collector logs, or internal detail into an unapproved model
(`nahamsec-ai-sanitize-before-sharing`, CWE-200).

- **Neighbor fetcher/parameter ideas (`nahamsec-ai-neighbor-path-ideas`).** From one observed
  fetch parameter or feature, ask an approved model for likely sibling params and
  URL-accepting endpoints (webhook variants, import routes, render/proxy paths); probe slowly
  against nonexistent controls, then attach the OOB canary to each candidate.
- **Model-assisted source→sink triage (`nahamsec-ai-unfamiliar-code-triage`).** On an
  unfamiliar stack, give an approved model the slice around the HTTP-client call and its
  validation, and ask where scheme/host/redirect handling diverges between the validator and
  the fetcher; hand-trace each candidate and confirm with the collector, not the model's claim.

## Version boundaries

SSRF is usually a design/validation flaw, not a package version — pivot to the target's URL
validation, allowlist, redirect handling, egress policy, and IMDS version. The exception is
**parser-confusion SSRF**, where a specific URL-parsing library version diverges from the
fetching client (Orange Tsai's class); when that is the root cause, identify the exact library
and verify the affected range against OSV.dev/NVD before relying on it. Do not assert a
CVE-backed version boundary from memory.
