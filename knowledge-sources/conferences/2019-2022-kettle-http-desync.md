---
source_type: conference-talk
last_updated: 2026-07-22
reliability: high
talks:
  - title: "HTTP Desync Attacks: Request Smuggling Reborn"
    venue: "Black Hat USA / DEF CON"
    year: 2019
  - title: "Browser-Powered Desync Attacks: A New Frontier in HTTP Request Smuggling"
    venue: "Black Hat USA / DEF CON"
    year: 2022
  speaker: "James Kettle (PortSwigger)"
---

# Deep-dive: HTTP Desync / Request Smuggling (James Kettle)

## Core mechanism
When a front-end proxy/CDN and a back-end server disagree on where one HTTP request ends, an
attacker can **prepend** bytes onto the *next* connection's request. Classic variants:

- **CL.TE** — front-end uses `Content-Length`, back-end uses `Transfer-Encoding: chunked`.
- **TE.CL** — the reverse.
- **TE.TE** — both support TE, but one can be tricked into ignoring it via header obfuscation.
- **TE.0 / CL.0** and **browser-powered desync** — later variants (2022–2024) extending the class,
  including turning victim browsers into desync clients.

## Impact
Request hijacking, credential/session theft, cache poisoning, bypassing front-end security controls,
and "desync worms".

## Why it matters for an agent
1. Smuggling is a **behavioral-discrepancy** bug — detect it by sending ambiguous requests and
   diffing front-end vs. back-end interpretation, not by matching a payload signature.
2. It only exists where there's a **proxy/CDN in front of an origin** — so gate the test on
   detecting that topology during recon.
3. Kettle ships tooling: **HTTP Request Smuggler** (Burp) and **Turbo Intruder** for high-rate/
   single-packet delivery — reusable as the agent's exploitation backend.

## Maps to
CWE-444 (Inconsistent Interpretation of HTTP Requests / request smuggling), plus downstream
CWE-524/CWE-639 (cache poisoning, request hijacking) impacts.

## Source assessment
- **Value:** Defines a whole modern class with detection method + open-source tool.
- **Accessibility:** Free (PortSwigger Research writeups, whitepapers, Burp extensions).
- **Next step:** Wrap HTTP Request Smuggler + Turbo Intruder as agent tools; encode the CL/TE
  disagreement probes as the CWE-444 skill's detection routine.
