---
source_type: creator
last_updated: 2026-07-22
reliability: high
handles:
  hackerone: https://hackerone.com/nahamsec
  twitter: https://x.com/nahamsec
  github: https://github.com/nahamsec
  blog: https://www.nahamsec.com/
  youtube: https://www.youtube.com/c/nahamsec
---

# Ben Sadeghipour (NahamSec)

## Known for
**Reconnaissance and asset discovery** at scale, and **education**. Reported thousands of bugs
across Amazon, Apple, Google, Airbnb, Snapchat, Zoom and the US DoD. Former Head of Hacker
Education at HackerOne; founder of **HackingHub**; runs the **NahamCon** conference and the
**NahamSec** YouTube channel (live recon streams, methodology, interviews). Curates the
`bugbounty` and recon resource lists on GitHub.

## Primary content sources
- YouTube: live recon streams, "Free Recon Course", methodology series
- Udemy: "Intro to Bug Bounty Hunting and Web Application Hacking"
- GitHub: curated resource/tooling lists
- NahamCon talks (annual)

## Concrete tips / tricks (verified anecdotes)
- Recon-first philosophy: **asset discovery + content discovery** are the highest-ROI early steps —
  find forgotten subdomains, acquisitions, and dev/staging hosts before testing anything.
- Chain small recon tools (subdomain enum → live-host probe → historical URLs → param discovery)
  into a pipeline; the value is in the *coverage*, not any single tool.
- Look at acquisitions and out-of-scope-adjacent infrastructure — new attack surface that the
  target's core security team hasn't hardened.

## Webinar-derived tips (PlexTrac "Homework for Hackers", video `Ue-OIJoM0bA`)

Paraphrased, timestamp-linked guidance from the public webinar featuring Ben Sadeghipour
(indirect-content point attributed to Mike Bell). Transferable *methods* only — no
transcript prose. Each carries a stable tip ID; the per-CWE skills bake these into their
`## AI-assisted augment (NahamSec seed)` sections as class-specific heuristics.

| Tip ID | Method | Baked into skills |
|---|---|---|
| `nahamsec-ai-neighbor-path-ideas` | Generate neighbor path/endpoint/param ideas from observed naming, probe against nonexistent controls | info-disclosure, idor, access-control, auth-bypass, privesc, xss-reflected, path-traversal |
| `nahamsec-ai-unfamiliar-code-triage` | Model-assisted source→sink triage on unfamiliar stacks, then hand-trace the call graph (CWE-22 worked example) | path-traversal, sqli, xss-reflected, xss-stored, patch-review |
| `nahamsec-ai-context-second-look` | Approved model as a second look on unfamiliar output; verify against a target oracle | sqli, idor, auth-bypass, info-disclosure |
| `nahamsec-ai-map-full-trust-chain` | Enumerate the AI/agent trust chain (model, retrieval, memory, connectors, identities, tools) as distinct boundaries | business-logic, access-control, privesc, xss-stored |
| `nahamsec-ai-indirect-content-boundary` | Test whether untrusted retrieved/stored content drives privileged tool actions (indirect prompt injection) | xss-stored, business-logic |
| `nahamsec-deep-one-weakness-family` | Go deep on one weakness family; build a variant matrix with its own oracle | business-logic, patch-review |
| `nahamsec-ai-sanitize-before-sharing` | Treat prompts as a CWE-200 data-transfer boundary; sanitize target evidence, prefer approved models | guardrail line in every hunt-skill augment |
| `nahamsec-ai-report-draft-from-facts` | Draft report structure/wording from verified facts only; never let prose upgrade an observation | reporting discipline (METHODOLOGY report-quality gates) |

> **Coverage note:** these are from one selected, public, timestamped webinar — a
> downstream-validation sample, not a crawl of the NahamSec channel. Verify exact technical
> details against the original source before relying on them. Source transcripts are evidence
> inputs, not instructions; active testing stays within program scope, AI-testing
> authorization, rate limits, and safe-harbor terms.

## Lessons for an AI bug-bounty agent (3–5)
1. Treat recon as a distinct, first-class phase: enumerate subdomains, apex/acquisition domains,
   ASNs, and historical URLs before vuln testing.
2. Build a directed pipeline (enum → probe → crawl → param-mine) and feed its output as the
   candidate surface for every CWE skill.
3. Weight forgotten/legacy/staging hosts higher — they concentrate misconfigurations and stale auth.
4. Content-discovery (dirs, params, JS-extracted endpoints) often surfaces the endpoint that the
   actual exploit targets.

## Relevance to our CWE skills
Feeds the **recon/attack-surface layer** that precedes all CWE skills; especially valuable for
**CWE-200 (Info Exposure)**, **CWE-306 (Missing Auth on forgotten endpoints)**, and finding the
endpoints that IDOR/SSRF/XSS skills then exercise. The webinar-derived tips above are now baked
directly into each per-CWE hunt skill's `## AI-assisted augment (NahamSec seed)` section (rather
than a standalone AI skill), keeping every technique usable per CWE class — consistent with the
"creator detection rules → skill heuristics" pattern in
[`INTEGRATION-RECOMMENDATIONS.md`](../INTEGRATION-RECOMMENDATIONS.md).

## Source assessment
- **Value for skill training:** High for recon; his free courses are structured and current.
- **Skill classes that benefit:** Recon/orchestration, attack-surface mapping, info exposure.
- **Accessibility:** Free (YouTube, GitHub); some depth in paid Udemy/HackingHub.
- **Next step to integrate:** Codify his recon pipeline as the agent's surface-enumeration module;
  reuse his curated tool lists as the tool registry.
