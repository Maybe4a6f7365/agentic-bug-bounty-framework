---
source_type: creator
last_updated: 2026-07-22
reliability: high
handles:
  twitter: https://x.com/samwcyo
  blog: https://samcurry.net/
  hackerone: https://hackerone.com/zlz
---

# Sam Curry (samwcyo / zlz)

## Known for
High-impact **API, authorization, and infrastructure** hacking at scale. Landmark research:
**"Web Hackers vs. The Auto Industry"** (2023) — remote unlock/start/locate across ~20 car brands
via telematics/API flaws; **SiriusXM** connected-vehicle vulns; large-scale bugs at Apple,
Starbucks, Atlassian, Tesla, and US government systems. Master of **IDOR/BOLA and auth bypass on
enterprise and third-party APIs**.

## Primary content sources
- Blog: samcurry.net (long collaborative writeups with the team)
- Twitter/X threads (e.g. Tesla $10k windshield, auto-industry thread)
- Conference talks / interviews (Bugcrowd hacker spotlight)

## Concrete tips / tricks (verified anecdotes)
- **VIN-as-identifier IDOR**: several car APIs used the vehicle VIN (a semi-public identifier
  printed on the windshield) as the authorization key — knowing the VIN let attackers control
  locks/engine. Lesson: any guessable/public identifier used for authZ is an IDOR.
- **Dealer/enrollment portals**: chained weak SSO, guessable enrollment, and provider APIs to
  cross the boundary from "employee portal" to "control any customer's car".
- Target **shared third-party platforms** (telematics providers, identity brokers): one bug affects
  every downstream brand that integrates them.
- Enumerate role/tenant boundaries in multi-tenant APIs — swap IDs, org IDs, and roles.

## Lessons for an AI bug-bounty agent (3–5)
1. Flag any endpoint whose authorization relies on a *public or guessable identifier* (VIN, email,
   sequential ID, UUIDv1) — candidate IDOR/BOLA (CWE-639/862).
2. Enumerate tenant/org/role parameters and replay requests across identities to detect horizontal
   and vertical privilege escalation.
3. Prioritize shared platforms/integrators — a single finding fans out across many programs.
4. Reconstruct the full account-provisioning/SSO flow; the weakest link is usually enrollment, not
   the main login.

## Relevance to our CWE skills
Feeds **CWE-639/862/863 (IDOR & broken authorization)**, **CWE-287 (improper auth)**, and API
business-logic skills. Excellent real-world exemplars of *authorization at API scale*.

## Source assessment
- **Value for skill training:** High — modern API/authZ chains with clear impact narratives.
- **Skill classes that benefit:** IDOR/BOLA, broken auth, multi-tenant privilege escalation.
- **Accessibility:** Free (blog, Twitter threads).
- **Next step to integrate:** Convert his writeups into (identifier-type → authZ-check → escalation)
  patterns for the IDOR/authorization skills; add "public-identifier-as-key" as a detection rule.
