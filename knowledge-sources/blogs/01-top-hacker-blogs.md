---
source_type: blogs
last_updated: 2026-07-22
reliability: high
---

# Top Writeup Blogs & Aggregators

Curated high-signal sources of technical writeups. Prioritized by density of *reproducible
technical detail* over volume.

## Primary research blogs (highest signal)
| Source | URL | Focus | Why it matters |
|--------|-----|-------|----------------|
| **PortSwigger Research** | portswigger.net/research | Novel web classes (smuggling, cache, SSTI, race) | Defines classes + ships whitepaper & tool |
| **blog.orange.tw** | blog.orange.tw | Server-side chains (SSRF→RCE, parser confusion) | Best chain-reasoning exemplars |
| **Assetnote Research** | assetnote.io/resources | Enterprise 0day, deep recon, CDN/WAF bypass | Real pre-auth RCEs in enterprise stacks |
| **Detectify Labs** | labs.detectify.com | Client-side, OAuth, cloud/subdomain takeover | Frans Rosén's OAuth/postMessage work |
| **samcurry.net** | samcurry.net | API/authZ at scale, automotive | Modern IDOR/BOLA impact narratives |
| **Google Project Zero** | googleprojectzero.blogspot.com | Deep memory/logic 0day, root-cause analysis | Gold standard for root-cause writeups |
| **Google Bug Hunters / Security blog** | bughunters.google.com | Program-side perspective, disclosed reports | Defender + disclosure view |

## Aggregators & annual roundups
| Source | URL | Focus | Why it matters |
|--------|-----|-------|----------------|
| **PortSwigger "Top 10 Web Hacking Techniques"** | portswigger.net/research/top-10-web-hacking-techniques | Community-voted best research each year | Pre-curated "best of" — highest ROI to mine |
| **InfoSec Writeups (Medium)** | infosecwriteups.com | Community bug-bounty writeups (mixed quality) | Volume of real-world PoCs; needs filtering |
| **HackerOne Hacktivity** | hackerone.com/hacktivity | Disclosed reports across programs | Structured, labeled real bugs (our core dataset) |
| **Intigriti "Bug Bytes" / blog** | blog.intigriti.com | Weekly research roundup + hacker spotlights | Good curation of the week's techniques |
| **Critical Thinking – Bug Bounty Podcast** | criticalthinkingpodcast.io | Weekly technique discussion (Rhynorater, teknogeek) | Distills new research into practical tips |
| **Pentester Land / "The 5 Hacking News"** | pentester.land | Curated writeup lists | Discovery of long-tail writeups |

## Note on the "Top 10 Web Hacking Techniques" (worked example)
The 2024 edition drew **121 nominations**; final #1 was Orange Tsai's *Confusion Attacks* on Apache.
The 2023 edition had 68 nominations with *Smashing the State Machine* (race conditions), *SMTP
Smuggling*, and *PHP filter chains* among finalists. These lists are the single best pre-filtered
feed of new, high-impact technique writeups. (See `../conferences/00-catalog.md` and
`../cve-trends/` for cross-links.)

## Source assessment
- **Value for skill training:** Very high for the primary research blogs (each writeup ≈ one skill's
  worth of detection logic); medium for aggregators (need quality filtering).
- **Skill classes that benefit:** all — depends on the writeup; smuggling/SSRF/cache/OAuth strongest.
- **Accessibility:** All free; some require just a browser. Podcasts free (audio + show notes).
- **Next step to integrate:** Build a scraper for the PortSwigger Top-10 lists (2015–present) as a
  seed corpus; index PortSwigger/Orange/Assetnote writeups into the RAG layer with CWE tags.
