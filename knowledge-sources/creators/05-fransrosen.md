---
source_type: creator
last_updated: 2026-07-22
reliability: high
handles:
  hackerone: https://hackerone.com/fransrosen
  twitter: https://x.com/fransrosen
  github: https://github.com/fransr
  blog: https://labs.detectify.com/tag/frans-rosen/
---

# Frans Rosén (fransrosen)

## Known for
Co-founder / Security Advisor at **Detectify**; consistently top-ranked HackerOne hunter
("the OG bug bounty king"). Signature research on **client-side and OAuth attacks**:
`postMessage` exploitation, **"dirty dancing" in OAuth sign-in flows**, cloud/storage takeover,
subdomain takeover, and RCE via misconfigured infra. Deep on the browser trust boundary.

## Primary content sources
- Detectify Labs writeups (labs.detectify.com)
- GitHub `fransr` — including the **postMessage-tracker** Chrome extension
- Critical Thinking podcast appearances (Ep. 45 / rerun Ep. 75)
- Conference talks (e.g. THREAT CON)

## Concrete tips / tricks (verified anecdotes)
- **"Dirty dancing" OAuth**: deliberately trigger *abnormal* states in a sign-in OAuth flow
  (error/redirect edge cases) and combine with third-party JS gadgets or URL leaks so the
  `code`/`token` leaks to an attacker-controlled context — **no XSS required**.
- **postMessage tracking**: instrument `window.postMessage` listeners (his extension logs url,
  origin, and stack) to find handlers that trust `event.origin` weakly or reflect data into the DOM.
- Hunt **subdomain / cloud-bucket takeovers** by resolving dangling DNS to unclaimed providers.
- On any redirect that carries secrets, test whether an open-redirect or referrer leak exfiltrates
  the credential.

## Lessons for an AI bug-bounty agent (3–5)
1. Enumerate all `postMessage` listeners and flag those that don't strictly validate `event.origin`
   or that sink data into `innerHTML`/`eval` (CWE-79 client-side).
2. For OAuth flows, fuzz the *unhappy paths* — malformed `redirect_uri`, error redirects, prompt/
   response_type manipulation — and watch where `code`/`token` ends up.
3. Continuously check for dangling DNS → subdomain/bucket takeover across the recon surface.
4. Track secrets through redirects; an open redirect + referrer/`postMessage` leak is a full ATO.

## Relevance to our CWE skills
Feeds **CWE-79 (DOM/client-side XSS)**, OAuth/**CWE-601 (open redirect)**, account-takeover chains,
and subdomain-takeover / **CWE-200** skills.

## Source assessment
- **Value for skill training:** High — one of the best sources for *client-side and OAuth* logic,
  under-represented in payload-centric datasets.
- **Skill classes that benefit:** DOM XSS, OAuth/ATO, open redirect, takeover.
- **Accessibility:** Free (Detectify Labs, GitHub).
- **Next step to integrate:** Turn "dirty dancing" flow states and the postMessage-listener checks
  into concrete test templates for the OAuth and client-side-XSS skills.
