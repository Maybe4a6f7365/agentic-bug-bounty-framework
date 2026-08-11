---
source_type: creator
last_updated: 2026-07-22
reliability: high
handles:
  twitter: https://x.com/orange_8361
  github: https://github.com/orangetw
  blog: https://blog.orange.tw/
  employer: DEVCORE (Principal Security Researcher)
---

# Orange Tsai (orange_8361)

## Known for
Principal Security Researcher at **DEVCORE**; arguably the most influential researcher on
**server-side pre-auth vulnerability chains**. Signature work: **ProxyLogon / ProxyShell**
(Microsoft Exchange RCE chains), **"A New Era of SSRF"** (won PortSwigger Top-10 #1), URL-parser
confusion, and **"Confusion Attacks" on Apache HTTP Server** (won PortSwigger Top-10 of 2024 #1).
Master of chaining an SSRF/parser bug into full RCE.

## Primary content sources
- Blog: blog.orange.tw (long, reproducible technical writeups)
- Black Hat / DEF CON talks (multiple years); DEF CON 29 "ProxyLogon is Just the Tip of the Iceberg"
- Whitepapers accompanying each talk (PDFs on media.defcon.org)

## Concrete tips / tricks (verified anecdotes)
- **ProxyLogon** = CVE-2021-26855 (pre-auth **SSRF** → auth bypass) chained with CVE-2021-27065
  (post-auth arbitrary file write → RCE). Lesson: SSRF that can reach an internal management/auth
  endpoint is often a stepping stone, not the finish.
- **URL/parser confusion**: different components (proxy vs. backend, WAF vs. app) parse the same
  URL/hostname differently — exploit the *discrepancy* to smuggle requests past front-end checks.
- **Apache "Confusion Attacks"**: hidden semantic ambiguity in how modules interpret paths/config
  lets you cross handler boundaries (e.g. reach admin/PHP-source/SSRF via crafted paths).
- Study the *architecture* (front-end proxy, module pipeline, internal services) — the bug lives in
  the seam between components.

## Lessons for an AI bug-bounty agent (3–5)
1. When an SSRF is found, immediately enumerate reachable internal services and pivot toward
   auth/management endpoints — score SSRF by *what it can reach*, not just its existence.
2. Test parser discrepancies: send the same URL/host/path with encodings, dot-segments, and
   ambiguous separators to front-end vs. backend and diff the behavior.
3. Model multi-tier architectures explicitly; generate tests that target the boundary between
   proxy/WAF and origin (smuggling, path confusion).
4. Chain primitives — a "medium" SSRF or file-write is a component of a critical RCE chain.

## Relevance to our CWE skills
Feeds **CWE-918 (SSRF)**, **CWE-94/78 (code/command injection & RCE chaining)**, path/parser
confusion, and request-smuggling (**CWE-444**) skills. Best-in-class exemplars for *chaining*.

## Source assessment
- **Value for skill training:** Very high — the gold standard for server-side chain reasoning.
- **Skill classes that benefit:** SSRF, RCE chains, request smuggling, path traversal/confusion.
- **Accessibility:** Free (blog + DEF CON media PDFs).
- **Next step to integrate:** Encode his chains as multi-step "primitive → pivot → impact" graphs;
  use the parser-discrepancy tests directly in the SSRF and smuggling skills.
