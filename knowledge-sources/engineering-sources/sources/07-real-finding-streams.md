---
source_type: real-finding-stream
last_updated: 2026-07-22
priority: P1
reliability: high
---

# Additional Real-Finding Streams (non-H1 attacker narratives)

## What it is

Vulnerability-disclosure and research streams from ecosystems **under-represented on HackerOne** —
vendor VRPs, AI/ML-specific bounties, and top research labs. They add fresh attacker narratives,
new bug classes (esp. AI/ML supply chain), and writeups with more engineering depth than a typical
H1 triage thread.

## Concrete endpoints / URLs

- **Google Bug Hunters / VRP:** `https://bughunters.google.com/` (Chrome, Android, Cloud, Google
  VRP) — writeups + reward reports.
- **Meta Bug Bounty:** `https://bugbounty.meta.com/` — AuthZ-at-scale, mobile, AI findings; Meta
  disclosure blog.
- **Huntr (Protect AI):** `https://huntr.com/` — the AI/ML supply-chain bounty. Two programs:
  **Model File Vulnerabilities** (`huntr.com/bounties/disclose/models`) and **Open Source
  Vulnerabilities**. 15,000+ members. AI-specific classes: model deserialization,
  **pickle/joblib loading**, model-file **path traversal**, notebook boundary escapes.
- **Research labs / blogs (attacker narrative + PoC):** GitHub Security Lab
  (`securitylab.github.com`), Google **Project Zero** (`googleprojectzero.blogspot.com`, 90-day
  disclosure tracker), **Assetnote** (`assetnote.io/resources`), **PortSwigger Research**
  (`portswigger.net/research`), **Sonar** (`sonarsource.com/blog`), **watchTowr**
  (`labs.watchtowr.com`), **Doyensec** (`blog.doyensec.com`), **Bishop Fox**
  (`bishopfox.com/blog`), **Quarkslab** (`blog.quarkslab.com`).
- **Coordination / advisory feeds:** **CERT/CC Vulnerability Notes** (`kb.cert.org/vuls/`, GitHub
  archive `github.com/CERTCC/Vulnerability-Data-Archive`) — very ingestion-friendly: summary + tech
  details + remediation + affected-vendors, structured. **ZDI** (`zerodayinitiative.com/advisories`),
  **oss-security** mailing list (`seclists.org/oss-sec/`).

## What it adds beyond HackerOne

- **AI/ML bug classes** (Huntr) barely present in the H1 corpus — pickle RCE, unsafe model loaders,
  notebook sandbox escapes, path traversal in model files. Directly relevant to our Anthropic/mcpb
  and AI-target work.
- **VRP depth** — Google/Meta reports often include the maintainer fix and design context.
- **Lab writeups** — full primitive→pivot→impact chains with reproducible detail (Assetnote,
  PortSwigger, watchTowr).
- **CERT/CC** — clean, structured, multi-vendor coordination records = cheap high-signal ingestion.

## Filter criteria for our use-case

- **Huntr** → seed a dedicated **AI/ML-supply-chain (CWE-502 pickle / CWE-22 model path)** skill.
- Lab blogs → invariant + chain templates for existing skills (SSRF, request smuggling, cache).
- Prefer posts that link a **fix commit / advisory** so we can join to GHSA/OSV and MoreFixes.
- CERT/CC → bulk-ingest the GitHub archive for structured records.

## License notes

- Blog content is **copyright each author/firm** — extract methodology/invariants with attribution
  (author, title, URL, date); don't republish prose. **CERT/CC** notes are public-sector, generally
  reusable with attribution. **Huntr** disclosures are public but respect their program terms.

## Risks / caveats

- **Heterogeneous quality/format** — no common schema; normalization cost per source.
- **Marketing framing** in vendor blogs — separate the technique from the promotion.
- **AI/ML class novelty** — fast-moving; skills go stale quickly, re-scrape periodically.
- Respect robots.txt / rate limits; some VRP details are redacted.

## Concrete next steps

- **First skill to benefit:** a **new AI/ML-supply-chain skill from Huntr** (highest novelty, aligns
  with the repo's AI targets), plus enrichment of SSRF/smuggling skills from Assetnote/PortSwigger.
- **Wave point:** Wave 2 (engagement knowledge) for the labs/CERT; Huntr can be pulled early as it's
  structured and program-scoped.

## Honest ledger

- **Verified (web):** Huntr = Protect AI AI/ML bounty with Model-File + Open-Source programs, 15,000+
  members, AI-supply-chain classes; Project Zero / Assetnote / PortSwigger / CERT-CC exist as cited.
- **Training knowledge (high):** exact blog URLs for Sonar/watchTowr/Doyensec/Bishop Fox/Quarkslab
  and the Google/Meta VRP portal paths — stable and well-known, but not re-fetched this session;
  validate each before scripting a crawler.
