---
source_type: public-issue-tracker
last_updated: 2026-07-22
priority: P0
reliability: high
---

# Public Security Issue Trackers

## What it is

Vendor-run bug trackers that publish the *full lifecycle* of a security bug once its fix ships:
Chromium/Chrome (issues.chromium.org / crbug.com), Mozilla Bugzilla (bugzilla.mozilla.org), and
GitHub Security Lab advisories. Unlike a HackerOne report — which is the reporter's polished
narrative — these expose the maintainer conversation: the questions asked, the severity haggling,
the failed hypotheses, the patch review, and the regression test that was added.

## Concrete endpoints / URLs

- **Chromium issue tracker** — `https://issues.chromium.org/` (canonical) and the legacy alias
  `https://crbug.com/<id>`. Security bugs start restricted to the security team, and become
  **public automatically 14 weeks after the fix is rolled out** (verified). Search public
  security issues via the tracker query UI, e.g. hotlist / `Type=Bug-Security status:Fixed`.
- **Mozilla Bugzilla** — `https://bugzilla.mozilla.org/`. REST API for bug metadata:
  `GET https://bugzilla.mozilla.org/rest/bug?product=Core&keywords=sec-high&resolution=FIXED`
  (returns JSON). Security-sensitive bugs are hidden while embargoed and **unhidden after the fix
  ships** in a release. Advisories cross-referenced at
  `https://www.mozilla.org/security/advisories/`. *(API path from training knowledge — validate
  the exact `rest/bug` params before scripting.)*
- **GitHub Security Lab** — `https://securitylab.github.com/advisories/` (their own coordinated
  disclosures, each linking CVE + affected repo + fix commit). Research writeups at
  `https://github.blog/tag/github-security-lab/`.

## What it adds beyond HackerOne

- **Maintainer questions** — the exact evidence a triager demanded before accepting the bug
  ("can you reproduce without the debug flag?", "what privilege does the attacker start with?").
  These are the single most valuable field for teaching the agent *what to collect before
  asserting a vulnerability.*
- **Severity debate / re-rating** — sec-high → sec-moderate downgrades with the reasoning.
- **Disputed assumptions & false starts** — hypotheses the maintainer rejected (great negatives).
- **Fix commit + review comments + regression test** — the engineering ground truth.
- **Release reference** — the exact version boundary where the fix landed.

Preserve the full event graph per report:

```yaml
report:
  initial_description:
  reporter_reproducer:
  maintainer_questions:
  reporter_answers:
  severity_changes:
  disputed_assumptions:
  fix_commits:
  review_comments:
  regression_tests:
  release_reference:
```

## Filter criteria for our use-case

- Prefer bugs with a **linked fix commit + added/changed test** (skip pure triage noise).
- Web/browser-surface CWEs first (CWE-79, CWE-352, CWE-918, CWE-668, UAF for parser skills).
- Skip Chromium memory-corruption sandbox internals unless building a native-code skill.
- Require a **released** fix (public, un-embargoed) — never ingest embargoed content.

## License notes

- Chromium content is under the Chromium/BSD + Creative-Commons terms of the project; issue text is
  public but attribute the tracker and issue ID. Mozilla Bugzilla content is public; Mozilla code is
  MPL-2.0. GitHub Security Lab advisories are CC-BY-4.0 (attribution). **Attribute the tracker,
  issue/advisory ID, and retrieval date; do not republish embargoed or restricted-access text.**

## Risks / caveats

- **Embargo hazard:** never scrape restricted bugs; only ingest after the public-visibility date.
- **Browser bias:** Chromium/Mozilla skew heavily to memory-safety and web-platform bugs — poor
  coverage of business-logic / authz, which is where our bounty ROI is. Balance with audit reports.
- **Volume/noise:** large fraction of tracker entries are non-security or stability; filter hard.
- **Rate/robots:** respect robots.txt and rate limits; prefer the REST/hotlist APIs over scraping.

## Concrete next steps

- **First skill to benefit:** the parser/DOM-XSS (CWE-79) and SSRF (CWE-918) skills — Chromium and
  GitHub Security Lab have rich, well-reviewed instances with tests.
- **Wave point:** Wave 1 (engineering ground truth), second after GHSA/OSV seeding so we can join
  tracker issues to advisory/version boundaries.

## Honest ledger

- **Verified (web):** Chromium security bugs become public 14 weeks after fix roll-out; use
  issues.chromium.org / crbug.com (chromium.org security + issue-tracking docs).
- **Verified (web):** Cure53/OSTIF and GitHub Security Lab publish advisories publicly (see file 06).
- **Training knowledge (medium):** exact Mozilla Bugzilla `rest/bug` query parameters and the
  precise "unhidden after ship" timing — directionally correct, validate before scripting.
- **Not accessed:** did not enumerate live issue lists this session; endpoints checked for shape,
  not crawled.
