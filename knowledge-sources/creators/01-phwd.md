---
source_type: creator
last_updated: 2026-07-22
reliability: high
handles:
  hackerone: https://hackerone.com/phwd
  twitter: https://x.com/phwd_
  github: https://github.com/phwd
  blog: https://philippeharewood.com/
  facebook_notes: "Facebook Bug Bounty page (maintained public list of Meta/Facebook bounties)"
---

# Philippe Harewood (phwd)

## Known for
Deep, sustained work on **Meta / Facebook / Instagram**. Specializes in **access-control and
authorization flaws, OAuth abuse, and business-logic bugs** rather than injection. Known for
finding logic issues where an app *trusts the wrong actor* — page-role manipulation, object
takeover, and permission bypasses. Co-author of *Bug Bounty Hunting Essentials*.

## Primary content sources
- Blog: philippeharewood.com (Facebook-centric access-control writeups)
- Maintains a long-running public list of disclosed Facebook bug bounties
- Talk: "Inside the Mind of a Hacker" and "Web Hacking Pro Tips" interview series (Peter Yaworski)

## Concrete tips / tricks (verified anecdotes)
- Documented bounties include: adding users to page **roles without invitation consent**,
  removing **any user's profile picture** ($2,500), reactivating an Instagram account
  **without entering 2FA** ($500), and downloading **Facebook internal mobile builds** ($6,000).
- Method: enumerate every object/edge in a graph-style API (Meta's GraphQL/edges) and test
  whether the *mutation* enforces the same authorization as the *read*. Writes are frequently
  under-checked compared to reads.
- Chase "hidden" or deprecated endpoints and internal build artifacts — access control on
  legacy/internal surfaces lags behind the main product.

## Lessons for an AI bug-bounty agent (3–5)
1. For every read endpoint that returns an object, generate a paired test that attempts the
   corresponding **write/mutate/delete** as a lower-privileged or unrelated actor.
2. Model the app as objects + roles + edges; flag any state transition that grants a role or
   membership without a consent/ownership check (CWE-862/863/639).
3. Treat "internal", "staging", "beta", and downloadable build artifacts as high-value targets —
   authorization is weaker there.
4. On OAuth/social-login flows, test whether one identity can be swapped for another mid-flow.

## Relevance to our CWE skills
Feeds **CWE-862 (Missing Authorization)**, **CWE-863 (Incorrect Authorization)**,
**CWE-639 (IDOR)**, and OAuth/business-logic skills. His disclosed-bug corpus is a canonical
source of *access-control* negative examples.

## Source assessment
- **Value for skill training:** High — rare, well-documented library of pure authorization/logic
  bugs, the category hardest to synthesize from generic payload lists.
- **Skill classes that benefit:** BOLA/IDOR, broken function-level authorization, OAuth abuse.
- **Accessibility:** Free (public blog + disclosed reports).
- **Next step to integrate:** Extract his disclosed bugs into structured (object, action, missing
  check, impact) tuples and add to the authorization-skill exemplar set.
