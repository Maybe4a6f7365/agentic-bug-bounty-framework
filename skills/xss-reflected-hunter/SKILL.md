---
name: xss-reflected-hunter
description: Hunt reflected XSS by tracing path/query/form input through redirects, Markdown renderers, media proxies, and CSP-sensitive sinks. Load when attacker-controlled input returns in HTML, attributes, navigation targets, or executable client-side templates. Triggers — Cross-site Scripting Reflected, reflected XSS, input reflected into HTML or javascript URL, CSP or sanitizer bypass. Use xss-stored-hunter instead when the input persists and is rendered later.
---

# Reflected-XSS Hunter

Use a controlled account and benign execution marker such as `console.log('XSS_CANARY')`. Do not exfiltrate cookies or victim data.

## Method

1. Send a unique inert canary through every query, path segment, form field, and redirect parameter; record the exact response context: text, quoted/unquoted attribute, script string, URL, Markdown link/image, or DOM assignment.
2. Reproduce in a browser. Raw reflection is not XSS; identify the parser and event that converts it into executable DOM.
3. Test the smallest payload class appropriate to that context, then vary encoding one layer at a time.
4. Map prerequisite actions: login, click/continue, locale, browser, POST-to-GET transition, or CSRF setup.
5. Evaluate CSP only after proving an injection sink. A CSP bypass without injection is defense-in-depth, not reflected XSS.

## Recon signals

- Parameters named `returnTo`, `redirect`, `url`, `greeting`, `query`, `callback`, `next`, and `continue`.
- Path suffixes after test/static pages and login response routes.
- Markdown renderers for chatbot greetings, help/search results, link previews, and images.
- Media/image proxy endpoints that first issue `HEAD`, then `GET`, and render SVG or HTML.
- Responses with `text/html`, template error pages, or client code using `innerHTML`, `srcdoc`, location assignment, or unsafe URL navigation.
- CSP allowlists for script-bearing resources and nonce-bearing DOM nodes.
- Behavior that changes with `Accept: */*`, Safari, locale, authentication, or a button click.

## Test recipes

### Context ladder

Start with `RXSS_<RANDOM>`, then use only the payload matching the observed sink:

```text
HTML text:       <img src=x onerror=console.log('XSS_CANARY')>
attribute break: "><img src=x onerror=console.log('XSS_CANARY')>
URL navigation:  javascript:console.log('XSS_CANARY')
path segment:    </pre><img src=x onerror=console.log('XSS_CANARY')>
```

Encode once for transport, not repeatedly by default. A report reflected a path segment on a test page; another passed `returnTo=javascript:...` into a Continue action after login. Prove the actual click/navigation and origin.

```http
GET /support/confirm?returnTo=javascript:console.log('XSS_CANARY') HTTP/1.1
Host: <TARGET>
Cookie: <CONTROLLED_SESSION>
```

### Markdown URL sink

A reported chatbot flow accepted a POSTed `greeting` and later rendered a Markdown image/link in a generated search page.

```http
POST /en/search?_data=<ROUTE> HTTP/1.1
Content-Type: application/x-www-form-urlencoded

query=probe&greeting=![probe](javascript:console.log('XSS_CANARY'))
```

Follow the product's normal subsequent GET and activate only the controlled link. Positive: the marker runs under the target origin, not an attacker origin or sandboxed preview.

### Validation/use mismatch

Where a proxy validates a remote resource with `HEAD` but fetches with `GET`, serve two harmless content types:

```text
HEAD /probe -> Content-Type: image/png, empty body
GET  /probe -> 302 to /canary.svg
```

Request `/resource?...&url=https://<CONTROLLED_HOST>/probe` and compare `Accept: */*` with browser defaults. A real pattern combined HEAD/GET TOCTOU with browser-specific SVG handling. Positive evidence requires script execution in target origin; a returned SVG download is not enough.

### CSP chain

