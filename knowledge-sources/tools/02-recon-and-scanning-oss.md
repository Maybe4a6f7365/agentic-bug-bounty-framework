---
source_type: tools
last_updated: 2026-07-22
reliability: high
---

# OSS Recon & Scanning Tools (what they find)

Open-source pentest tooling grouped by pipeline stage. URLs are canonical GitHub orgs. Most are
free/MIT-style and CLI-scriptable — ideal agent backends.

## Asset & subdomain discovery
| Tool | Repo | Function | Feeds CWE |
|------|------|----------|-----------|
| **subfinder** | github.com/projectdiscovery/subfinder | Passive subdomain enumeration (many sources) | attack surface |
| **amass** | github.com/owasp-amass/amass | DNS enum + graph mapping, ASN/CIDR | attack surface |
| **assetfinder** | github.com/tomnomnom/assetfinder | Related domain/subdomain discovery | attack surface |
| **httpx** | github.com/projectdiscovery/httpx | Fast live-host probing, tech/title/status | surface triage |
| **katana** | github.com/projectdiscovery/katana | Modern crawler (JS-aware) | endpoint discovery |
| **gau / waybackurls** | github.com/lc/gau · github.com/tomnomnom/waybackurls | Historical URLs (Wayback/CommonCrawl) | hidden params/endpoints |

## Content / parameter discovery
| Tool | Repo | Function | Feeds CWE |
|------|------|----------|-----------|
| **ffuf** | github.com/ffuf/ffuf | Fast fuzzing: dirs, vhosts, params | hidden endpoints (CWE-200/306) |
| **feroxbuster** | github.com/epi052/feroxbuster | Recursive content discovery | hidden endpoints |
| **Arjun** | github.com/s0md3v/Arjun | HTTP parameter discovery | hidden-param injection |
| **gf** | github.com/tomnomnom/gf | grep pattern packs to triage URLs per class | per-CWE candidate params |

## Vulnerability detection / exploitation
| Tool | Repo | Function | Feeds CWE |
|------|------|----------|-----------|
| **nuclei** | github.com/projectdiscovery/nuclei | Template-based scanner (CVEs, misconfig, exposures) | broad (CWE-200, nday CVEs) |
| **dalfox** | github.com/hahwul/dalfox | XSS scanning/parameter analysis | CWE-79 |
| **sqlmap** | github.com/sqlmapproject/sqlmap | Automated SQL injection detection/exploitation | CWE-89 |
| **kiterunner** | github.com/assetnote/kiterunner | API/route brute-forcing (from Assetnote) | API surface, CWE-862 |
| **jwt_tool** | github.com/ticarpi/jwt_tool | JWT tampering (alg=none, key confusion) | CWE-287/CWE-347 |
| **interactsh** | github.com/projectdiscovery/interactsh | OOB interaction server for blind bugs | blind SSRF/RCE (CWE-918) |

## Source assessment
- **Value for skill training:** High as *executable capability*; `nuclei` templates in particular are
  a large, structured, community-maintained detection corpus worth mining for skill rules.
- **Skill classes that benefit:** recon (all), XSS, SQLi, SSRF, API authZ, JWT/auth.
- **Accessibility:** Free / open-source.
- **Next step to integrate:** Register subfinder→httpx→katana→gau as the recon module; adopt
  `nuclei` as the nday/misconfig detector and mine its templates for per-CWE signatures; use
  `interactsh` for all blind-bug confirmation.
