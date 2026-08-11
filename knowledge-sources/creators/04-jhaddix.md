---
source_type: creator
last_updated: 2026-07-22
reliability: high
handles:
  twitter: https://x.com/Jhaddix
  github: https://github.com/jhaddix
  blog: https://www.arcanum-sec.com/ (Arcanum Security)
  resource: https://github.com/jhaddix/tbhm
---

# Jason Haddix (Jhaddix)

## Known for
**The Bug Hunter's Methodology (TBHM)** — the most widely-referenced recon/attack-surface
methodology in bug bounty. Former Head of Trust/Security leadership roles; longtime Bugcrowd figure
("How Do I Shot Web" DEF CON 23). Runs Arcanum Security training. Focus: **recon, target analysis,
and a repeatable end-to-end hunting workflow**.

## Primary content sources
- GitHub: `jhaddix/tbhm` (methodology + tooling references)
- Conference talks: "How Do I Shot Web" (DEF CON 23), TBHM v1–v4 (Hacktivitycon/DEF CON)
- Arcanum "The Bug Hunter's Methodology [Core]" course (paid)
- Slides on SlideShare / YouTube recordings

## Concrete tips / tricks (verified anecdotes)
- Systematic **asset discovery**: seed → subdomain enum (multiple sources, not one tool) →
  permutation/bruteforce → resolve → screenshot → triage by interesting tech.
- **"Content discovery"** with curated wordlists (he popularized combined lists) beats generic
  scanning; tailor wordlists to the observed tech stack.
- Map the target's **acquisitions and ASN/CIDR ranges** to expand scope legitimately.
- Fingerprint tech, then pull known CVEs/nday for that stack — combine recon output with a
  vuln-intel lookup.

## Lessons for an AI bug-bounty agent (3–5)
1. Never rely on a single enumeration source; union multiple subdomain sources then dedupe.
2. Drive content-discovery wordlists from detected technology, not a fixed list.
3. Screenshot + fingerprint every live host to triage which surfaces deserve deep testing.
4. After fingerprinting, query a CVE/nday index for the exact stack version (ties to cve-trends).

## Relevance to our CWE skills
Foundational for the **recon layer**; his tech-fingerprint → CVE lookup step directly feeds the
**cve-trends** mapping and version-specific skills (e.g. deserialization/RCE in known stacks).

## Source assessment
- **Value for skill training:** High for methodology structure; the canonical recon reference.
- **Skill classes that benefit:** Recon, attack-surface mapping, nday/CVE correlation.
- **Accessibility:** Free (TBHM repo, talks) + paid deep course.
- **Next step to integrate:** Adopt TBHM's phase model as the agent's recon state machine; wire the
  fingerprint→CVE step to our cve-trends library.