After proving HTML injection, inventory allowed script URLs and nonce exposure. Test whether an allowlisted Angular-capable script plus an Angular event expression can create a script element carrying an existing nonce. Keep the loaded script a harmless canary. Do not call CSP bypass itself XSS if no injection surface exists.

## Detection signals

- Browser console canary executes and `location.origin` equals the target.
- DevTools Elements shows the intended executable node after browser parsing.
- Network trace proves attacker input traveled through the reflected request and no extension/bookmarklet caused execution.
- The same payload fails in a safely encoded control context.
- For staged flows, a clean session reproduces the POST setup, redirect/GET, and user action.

Capture the final DOM, response headers, CSP, browser/version, and minimal interaction.

After completing these checks, explore adjacent reflection surface the checklist did not
cover — the skill is a floor, not a ceiling.

## Stop conditions (verified negatives)

Each stop condition below carries one of the 12 categories from [`skills/references/negative-control-taxonomy.md`](../references/negative-control-taxonomy.md). Apply ALL applicable labels. Never file a finding that triggers any category below.

**Decision split (apply separately, never collapse):**
- `technically_vulnerable`: does reflected input execute under the target origin?
- `in_scope`: does the program's bounty policy cover this asset?
- `program_reportable`: do the victim path and impact meet its threshold?
Scope is less commonly the deciding issue here, but remains independent. Do not submit raw reflection on `technically_vulnerable` assumptions alone.

- `[expected_product_behavior]` Input is HTML-encoded, returned as `application/json`/`text/plain`, or an open redirect performs only normal URL navigation. `[technical_placeholder]`
- `[control_exists_elsewhere]` CSP blocks the only event/script path and no allowed gadget/nonce chain exists. `[technical_placeholder]`
- `[missing_attacker_control]` The CSP gadget requires markup the attacker cannot inject, or execution requires the victim to paste code into DevTools. `[technical_placeholder]`
- `[theoretical_without_oracle]` A payload appears in source or a `400/500`, but no clean-browser canary executes under `location.origin`. `[technical_placeholder]`
- `[real_but_below_program_impact_threshold]` Execution is self-XSS or requires implausible manual developer-tool interaction, with no cross-user delivery. `[technical_placeholder]`
- `[technically_not_vulnerable]` JavaScript runs only on a `data:`/local/attacker origin, or SVG is downloaded/rendered on an isolated origin. `[technical_placeholder]`
- `[patched_version]` The deployed sanitizer/encoder is at or above the relevant fix and the target sink does not reproduce. `[technical_placeholder]`
- `[out_of_scope_asset]` The only executable reflection occurs on an explicitly excluded test/static host. `[technical_placeholder]`

## Anti-patterns

- Do not start with obfuscated data-exfiltration payloads. Use a visible/console canary.
- Do not spray large payload lists; derive payloads from the reflection context.
- Do not ignore click, authentication, locale, or browser prerequisites.
- Do not report raw reflection, open redirect, or CSP weakness as XSS without target-origin execution.
- Do not test against real victims or send support messages containing active payloads.

## Minimal reproducer

```python
import os, requests
from urllib.parse import quote

base = os.environ["TARGET_BASE"].rstrip("/")
param = os.environ.get("PARAM", "returnTo")
payload = "<img src=x onerror=console.log('XSS_CANARY')>"
r = requests.get(f"{base}/<PATH>?{param}={quote(payload)}", timeout=15)
print(r.status_code, r.headers.get("content-type"))
print("raw reflection", payload in r.text, "encoded", "&lt;img" in r.text)
# Browser verification is mandatory before classifying as XSS.
```

## Evidence basis and limits

Derived from six full reports: H1 `2038943`, `2279346`, `1940245`, `2509022`, `2106708`, and `2503113`. Patterns include path reflection, `returnTo` navigation, Markdown image URLs, POST-seeded greetings, HEAD/GET media validation drift, `Accept`-dependent behavior, and nonce-based CSP chains.

