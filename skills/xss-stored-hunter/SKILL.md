---
name: xss-stored-hunter
description: Hunt stored XSS across messages, uploads, names, API-only fields, Markdown/wiki pipelines, exports, and internal viewers. Load when attacker input persists and is later rendered to another user or a higher-privilege operator. Triggers — Cross-site Scripting Stored, stored XSS, blind XSS, persistent user content executes. Use xss-reflected-hunter instead when the input is echoed in the same response.
---

# Stored-XSS Hunter

Use two controlled users and a harmless callback/canary. Stored XSS requires persistence plus execution in a later render context; reflection at submission time is insufficient.

## Recon signals: trace source → storage → sink → viewer

For each user-controlled field, record the write endpoint, stored representation, every renderer, viewer role, origin, CSP, and required interaction. Prioritize fields that cross trust boundaries:

- message attachments and API-only nested fields;
- filenames, declared MIME types, and uploaded HTML/SVG;
- link/campaign/tracker names rendered inside `<script>` or admin modals;
- Markdown, wiki, rich-text, reference expansion, exports, and email notifications;
- payment/IP/callback metadata later served as `text/html`;
- internal analytics, support, log, or Parquet viewers (blind sinks).

## Test recipes

### API/UI coverage mismatch

Capture a normal message, then add nested fields the UI does not expose. A disclosed chat pattern used the first attachment field value, with `<` as its leading character.

```bash
curl 'https://<TARGET>/api/v1/chat.postMessage' \
  -H 'X-Auth-Token: <CONTROLLED_TOKEN>' -H 'X-User-Id: <USER_ID>' \
  --data-urlencode 'channel=<CONTROLLED_CHANNEL>' \
  --data-urlencode "attachments[0][image_url]=/assets/logo" \
  --data-urlencode "attachments[0][fields][0][value]=<img src=x onerror=console.log('SXSS_CANARY')>"
```

Open with controlled viewer B. Positive: canary executes under target origin.

### Script-context name

Store a unique inert marker in names used by templates, then inspect source. If it lands in a script block, test a context-specific breakout:

```text
'"></script><img src=x onerror=console.log('SXSS_CANARY')>
```

Visit the exact downstream page or modal as viewer B. A report pattern required creating a redirect-link name, then opening email templates.

### Upload and content-type chain

Test server trust in filename versus declared content type versus bytes. Use a harmless HTML file and an innocuous filename only on your workspace.

```json
{"contentType":"text/html","fileName":"canary.png","fileSize":<SIZE>,"useCase":"conversation"}
```

Upload through the issued URL, finalize it, and open the file as B. Positive only if it executes with target credentials/origin; an isolated object-storage origin or forced download is not exploitable stored XSS.

### Error-but-stored behavior

After a write returns `400`, read the object back. One report stored an `ipAddress` payload despite an empty `400` response, then served it from an info-by-ID endpoint as `text/html`. Never assume failure status means no persistence.

### Markdown/wiki mutation

Test parser boundaries in stages: raw HTML, entity-decoded quotes, generated reference links, and browser HTML5 mutation. A real wiki pattern combined reference expansion, `&quot;`, generated `href`, and parser differential. Use a compact canary and compare server-sanitized HTML to the final DOM; do not paste large historical exploit strings blindly.

### Blind internal sink

Place a unique callback URL with no data collection in likely exported fields. Record source field, timestamp, and controlled hostname. A callback from an internal viewer proves rendering, but not session theft. Stop at one callback.

## Detection signals

- Payload remains after logout/new session and executes for controlled viewer B.
- `location.origin` is the target and CSP/iframe sandbox does not isolate it.
- A server read endpoint shows the stored value even when the write returned an error.
- Blind callback includes only the canary path and a viewer user-agent/time correlation.
- The final browser DOM contains an executable node absent from sanitized server DOM, proving mutation-XSS.

After completing these checks, explore adjacent stored-injection surface the checklist did not
cover — the skill is a floor, not a ceiling.

## Stop conditions (verified negatives)

Each stop condition below carries one of the 12 categories from [`skills/references/negative-control-taxonomy.md`](../references/negative-control-taxonomy.md). Apply ALL applicable labels. Never file a finding that triggers any category below.

**Decision split (apply separately, never collapse):**
- `technically_vulnerable`: does stored input execute in the target origin?
- `in_scope`: does the program's bounty policy cover this asset?
- `program_reportable`: does the victim path and impact meet its threshold?
A finding can be yes/yes/no, yes/no/yes, etc. Do not submit on `technically_vulnerable` alone.

- `[expected_product_behavior]` HTML is intentionally displayed as text/downloaded documentation, or execution occurs only after opening a local generated file. Empirical: H1 `1321358` and `1977168` (informative — RDoc-generated documentation XSS).
- `[control_exists_elsewhere]` CSP blocks every stored event/script and no allowed execution chain exists. `[technical_placeholder]`
- `[missing_attacker_control]` Only a trusted documentation author/admin can persist the scheme or markup. Empirical: H1 `1977258` (informative — stored `javascript:` scheme in RDoc hyperlinks).
- `[theoretical_without_oracle]` The value is stored but disappears/encodes before a second clean session renders it. `[technical_placeholder]`
- `[real_but_below_program_impact_threshold]` Execution is self-XSS with no credible cross-user viewer or privileged same-origin capability. `[technical_placeholder]`
- `[technically_not_vulnerable]` A callback is a server-side preview fetch, or content is `text/plain`/isolated origin rather than browser script execution. `[technical_placeholder]`
- `[out_of_scope_asset]` Execution occurs only in an excluded documentation host or generated artifact. `[technical_placeholder]`

