---
source_type: tools
last_updated: 2026-07-22
reliability: high
---

# Interception Proxy: Caido (with Burp extension ecosystem as reference)

**Our chosen interception proxy is Caido** — a modern, lightweight interception proxy — and we
run it for day-to-day interception, replay, and traffic capture. We still track **Burp Suite's
(PortSwigger) extension ecosystem** below because those extensions encode the field's reference
*detection algorithms*, and each maps onto a Caido workflow we drive by hand or via plugins.
Rough Caido equivalents: Burp's **Match & Replace** → Caido **Match & Replace**; Burp
**Repeater/Intruder** → Caido **Automate / Replay**; Burp extensions/BApps → Caido
**Workflows & plugins**. Keep the catalog: it still informs methodology even where we execute
the technique in Caido.

These extensions (mostly from the BApp Store / PortSwigger) turn manual testing into repeatable
detection — several are directly wrappable as agent exploitation backends.

| Extension | Author | What it does | Bug class (CWE) |
|-----------|--------|--------------|-----------------|
| **Param Miner** | James Kettle / PortSwigger | Brute-forces hidden/unlinked headers & params; core of cache-poisoning discovery (finds unkeyed inputs) | Web cache poisoning, hidden-param injection (CWE-524, CWE-79) |
| **HTTP Request Smuggler** | James Kettle | Detects & exploits CL.TE/TE.CL/TE.TE desync | Request smuggling (CWE-444) |
| **Turbo Intruder** | James Kettle | High-rate request engine; enables the single-packet race attack | Race conditions / TOCTOU (CWE-362/CWE-1188) |
| **Backslash Powered Scanner** | James Kettle | Finds *unknown* injection classes via behavioral probing | Injection (CWE-74 family) |
| **Autorize** | Barak Tawily | Replays each request as a low-priv/other user; auto-detects broken access control | IDOR / broken authZ (CWE-639/862/863) |
| **Logger++** | Soroush Dalili et al. | Advanced request logging, filtering, grep across all Burp traffic | Recon / triage (cross-cutting) |
| **Collaborator Everywhere** | PortSwigger | Injects OOB payloads to catch blind SSRF/interactions | Blind SSRF/RCE (CWE-918, CWE-77) |
| **JS Miner / retire.js** | community | Extracts endpoints/secrets & flags vulnerable JS libs | Info exposure, known-vuln libs (CWE-200, CWE-1104) |
| **InQL** | Doyensec | GraphQL introspection + query generation | GraphQL authZ/injection (CWE-863) |
| **Active Scan++** | PortSwigger | Extends the active scanner (host-header, SSTI, etc.) | Multiple (CWE-94, CWE-79) |

## Source assessment
- **Value for skill training:** Very high — each extension encodes a *detection algorithm* for a
  specific class; these are the reference implementations to model each CWE skill's detector on.
- **Skill classes that benefit:** cache poisoning, smuggling, race conditions, IDOR, SSRF, GraphQL.
- **Accessibility:** Free extensions; Burp Suite Pro (paid) needed for the scanner/Collaborator,
  Community edition covers proxy + several extensions. Headless automation → Burp Suite Enterprise
  or the Montoya API.
- **Next step to integrate:** Prioritize wrapping **Autorize** (IDOR), **HTTP Request Smuggler**,
  **Param Miner**, and **Collaborator** as agent tools; mirror their heuristics in the CWE skills.