Negatives in this skill are structural from arXiv 2511.18608 / ESEM 2021 (0 disclosed non-accepted Cross-site Scripting (XSS) - Reflected reports in the local corpus) — see `skills/references/negative-control-taxonomy.md` for provenance.

## Web-Verification Augment (2026-07-22)

- Local negatives: 0 (no informative, not-applicable, duplicate, or spam records for this CWE in the JSONL).
- Study-only taxonomy: all eight stop conditions are `[technical_placeholder]`; they specialize the shared taxonomy using this skill's existing browser-origin, CSP, encoding, and victim-interaction controls. No H1 negative or closing rationale is claimed, and no body fetch was attempted.

## AI-assisted augment (NahamSec seed)

Transferable techniques from Ben Sadeghipour (NahamSec), public PlexTrac "Homework for
Hackers" webinar (`Ue-OIJoM0bA`). Guardrail: model output is a hypothesis, not evidence —
confirm every candidate against a live execution oracle and the shared
[negative-control taxonomy](../references/negative-control-taxonomy.md); never paste
unsanitized target source or data into an unapproved model
(`nahamsec-ai-sanitize-before-sharing`, CWE-200).

- **Model-assisted source→sink triage (`nahamsec-ai-unfamiliar-code-triage`).** Ask an
  approved model to trace a path/query/form input through redirects, Markdown renderers, and
  media proxies to the HTML/attribute/JS-URL sink and to name the encoding applied; then
  prove execution against the real sink — reflection alone is not XSS.
- **Second-look on sanitizer/CSP behavior (`nahamsec-ai-context-second-look`).** Use a model
  to hypothesize why a payload was neutralized (encoder, allowlist, CSP directive) and
  suggest a bypass class, then confirm with an actual execution oracle, not the transcript.
- **Neighbor reflection-point ideas (`nahamsec-ai-neighbor-path-ideas`).** From one observed
  reflected parameter, ask for likely sibling params/routes, probing against nonexistent
  controls within rate limits.

## Version boundaries

Each row is a real, machine-readable OSV/GHSA entry bounding the sanitizer / encoder / template surface for this class. Use it as a "what's already been fixed" filter — a target on or above the `fixed` boundary is not a bug candidate without independent reproduction.

| package (ecosystem) | GHSA / CVE | severity | introduced | fixed | summary |
|---|---|---|---|---|---|
| dompurify (npm) | GHSA-gx9m-whjm-85jf / CVE-2024-47875 | high | 0 | 2.5.0 | Nesting-based mutation XSS (mXSS) |
| handlebars (npm) | GHSA-2w6w-674q-4c4q / CVE-2026-33937 | critical | 4.0.0 | 4.7.9 | JS injection via AST type confusion |
| sanitize-html (npm) | GHSA-qhxp-v273-g94h / CVE-2019-25225 | moderate | 0 | 2.0.0-beta | XSS via incomprehensive sanitization |
| jquery (npm) | GHSA-gxr4-xjj5-5px2 / CVE-2020-11022 | moderate | 1.12.0 | 3.5.0 | XSS via DOM manipulation of untrusted markup |
| bleach (PyPI) | GHSA-m6xf-fq7q-8743 / CVE-2020-6816 | moderate | 0 | 3.1.2 | mXSS via whitelisted math/svg + raw tag |

**Usage:** when a target pulls in one of these at version `x`, check `x` against `introduced`/`fixed`. If `x >= fixed`, the sanitizer/encoder already closes that bypass — look at target-level sink context (unescaped interpolation, `dangerouslySetInnerHTML`) instead. SEMVER `fixed` is exclusive (first safe version). Data from OSV.dev (`api.osv.dev/v1/query`) + GitHub Advisory DB, fetched 2026-07-22; full dataset in `knowledge-sources/engineering-sources/version-boundaries.md`.

**Caveat:** the table proves the package's *known* vulnerable range, not that the *target's* sink reaches it — a target may sanitize server-side before the vulnerable client render, or never enable the affected config. Treat it as a **filter**, not a finding.
