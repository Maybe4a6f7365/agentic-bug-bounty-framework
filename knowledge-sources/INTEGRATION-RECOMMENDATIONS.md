---
source_type: integration-guide
last_updated: 2026-07-22
reliability: high
---

# Integration Recommendations — Wiring Sources into the Skill Pipeline

How the scouted sources map onto the bug-bounty agent's skill repo (`~/projects/h1-skills/`).
Three buckets: **(1) bake directly into a static skill**, **(2) needs a RAG layer**, **(3) CWE
relevance map**.

---

## 1. Sources that go DIRECTLY into a static skill

These are small, structured, and rule-shaped — encode them as skill instructions/heuristics.

### a) `gf` pattern packs → per-CWE candidate-parameter selectors
`tomnomnom/gf` ships grep patterns (`gf ssrf`, `gf xss`, `gf redirect`, `gf sqli`). Drop them into
each skill as the first-pass filter over recon URLs.
> **Example — SSRF skill:** input = URLs from recon; step 1 = `gf ssrf` (params like
> `url=,dest=,redirect=,uri=,path=,continue=,domain=,callback=`) → these become the fuzz targets.

### b) Burp-extension heuristics → skill detection logic
- **Autorize** logic → IDOR/authZ skill: *replay each request stripped of / with a second identity's
  session; flag responses that still return the object* (CWE-639/862/863).
- **Param Miner** logic → cache-poisoning skill: *inject a canary into `X-Forwarded-Host`/`X-Host`
  etc.; if it reflects into a cacheable response, unkeyed-input poisoning candidate.*
- **HTTP Request Smuggler** probes → CWE-444 skill: *send CL.TE and TE.CL variants, diff timing/
  response.*

### c) Creator "detection rules" → skill heuristics
- **Sam Curry** → rule: *authorization keyed on a public/guessable identifier (VIN, email,
  sequential ID) = IDOR candidate.*
- **Frans Rosén** → rule: *enumerate `postMessage` listeners; flag weak `event.origin` checks or DOM
  sinks* (client-side XSS / OAuth token leak).
- **Orange Tsai** → rule: *SSRF severity = f(reachable internal auth/mgmt endpoints); always attempt
  parser-discrepancy filter bypass.*
- **James Kettle** → rule: *probe template-render fields with `{{7*7}}`/`${7*7}` before concluding
  plain XSS* (SSTI).

### d) 2024 CWE Top-25 (web-reweighted) → skill roadmap ordering
Static priority list the orchestrator consults to allocate test budget (see `cve-trends/`).

**Worked micro-example (drop-in for the IDOR skill's heuristics section):**
```
IDOR/BOLA candidate signals (from Sam Curry, phwd, InsiderPhD):
- endpoint takes an object id that is sequential / UUIDv1 / email / public identifier
- read endpoint exists but the paired write/delete lacks an ownership check
- multi-tenant param (org_id, account_id, role) present in request
Action: replay as second identity (Autorize pattern); success => report.
```

---

## 2. Sources that need a RAG layer (too big / narrative for a static skill)

Index these into a retrieval store, chunked and CWE-tagged; the skill queries them at runtime for
exemplars and edge-cases.

| Source | Why RAG | Ingest plan |
|--------|---------|-------------|
| **PortSwigger Research (full corpus)** | Large, deep, evolving | Scrape writeups + whitepapers; chunk; tag by CWE/technique |
| **PortSwigger "Top 10 Web Hacking Techniques" 2015–present** | Best pre-curated feed | Scrape each year's ranked list + linked writeups |
| **blog.orange.tw / Assetnote / Detectify Labs / samcurry.net** | Long chained writeups | Per-post ingest, tag chain primitives |
| **HackerOne Hacktivity + our 1848-report dataset** | Very large, labeled | Already local (`h1-skills/`) — the primary retrieval corpus |
| **InfoSecWriteups (Medium)** | High volume, mixed quality | Ingest with a quality filter (length, PoC presence, CWE tag) |
| **nuclei templates** | Thousands of detections | Index templates by CWE as a detection-pattern store |
| **Academic papers (fuzzing/taint)** | Dense, architectural | Reference tier; retrieve for methodology, not payloads |

**RAG guidance:** chunk by technique, attach `{cwe, source, url, reliability}` metadata, and let each
per-CWE skill retrieve top-k exemplars scoped to its CWE before generating a test plan.

---

## 3. CWE-relevance map (source → which of the Top-10 skills)

Assuming the first 10 per-CWE skills track the web-reweighted Top-25, here's who feeds what:

| CWE skill | Primary creator/source feeds |
|-----------|------------------------------|
| **CWE-79 XSS** (incl. DOM) | Frans Rosén (postMessage/DOM), James Kettle (variants), dalfox, PortSwigger |
| **CWE-89 SQLi** | sqlmap, PortSwigger labs, "SQLi isn't dead" (Top-10 2024 #2) |
| **CWE-352 CSRF** | PortSwigger research, Autorize-adjacent checks |
| **CWE-22 Path Traversal** | Orange Tsai (parser confusion), ffuf/nuclei |
| **CWE-78/77/94 Cmd/Code Injection & SSTI** | James Kettle (SSTI), Backslash Powered Scanner, Orange Tsai |
| **CWE-862/863/639 Authorization/IDOR** | phwd, Sam Curry, InsiderPhD, Autorize, kiterunner |
| **CWE-918 SSRF** | Orange Tsai (canonical), Collaborator/interactsh, `gf ssrf` |
| **CWE-502 Deserialization** | Assetnote/enterprise 0day writeups, nuclei |
| **CWE-200 Info Exposure** | NahamSec/Jhaddix recon, tomnomnom (waybackurls), JS Miner |
| **CWE-287 Broken Auth / OAuth** | Frans Rosén (OAuth "dirty dancing"), phwd, jwt_tool |
| **CWE-444 Request Smuggling** *(bonus)* | James Kettle (canonical) + HTTP Request Smuggler |

---

## Suggested build order (first sprint)
1. Wire **recon module** (subfinder→httpx→katana→gau→gf) — every skill depends on it.
2. Ship **IDOR/authZ skill** first (Autorize + Sam Curry/phwd rules) — highest bounty ROI, weakest
   automated coverage, rising in CWE Top 25.
3. Ship **SSRF skill** with Orange Tsai chain reasoning + interactsh confirmation.
4. Stand up the **RAG layer** over the local H1 dataset + PortSwigger corpus, CWE-tagged.
5. Adopt the **Klees et al. evaluation discipline** for a per-skill benchmark harness.
