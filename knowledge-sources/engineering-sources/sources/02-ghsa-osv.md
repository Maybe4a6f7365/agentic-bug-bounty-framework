---
source_type: advisory-database
last_updated: 2026-07-22
priority: P0
reliability: high
---

# GitHub Advisory Database (GHSA) + OSV.dev

## What it is

Two curated, machine-readable vulnerability databases that join a CVE/GHSA to a specific package,
an **exact introduced/fixed version boundary**, the upstream repository, and (often) the fixing
PR/commit. GHSA is GitHub's reviewed advisory set; OSV.dev is Google's aggregator that normalizes
many ecosystems into the **OSV schema**. Both are the connective tissue that turns a report into an
"affected code at version X, fixed at version Y" ground-truth pair.

## Concrete endpoints / URLs (both live-verified this session)

- **OSV query by package+version or commit** (verified `https://api.osv.dev`):
  ```http
  POST https://api.osv.dev/v1/query
  Content-Type: application/json

  { "package": { "name": "lodash", "ecosystem": "npm" }, "version": "4.17.20" }
  ```
  or by commit: `{ "commit": "<sha>" }`. Choose commit *or* version, not both.
- **OSV batch** (up to 1000 queries/request, returns IDs): `POST https://api.osv.dev/v1/querybatch`.
  Fetch a single record: `GET https://api.osv.dev/v1/vulns/<OSV-ID>`.
  **Rate limit ~100 req/min; 32 MiB response cap on HTTP/1.1 (uncapped on HTTP/2).**
- **OSV schema spec:** `https://ossf.github.io/osv-schema/` — the `affected[].ranges[].events`
  array carries `introduced` / `fixed` boundaries per ecosystem.
- **GHSA REST list** (verified `https://api.github.com/advisories`):
  ```bash
  curl -L "https://api.github.com/advisories?ecosystem=npm&severity=critical&cwes=79"
  ```
  Params include `cwes` (comma list, e.g. `79,284,22`), `ecosystem`, `severity`, `cve_id`.
  Default returns reviewed advisories, excludes malware.
- **GHSA raw corpus:** `https://github.com/github/advisory-database` — all advisories as JSON files
  in **OSV format**, bulk-cloneable (no rate limit). GraphQL `securityAdvisories` also available.

## What it adds beyond HackerOne

- **Exact version boundaries** — kills the "every version before latest = vulnerable" bias.
- **CWE labels** already attached (leaf + class) — cheap classification signal for per-CWE skills.
- **Repository + fix-commit link** — the pivot into MoreFixes-style diffs and regression tests.
- **CVSS + references** — external research writeups, blog posts, PoCs aggregated per advisory.
- **Ecosystem coverage** (npm, PyPI, Maven, RubyGems, Go, NuGet, Packagist, crates, etc.) — much
  broader package/language spread than the H1 corpus.

Traversal chain: `CVE/GHSA → CWE → affected package → introduced/fixed version → repository →
advisory → issue/PR → external research writeup`.

## Filter criteria for our use-case

- Ecosystems: npm/pip/Maven/RubyGems/Go/NuGet/Packagist first (web/API relevance).
- CWE range: our 10 existing per-CWE skills (79, 89, 352, 862/639, 918, 22, 287/347, 502, 611, 918).
- Require a resolvable **fixed** version boundary and, ideally, a linked PR/commit.
- Prefer **reviewed** GHSA (higher label quality) over unreviewed/imported.

## License notes

- **GHSA data: CC-BY-4.0** (github/advisory-database is explicitly CC-BY-4.0). Attribution required;
  redistribution allowed. **OSV.dev** records aggregate upstream sources under CC-BY-4.0 (per-record
  license noted in the entry). Safe for our internal skill corpus with attribution + retrieval date.

## Risks / caveats

- **Label drift:** CWE mappings are sometimes coarse or wrong; treat as `mapping_confidence:
  auto` until a human reviews (see case-bundle schema).
- **Version-range semantics differ per ecosystem** — read the OSV schema carefully; a `fixed` event
  is exclusive/inclusive depending on `type`.
- **Not every advisory has a fix commit** — many only carry a version boundary. Join to MoreFixes.
- Rate limits on the hosted OSV API — for bulk work, clone the advisory-database repo instead.

## Concrete next steps

- **First skill to benefit:** all ten — GHSA/OSV is the **enrichment spine**. Start by back-filling
  every existing skill's example CVEs with `introduced/fixed` boundaries.
- **Wave point:** Wave 1, **first** — seed the index before pulling issue trackers or MoreFixes so
  every downstream diff has a version anchor.

## Honest ledger

- **Verified (WebFetch, live):** OSV `POST /v1/query` shape + `api.osv.dev` host; GHSA
  `GET /advisories` with `cwes`/`ecosystem`/`severity`/`cve_id` params.
- **Verified (web):** OSV batch limit 1000, ~100 req/min, 32 MiB HTTP/1.1 cap; GHSA JSON in OSV
  format; github/advisory-database is the raw repo.
- **Training knowledge (high):** GHSA CC-BY-4.0 license — corroborated by GitHub docs, but confirm
  the current LICENSE in the repo before redistribution.
