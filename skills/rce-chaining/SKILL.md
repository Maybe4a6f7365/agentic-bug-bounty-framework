---
name: rce-chaining
description: Chain proven primitives — arbitrary file write, file read, SSRF, JS execution in headless browsers, and deserialization — into remote code execution, and decide when a primitive is worth escalating versus banking as a gadget. Load when a hunter proves a primitive but its standalone impact is low, or when assessing how far a foothold escalates. Triggers — RCE chain, escalate this primitive, file write to RCE, SSRF to cloud metadata, headless Chrome DevTools, deserialization gadget.
---

# RCE Chaining Methodology

> **Scope & authorization.** This is a reusable methodology reference, not a
> target-specific finding. Apply it only against assets you are explicitly
> authorized to test under the relevant program's published HackerOne policy and
> the repository's [`SECURITY-RESEARCH-POLICY.md`](../../SECURITY-RESEARCH-POLICY.md).
> Stay in scope, honor each program's rate limits and identification headers, and
> **do not execute destructive or malicious payloads** — for file-write-to-RCE
> and similar chains, demonstrate the primitive and *explain* the escalation path
> rather than actually running attacker code. Redact all evidence (tokens,
> credentials, device IDs, PII) before committing. This guidance is optional and
> non-normative; the repository's contracts and gates always take precedence.

_Transcribed from terminal screenshots._

You are assisting archangel (HackerOne), whose RCE reports include headless Chrome
exploitation chains, Perforce protocol abuse for arbitrary file write, and
vulnerable component exploitation. His RCE findings are typically chains:
SSRF → LFI → RCE, or file write → DLL hijack → RCE.

## Core Philosophy

RCE is the holy grail. In bug bounty, you rarely get direct `eval(user_input)`.
Instead, RCE comes from **chaining primitives**: a file write becomes RCE via DLL
hijack, an SSRF becomes RCE via cloud metadata → instance credentials → deploy
pipeline. Think in chains.

## RCE Chains (from real reports)

### Chain 1: Headless Chrome + Debug Protocol + File Read → K8s Secrets

When you find HTML-to-PDF or screenshot rendering:

1. Confirm JavaScript execution in the renderer
2. Port scan localhost for Chrome DevTools port (30000-50000 range)
3. Access `/json` endpoint on debug port to get WebSocket URL
4. Use Chrome DevTools Protocol over WebSocket to read local files
5. Read `/var/run/secrets/kubernetes.io/serviceaccount/token`
6. Use K8s service account token to access cluster API

### Chain 2: Perforce Client + Arbitrary File Write → DLL Hijack

When target uses Perforce for version control:

1. Set up malicious Perforce server
2. Coerce connection via mDNS poisoning or social engineering
3. Use `client-WriteFile` to write malicious DLL to application directory
4. Application loads DLL on next startup → RCE

Key: Check if `P4CLIENTPATH` is set. If not, the Perforce server can write ANYWHERE.

### Chain 3: Vulnerable Component + Known CVE

Identify component versions and check for known RCE CVEs:

- HeadlessChrome/77.0.3844.0 → multiple RCE CVEs
- pdf.js 1.10.97 → CVE-2018-5158 (XSS that enables further chains)
- Old libcurl → protocol smuggling
- OpenSearch with vulnerable Chrome → RCE via reporting plugin

### Chain 4: SSRF + Cloud Metadata + Deploy Key → Code Push

1. SSRF to `169.254.169.254/latest/meta-data/iam/security-credentials/`
2. Extract AWS credentials
3. List accessible services (S3, CodeCommit, ECR)
4. Push malicious code or container → RCE in deployment

## Discovery Methodology

### Step 1: Identify Code Execution Surfaces

- PDF generators (wkhtmltopdf, headless Chrome, Puppeteer)
- Image processors (ImageMagick, GraphicsMagick)
- Document converters (LibreOffice, Pandoc)
- Template engines (Jinja2, ERB, Handlebars)
- Import/export features using external tools
- Version control integrations (Git, SVN, Perforce)
- CI/CD pipelines accessible via API

### Step 2: Version Fingerprinting

For every component you identify:

- Extract exact version from headers, error messages, or behavior
- Check CVE databases for that version
- Look at the User-Agent of server-side HTTP clients
- Check `navigator.userAgent` in headless browsers via injected JS

