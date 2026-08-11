---
source_type: conference-talk
last_updated: 2026-07-22
reliability: high
talk:
  title: "ProxyLogon is Just the Tip of the Iceberg: A New Attack Surface on Microsoft Exchange Server"
  speaker: "Orange Tsai (DEVCORE)"
  venue: "DEF CON 29"
  year: 2021
  slides: "https://media.defcon.org/DEF%20CON%2029/DEF%20CON%2029%20presentations/Orange%20Tsai%20-%20ProxyLogon%20is%20Just%20the%20Tip%20of%20the%20Iceberg%2C%20A%20New%20Attack%20Surface%20on%20Microsoft%20Exchange%20Server.pdf"
---

# Deep-dive: ProxyLogon / ProxyShell (Orange Tsai, DEF CON 29)

## What it is
Orange Tsai found a *new attack surface* on Microsoft Exchange's frontend/backend proxy
architecture, yielding several pre-/post-auth chains. The two headline chains:

- **ProxyLogon**: `CVE-2021-26855` (pre-auth **SSRF** → server-side authentication as Exchange) +
  `CVE-2021-27065` (post-auth **arbitrary file write** → RCE). Full pre-auth RCE.
- **ProxyShell**: an Exchange path-confusion → privilege → RCE chain demonstrated at Pwn2Own 2021.

## Why it matters for an agent
1. **SSRF is a pivot, not a destination.** The SSRF was only critical because it reached an
   internal endpoint that would authenticate the request as the server. The agent should always
   ask: *what internal service does this SSRF reach, and what does that service trust?*
2. **Architecture bugs live in the frontend/backend seam.** Exchange's proxy trusted the frontend
   to have authenticated; abusing the proxy let requests slip through as trusted. Generalize:
   any two-tier (proxy → app) system may misplace the trust boundary.
3. **Chain primitives.** SSRF + file-write, each "medium" alone, composed into a critical.

## Maps to
CWE-918 (SSRF), CWE-287 (improper authentication / auth bypass), CWE-22/CWE-434 (file write),
CWE-94 (resulting code execution).

## Source assessment
- **Value:** Canonical exemplar for SSRF-to-RCE chain reasoning; slides + whitepaper are free.
- **Accessibility:** Free (DEF CON media PDF, blog.orange.tw multi-part series).
- **Next step:** Encode as a "primitive → pivot → impact" template in the SSRF skill; add the
  "trust boundary misplacement in proxy architectures" heuristic to the auth-bypass skill.
