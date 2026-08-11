---
source_type: creator
last_updated: 2026-07-22
reliability: high
handles:
  twitter: https://x.com/InsiderPhD
  github: https://github.com/InsiderPhD
  blog: https://insiderphd.dev/
  youtube: https://www.youtube.com/c/InsiderPhD
---

# Dr. Katie Paxton-Fear (InsiderPhD)

## Known for
**API hacking education** and beginner-to-intermediate methodology. Lecturer in Cyber Security at
Manchester Metropolitan University; PhD (Cranfield) in NLP/insider-threat. Found real vulns at
Verizon, US DoD and others. Her YouTube channel (InsiderPhD, ~70k+ subs) is a leading structured
on-ramp to bug bounty, with a strong API-security focus. Researches **ML/NLP applied to pentesting
and bug hunting** — directly relevant to building an AI agent.

## Primary content sources
- YouTube (InsiderPhD): "What is Bug Bounty?", API-hacking series, methodology explainers
- Academic profile / talks (API security, ML in security)
- Bugcrowd educational collaborations

## Concrete tips / tricks (verified anecdotes)
- **API-first methodology**: find the API behind the app (mobile proxying, JS analysis, `/api`,
  Swagger/OpenAPI docs), then test each endpoint's authorization and object references
  systematically.
- Hunt **hidden/undocumented API functionality** — endpoints referenced in JS or old docs but not
  in the UI often lack authorization checks.
- Structured beginner framing: pick *one* vuln class, learn its root cause, then apply a repeatable
  checklist — good scaffolding for an agent's per-CWE skill design.
- Her research explicitly explores using **ML/NLP to assist vulnerability discovery**, e.g. reading
  API docs to predict where authZ checks are missing.

## Lessons for an AI bug-bounty agent (3–5)
1. Recover the underlying API contract (OpenAPI/Swagger, JS-defined routes, mobile traffic) and
   treat *each endpoint* as a unit of test, not the rendered UI.
2. Diff documented vs. reachable endpoints; undocumented ones are high-probability authZ gaps.
3. Structure each CWE skill as: root-cause explanation → detection checklist → escalation path —
   mirroring her teaching structure.
4. Use NLP over API docs/JS to predict missing-authorization endpoints before active testing.

## Relevance to our CWE skills
Feeds **API authorization** skills (**CWE-862/863/639**), **CWE-200**, and the *pedagogical
structure* of every per-CWE skill. Her ML/NLP angle informs the agent's own design.

## Source assessment
- **Value for skill training:** High for API methodology and for *skill pedagogy*; approachable and
  well-structured.
- **Skill classes that benefit:** API IDOR/BOLA, broken auth, info exposure; agent skill design.
- **Accessibility:** Free (YouTube, academic pages).
- **Next step to integrate:** Adopt her API-contract-recovery step as a pre-test module; use her
  per-class checklist format as the template for each CWE skill.
