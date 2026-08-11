---
source_type: index
last_updated: 2026-07-22
reliability: high
---

# Knowledge Sources / Wissensquellen

**EN:** Curated external, public sources to enrich the bug-bounty AI agent's per-CWE skills —
top creators/influencers, conference talks, OSS tooling, writeup blogs, academic papers, and CVE/CWE
trend data. Complements (does not overlap) the local H1 disclosed-reports dataset in
`~/projects/h1-skills/`.

**DE:** Kuratierte öffentliche Quellen zur Anreicherung der Per-CWE-Skills des Bug-Bounty-Agents —
Top-Creator, Conference-Talks, OSS-Tools, Writeup-Blogs, Papers und CVE/CWE-Trends. Ergänzt den
lokalen H1-Datensatz, überschneidet sich nicht mit ihm.

Everything here is **factual and public** (public handles, blog URLs, disclosed reports only — no
PII). Each file carries YAML frontmatter with `source_type`, `last_updated`, and a `reliability`
rating reflecting how well it could be verified during this session.

---

## Inventory

### `creators/` — Top 10 bug-bounty creators (one file each)
| # | Creator | Specialty | Reliability |
|---|---------|-----------|-------------|
| 01 | **phwd** (Philippe Harewood) | Access control / OAuth / logic on Meta | high |
| 02 | **STÖK** (Fredrik Alexandersson) | Methodology, mindset, content | high |
| 03 | **NahamSec** (Ben Sadeghipour) | Recon at scale, education | high |
| 04 | **Jhaddix** (Jason Haddix) | The Bug Hunter's Methodology (recon) | high |
| 05 | **Frans Rosén** | postMessage / OAuth / client-side / takeover | high |
| 06 | **Orange Tsai** | SSRF→RCE chains, parser/request confusion | high |
| 07 | **albinowax** (James Kettle) | Request smuggling, cache poisoning, SSTI, races | high |
| 08 | **Sam Curry** | API/authZ (IDOR/BOLA) at scale, automotive | high |
| 09 | **tomnomnom** (Tom Hudson) | Recon tooling (Go, Unix-philosophy) | high |
| 10 | **InsiderPhD** (Katie Paxton-Fear) | API hacking, education, ML-in-security | high |

`_TEMPLATE.md` — template for adding more creators.
*Adjacent sources referenced (not full profiles): Shubham Shah / Assetnote (deep recon, enterprise
0day) and the Critical Thinking podcast (Rhynorater & teknogeek).*

### `conferences/`
- `00-catalog.md` — 10 landmark web/appsec talks (title/speaker/year/lesson)
- `2021-defcon-orange-tsai-proxylogon.md` — SSRF→RCE chain deep dive
- `2019-2022-kettle-http-desync.md` — request smuggling deep dive

### `tools/`
- `01-burp-suite-extensions.md` — Burp extensions mapped to bug classes
- `02-recon-and-scanning-oss.md` — OSS recon/scanning pipeline (CWE-mapped)

### `blogs/`
- `01-top-hacker-blogs.md` — primary research blogs + aggregators (incl. PortSwigger Top-10 poll)

### `papers/`
- `01-methodology-and-vuln-discovery.md` — web whitepapers (verified) + academic methodology papers

### `cve-trends/`
- `cwe-top25-2020-2025.md` — verified 2024 CWE Top 25 + web-reweighted prioritization

### Root
- `INTEGRATION-RECOMMENDATIONS.md` — how to wire each source into the skill pipeline (direct vs. RAG
  vs. CWE map), with a suggested build order.

---

## Top-5 sources to integrate NEXT (highest ROI)

1. **PortSwigger "Top 10 Web Hacking Techniques" (2015→present)** — a pre-curated, community-voted
   feed of the best web research each year. Scrape it as a seed corpus; near-zero curation cost,
   maximum signal. *(blogs/, conferences/)*
2. **James Kettle / PortSwigger tooling + whitepapers** — each defines a class *and* ships an
   open-source detector (HTTP Request Smuggler, Param Miner, Turbo Intruder). Wrap the tools; lift
   the heuristics into CWE-444 / cache / race skills. *(creators/07, tools/01)*
3. **Autorize (Burp) + Sam Curry & phwd authZ patterns** — the IDOR/broken-authorization skill.
   Highest bounty ROI, weakest scanner coverage, rising in the CWE Top 25. *(tools/01, creators/01,08)*
4. **Orange Tsai's SSRF→RCE chain corpus** — the reference for chain reasoning; encode as
   "primitive→pivot→impact" templates for the SSRF skill. *(creators/06, conferences/)*
5. **tomnomnom `gf` pattern packs + ProjectDiscovery recon pipeline** — the recon/candidate-param
   layer every other skill depends on; cheap to adopt directly. *(creators/09, tools/02)*

---

## Verification notes (honesty ledger)
- Creator identities, handles, and signature research: **web-verified** this session (high).
- 2024 CWE Top-25 ranked list: **fetched from cwe.mitre.org** (high).
- PortSwigger Top-10 of 2024 ranked list: **fetched from portswigger.net** (high).
- Academic paper venues/years in `papers/`: **from training knowledge, marked medium** — verify
  DOIs before formal citation.
- Multi-year CWE movement narrative: partly from secondary reporting (CISA/CWE blog) — directional.
- No private emails, addresses, or phone numbers are recorded anywhere in this directory.
