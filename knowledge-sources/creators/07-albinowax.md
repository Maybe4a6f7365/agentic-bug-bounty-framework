---
source_type: creator
last_updated: 2026-07-22
reliability: high
handles:
  twitter: https://x.com/albinowax
  blog: https://portswigger.net/research/james-kettle
  personal: https://jameskettle.com/
  employer: PortSwigger (Director of Research)
---

# James Kettle (albinowax)

## Known for
Director of Research at **PortSwigger** (Burp Suite). The most prolific source of *new web attack
classes* of the last decade: **HTTP Desync / Request Smuggling** (popularized it), the
**Single-Packet Attack** (race conditions), **Web Cache Poisoning / Entanglement**,
**Server-Side Template Injection (SSTI)**, **Browser-Powered Desync**, and password-reset
poisoning. Publishes novel Black Hat research for ~10 consecutive years.

## Primary content sources
- PortSwigger Research (portswigger.net/research) — writeups + accompanying whitepapers
- Black Hat / DEF CON talks (e.g. "Browser-Powered Desync Attacks")
- Open-source Burp tooling he authored: **Param Miner**, **Turbo Intruder**, **HTTP Request
  Smuggler**, **Backslash Powered Scanner**
- Methodology paper: "Hunting Evasive Vulnerabilities" / "So you want to be a web security researcher"

## Concrete tips / tricks (verified anecdotes)
- **HTTP Request Smuggling**: exploit `Content-Length` vs. `Transfer-Encoding` disagreement between
  front-end and back-end (CL.TE / TE.CL / TE.TE) to prepend a request onto the next user's — leads
  to cache poisoning, credential theft, request hijacking.
- **Single-Packet Attack**: eliminate network jitter in race conditions by sending ~20–30 requests
  in a *single* TCP packet (HTTP/2), exposing limit-overrun/TOCTOU bugs that timing-based tests miss.
- **Web cache poisoning / "fat GET"**: find unkeyed inputs (headers like `X-Forwarded-Host`, or a
  body on a GET) that influence the response but aren't part of the cache key; poison the cached
  response for all users.
- **SSTI**: inject template syntax (`{{7*7}}`, `${7*7}`) into template-rendered inputs; a reflected
  `49` reveals the engine → escalate to RCE per-engine.
- General method: hunt *unknown* classes by looking for behavioral discrepancies and building
  detection into scanners (his tools automate exactly this).

## Lessons for an AI bug-bounty agent (3–5)
1. For every host behind a proxy/CDN, run smuggling probes (CL.TE/TE.CL) and diff front-end vs.
   back-end handling.
2. Detect unkeyed inputs by injecting canaries into headers/params and checking whether they land in
   a *cacheable* response — the core of cache-poisoning discovery.
3. For race-sensitive actions (coupons, balance, invites), use single-packet concurrency, not loops.
4. Probe template-rendered fields with polyglot template payloads before assuming plain XSS.
5. Prefer *behavioral discrepancy* detection over signature matching — it finds novel variants.

## Relevance to our CWE skills
Feeds **CWE-444 (request smuggling)**, **CWE-1188/362 (race conditions)**, web-cache-poisoning,
**CWE-94 (SSTI→code injection)**, and **CWE-79** variants. His Burp tools are directly reusable as
the agent's exploitation backends.

## Source assessment
- **Value for skill training:** Very high — the canonical source for modern server-side web classes,
  each with a whitepaper *and* an automated tool.
- **Skill classes that benefit:** Request smuggling, cache poisoning, race conditions, SSTI.
- **Accessibility:** Free (research + open-source tools).
- **Next step to integrate:** Wrap Param Miner / HTTP Request Smuggler / Turbo Intruder as agent
  tools; lift each whitepaper's detection heuristic into the matching CWE skill.