## Anti-patterns

- Do not exfiltrate cookies, PII, secrets, or perform admin mutations. Use `console.log`/visual canaries.
- Do not send payloads to real users, support queues, or broad internal pipelines.
- Do not claim blind XSS from DNS alone; separate preview bots from browser execution.
- Do not ignore origin, MIME type, sandbox, CSP, and viewer permissions.
- Restore/delete test content after evidence capture.

## Minimal reproducer

```python
import os, requests

base = os.environ["TARGET_BASE"].rstrip("/")
token = os.environ["WRITER_TOKEN"]
payload = "<img src=x onerror=console.log('SXSS_CANARY')>"
r = requests.post(base + "/api/<CONTROLLED_OBJECT>",
    headers={"Authorization": f"Bearer {token}"},
    json={"name": payload}, timeout=15)
print("write", r.status_code, r.text[:200])
print("Verify persistence and execution with a second controlled browser.")
```

## Evidence basis and limits

Derived from seven full reports: H1 `3115705`, `1669764`, `2078490`, `1392262`, `1103298`, `219957`, and `2257080`. Patterns cover uploaded HTML, encoded messages, error-but-stored API fields, script-context names, blind internal viewers, attachment fields, and multi-parser wiki mutation.

Negatives in this skill are partly empirical (3 disclosed non-accepted Cross-site Scripting (XSS) - Stored reports in the local corpus) and partly structural from arXiv 2511.18608 / ESEM 2021 — see `skills/references/negative-control-taxonomy.md` for provenance.

## Web-Verification Augment (2026-07-22)

- Local negatives: 3 total (3 informative): H1 `1321358`, `1977168`, `1977258`; IDs, titles, and substates verified in JSONL.
- Study-only taxonomy: CSP, second-session oracle, self-XSS impact, isolated rendering, and excluded-host cases are `[technical_placeholder]`; no body fetch was required.

## AI-assisted augment (NahamSec seed)

Transferable techniques from Ben Sadeghipour (NahamSec), with the indirect-content point
attributed to Mike Bell, public PlexTrac "Homework for Hackers" webinar (`Ue-OIJoM0bA`).
Guardrail: model output is a hypothesis, not evidence — confirm against a live target
oracle and the shared
[negative-control taxonomy](../references/negative-control-taxonomy.md); never send
unsanitized target data to an unapproved model (`nahamsec-ai-sanitize-before-sharing`,
CWE-200).

- **Extend the viewer model to automated consumers (`nahamsec-ai-indirect-content-boundary`,
  `nahamsec-ai-map-full-trust-chain`).** Stored content is increasingly rendered not only to
  a human operator but to an **LLM summarizer, RAG pipeline, or agent** that can call tools.
  This is the blind-injection surface: plant a benign canary *instruction* in stored content
  and check whether an automated consumer follows it into a privileged action. The oracle is
  a real side effect (a tool call or cross-boundary access) confirmed out-of-band — a model
  merely echoing the canary is `[theoretical_without_oracle]`, not impact. Only where the
  program explicitly authorizes AI testing; stop at reversible, self-scoped actions.
- **Model-assisted source→sink triage (`nahamsec-ai-unfamiliar-code-triage`).** On an
  unfamiliar rendering stack, ask an approved model for the store→render path and the
  encoding/sanitizer applied at output, then confirm execution against a real sink rather
  than trusting the model's claim.

## Version boundaries

Each row is a real, machine-readable OSV/GHSA entry bounding the WYSIWYG / rich-text / sanitizer surface where persisted payloads live. Use it as a "what's already been fixed" filter — a target on or above the `fixed` boundary is not a bug candidate without independent reproduction.

| package (ecosystem) | GHSA / CVE | severity | introduced | fixed | summary |
|---|---|---|---|---|---|
| dompurify (npm) | GHSA-gx9m-whjm-85jf / CVE-2024-47875 | high | 0 | 2.5.0 | Nesting-based mXSS (persisted rich-text) |
| ckeditor4 (npm) | GHSA-4fc4-4p5g-6w89 / CVE-2022-24728 | moderate | 0 | 4.18.0 | Stored XSS in CKEditor4 content |
| prismjs (npm) | GHSA-3949-f494-cm99 / CVE-2022-23647 | high | 1.14.0 | 1.27.0 | XSS via rendered highlighted content |
| quill (npm) | GHSA-4943-9vgg-gr5r / CVE-2021-3163 | moderate | 0 | ≤1.3.7 (last_affected) | Stored XSS in Quill editor |
| froala-editor (npm) | GHSA-97x5-cc53-cv4v / CVE-2020-22864 | moderate | 0 | 4.0.11 | Stored XSS in Froala WYSIWYG |
| bleach (PyPI) | GHSA-vv2x-vrpj-qqpq / CVE-2021-23980 | moderate | 0 | 3.3.0 | Stored XSS via sanitizer bypass |

**Usage:** when a target pulls in one of these at version `x`, check `x` against `introduced`/`fixed`. If `x >= fixed`, the editor/sanitizer already blocks that persisted payload — look at target-level storage→viewer re-render instead. SEMVER `fixed` is exclusive; `≤1.3.7 (last_affected)` means OSV recorded no clean fix version at record time, so treat *all* Quill ≤1.3.7 as affected. Data from OSV.dev (`api.osv.dev/v1/query`) + GitHub Advisory DB, fetched 2026-07-22; full dataset in `knowledge-sources/engineering-sources/version-boundaries.md`.

**Caveat:** the table proves the package's *known* vulnerable range, not that the *target's* viewer reaches it — the target may re-sanitize on read, or render stored content in a non-executing context. Treat it as a **filter**, not a finding.
