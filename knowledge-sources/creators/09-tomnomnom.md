---
source_type: creator
last_updated: 2026-07-22
reliability: high
handles:
  twitter: https://x.com/tomnomnom
  github: https://github.com/tomnomnom
  blog: https://tomhudson.co.uk/
---

# Tom Hudson (tomnomnom)

## Known for
The **recon-tooling** backbone of modern bug bounty. Author of a suite of small, fast, composable
Go tools built on the Unix philosophy (do one thing well, pipe them together). Also a strong
educator on *understanding what tools actually do* rather than copy-pasting.

## Primary content sources
- GitHub `tomnomnom` — the tools themselves (best-documented in their READMEs)
- Conference/workshop talks ("The Art of Subdomain Enumeration", meg/gf demos)
- Live-hacking / methodology streams

## Concrete tips / tricks (verified anecdotes)
- **`waybackurls` / `gau`**: pull every historical URL a domain ever exposed (Wayback, Common
  Crawl) — surfaces dead/hidden params and endpoints that live crawling misses.
- **`gf`**: reusable grep pattern packs (e.g. `gf ssrf`, `gf xss`, `gf redirect`) to triage large
  URL lists for parameters likely vulnerable to a given class.
- **`assetfinder` / `httprobe`**: enumerate related domains, then probe which are live over HTTP/S.
- **`anew`**: append only *new* lines to a file — makes recon pipelines idempotent and diff-able
  across runs (detect newly-appeared assets).
- **`unfurl`**: extract/normalize URL components (domains, paths, params) for bulk analysis.

## Lessons for an AI bug-bounty agent (3–5)
1. Build recon as composable stages with stable text interfaces (one URL/host per line) so any stage
   can be swapped or re-run.
2. Mine *historical* URLs (Wayback/CommonCrawl), not just the live crawl, to recover forgotten
   parameters and endpoints.
3. Use pattern packs (`gf`-style) to pre-filter huge URL sets to per-CWE candidate params before
   spending test budget.
4. Use `anew`-style diffing to detect newly-added attack surface between scans and re-trigger tests.

## Relevance to our CWE skills
Provides the **candidate-input generation** layer for every injection/SSRF/redirect skill: his
`gf` patterns map almost 1:1 onto CWE candidate-parameter selection (e.g. `gf ssrf` → CWE-918).

## Source assessment
- **Value for skill training:** High as *tooling/infrastructure*, medium as narrative content.
- **Skill classes that benefit:** All injection/SSRF/redirect skills (candidate-param triage), recon.
- **Accessibility:** Free / open-source (MIT-style).
- **Next step to integrate:** Register his tools as the agent's recon/param-mining backends; import
  the `gf` pattern packs as the initial per-CWE parameter classifiers.
