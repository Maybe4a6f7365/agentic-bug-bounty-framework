---
source_type: conference-talks
last_updated: 2026-07-22
reliability: high      # talk titles/speakers/years verified; watch individual recordings for detail
---

# Landmark Web/AppSec Conference Talks — Catalog

Curated, not exhaustive. Each entry: **title — speaker (venue year)** → *lesson for the agent*.
These pair well with the PortSwigger "Top 10 Web Hacking Techniques" annual polls
(see `../blogs/01-top-hacker-blogs.md`).

1. **HTTP Desync Attacks: Request Smuggling Reborn — James Kettle (Black Hat USA / DEF CON 2019)**
   → Front-end vs. back-end disagreement on `Content-Length`/`Transfer-Encoding` re-opened request
   smuggling as a mass-exploitable class. *Agent: probe CL.TE/TE.CL on every proxied host.*

2. **Browser-Powered Desync Attacks — James Kettle (Black Hat USA / DEF CON 2022)**
   → Victim browsers can be turned into desync delivery platforms (client-side smuggling).
   *Agent: consider client-initiated desync, not just server-to-server.*

3. **ProxyLogon is Just the Tip of the Iceberg — Orange Tsai (DEF CON 29, 2021)**
   → A new Exchange attack surface: pre-auth SSRF (CVE-2021-26855) → RCE chain (ProxyLogon/Shell).
   *Agent: score SSRF by reachable internal auth/management endpoints; chain to RCE.*

4. **A New Era of SSRF — Orange Tsai (Black Hat USA 2017)**
   → URL-parser inconsistencies across languages/libraries enable SSRF filter bypass.
   *Agent: fuzz URL parsers with confusing hosts/encodings; test parser-vs-parser discrepancy.*

5. **Confusion Attacks: Hidden Semantic Ambiguity in Apache HTTP Server — Orange Tsai (2024)**
   → #1 PortSwigger Top-10 of 2024; module/path parsing ambiguity crosses handler boundaries.
   *Agent: test path/handler confusion at the proxy↔origin seam.*

6. **How Do I Shot Web (bug bounty recon/methodology) — Jason Haddix (DEF CON 23, 2015)**
   → Systematized recon → attack-surface → testing workflow for bounty. *Agent: adopt phased recon.*

7. **Web Cache Deception / Web Cache Poisoning — (Omer Gil, Black Hat 2017; Kettle 2018–2020)**
   → Caches store attacker-influenced or wrongly-keyed responses served to other users.
   *Agent: probe unkeyed inputs + cacheable path tricks.*

8. **Server-Side Template Injection — James Kettle (Black Hat 2015)**
   → Template syntax reaching a render engine escalates to RCE, engine-specific.
   *Agent: send `{{7*7}}`/`${7*7}` polyglots into rendered fields before assuming plain XSS.*

9. **DEF CON AppSec Village — "Got 99 Problems But Prompt Injection Ain't Watermelon" (Messdaghi &
   Shulz, DC32 2024)** → LLM/prompt-injection as an emerging appsec class.
   *Agent: include LLM-integration attack surface (prompt injection, tool abuse) in scope.*

10. **Web Hackers vs. The Auto Industry — Sam Curry et al. (writeup 2023; talk circuit)**
    → Public identifiers (VIN) used as authZ keys; shared telematics platforms fan out one bug.
    *Agent: flag public-identifier-as-authZ-key; prioritize shared integrators.*

## Source assessment
- **Value for skill training:** High — each talk defines or refines a vuln class with a detection
  method; several ship an accompanying whitepaper and open-source tool.
- **Skill classes that benefit:** Request smuggling, SSRF/RCE chains, cache poisoning, SSTI, recon.
- **Accessibility:** Free — recordings on YouTube/DEF CON media; slides/whitepapers public.
- **Next step to integrate:** For talks that ship a tool (Kettle) or whitepaper (Tsai), lift the
  detection heuristic directly into the matching CWE skill; keep the rest as RAG reference.
