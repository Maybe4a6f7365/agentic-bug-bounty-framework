---
source_type: creator
last_updated: 2026-07-22
reliability: high
handles:
  hackerone: https://hackerone.com/stok
  twitter: https://x.com/stokfredrik
  github: https://github.com/stokfredrik
  blog: https://www.stokfredrik.com/
  youtube: https://www.youtube.com/c/STOKfredrik
---

# Fredrik Alexandersson (STÖK)

## Known for
Bug-bounty **content creation, methodology, and mindset** more than a single vuln class. Awarded
by Uber, Salesforce, Microsoft, US DoD, HackerOne, Dell and others. Widely credited with
popularizing the "hacker lifestyle / vlog" format and coaching hunters on *workflow, focus, and
recon-to-report pipelines*. Frequent collaborator and live-hacking-event competitor.

## Primary content sources
- YouTube (STÖK): methodology walkthroughs, live-hacking recaps, tooling demos
- Conference keynotes on creativity/community in security
- Twitter/X threads distilling single techniques

## Concrete tips / tricks (verified anecdotes)
- Emphasizes **"hack, learn, share"** — turning each finding into a reusable, teachable pattern
  rather than a one-off payoff. For an agent, this maps to: after every bug, generalize the root
  cause into a detection rule.
- Strong advocate of **time-boxed, target-focused recon** over spraying tools blindly: pick a
  program, understand its attack surface deeply, then go wide.
- Promotes reproducible, clearly-written reports (impact-first) as a force multiplier for triage.

## Lessons for an AI bug-bounty agent (3–5)
1. After confirming a finding, auto-generate a generalized signature (root-cause + variant
   parameters) so the same class is caught elsewhere.
2. Prioritize depth on a chosen target's attack surface before breadth across many targets.
3. Optimize report quality (clear repro steps + business impact) — it materially affects triage
   outcome and bounty, and is cheap for an agent to do well.

## Relevance to our CWE skills
Cross-cutting: informs the **methodology/orchestration layer** and the **report-writing** step of
every CWE skill rather than one vuln class.

## Source assessment
- **Value for skill training:** Medium-high — best for *process and reporting* heuristics; less for
  raw payloads.
- **Skill classes that benefit:** Agent orchestration, recon prioritization, report generation.
- **Accessibility:** Free (YouTube, Twitter).
- **Next step to integrate:** Mine his methodology videos for a "recon → triage → report" checklist
  and encode it as the agent's default workflow scaffold.