### Step 3: Primitive Hunting (gadget inventory)

Look for these primitives that chain to RCE. Each proven primitive is a **gadget** —
a reusable chain component that is not a vulnerability by itself but enables one.
Track gadgets per target in `notes/recon/gadgets.md` so they feed future chains:

- **File write**: upload features, Perforce, import tools
- **File read**: SSRF, LFI, directory traversal
- **JS execution**: XSS in headless browser context, template injection
- **Command injection**: user input in system calls, filename handling
- **Deserialization**: Java/PHP/Python/Ruby object deserialization
- **Open redirect**: chain primitive for OAuth token theft, SSRF filter bypass, phishing
- **Header injection**: CRLF/host-header for cache poisoning, request smuggling

When you prove a primitive works but it has no standalone impact, record it as an
`observation` in the manifest with a note pointing to this skill — do not discard it.
A gadget without a chain today is a chain component tomorrow.

### Step 4: Chain the Primitives

Map your primitives to known escalation paths:

```
File Write → DLL hijack, webshell, cron job, authorized_keys
File Read → secrets, tokens, source code → auth bypass → more access
JS Execution (headless) → Chrome debug protocol → file read → K8s secrets
SSRF → cloud metadata → credentials → lateral movement
Template Injection → code execution in server-side template engine
```

## Impact Demonstration

For RCE, demonstrate:

1. **Command execution proof**: `id`, `whoami`, `hostname` output
2. **Or file read proof**: sensitive file contents (tokens, configs)
3. **Environment context**: are you in a container? What services are accessible?
4. **Blast radius**: one pod? The whole cluster? All customer data?

For file-write-to-RCE chains, you may need to explain the chain rather than
actually execute malicious code. Show the write primitive works, explain the RCE
path.

## Key Considerations

- Always check if you're in a container (Docker/K8s) – K8s secrets are at known paths
- Check for service mesh/sidecar proxies that might give access to other services
- Look for IAM roles/service accounts attached to the compute instance
- Document the full chain clearly – reviewers need to understand each step

## AI-assisted augment (NahamSec seed)

Transferable techniques from Ben Sadeghipour (NahamSec), public PlexTrac "Homework for
Hackers" webinar (`Ue-OIJoM0bA`); see
[`knowledge-sources/creators/03-nahamsec.md`](../../knowledge-sources/creators/03-nahamsec.md).
**Strict guardrail:** model output is a hypothesis, never a proven chain step — a primitive
counts only when demonstrated at runtime, and a chain link counts only when each step is
individually proven (see the assumption-ledger discipline in
[`METHODOLOGY.md`](../../METHODOLOGY.md)). Confirm every candidate against a live oracle and the
shared [negative-control taxonomy](references/negative-control-taxonomy.md). Never send
unsanitized target source, tokens, or infrastructure detail to an unapproved model
(`nahamsec-ai-sanitize-before-sharing`, CWE-200), and never execute destructive payloads —
demonstrate the primitive and explain the escalation.

- **Model-assisted source→sink triage for execution surfaces
  (`nahamsec-ai-unfamiliar-code-triage`).** On an unfamiliar stack, give an approved model
  the smallest slice around a candidate sink (deserializer, template render, file-write,
  document/image converter invocation) plus its call sites and ask for attacker-controlled
  inputs and the reachability conditions; then hand-trace the real call graph. A pattern
  match on a dangerous function is not reachability.
- **Second-look on component fingerprints — but verify CVEs independently
  (`nahamsec-ai-context-second-look`).** Use a model to interpret an unfamiliar version
  banner, renderer `navigator.userAgent`, error string, or server HTTP-client User-Agent and
  to hypothesize a chainable CVE. **Never trust a model-recalled CVE-ID:** confirm the exact
  affected-version range against OSV.dev/NVD before relying on it (models hallucinate CVEs and
  version boundaries).
- **Variant matrix over primitives and chains (`nahamsec-deep-one-weakness-family`).** Hold
  the escalation invariant fixed (e.g. "arbitrary file write → code load") and enumerate how
  each stack reaches it (DLL hijack, webshell, cron, `authorized_keys`, plugin dir); a
  hardened/patched sink must stay negative under the same probe.
