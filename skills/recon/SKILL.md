---
name: recon
description: Map a target's external attack surface — JS-bundle mining first, then subdomain/asset enum, live-host probe, JS-aware crawl, historical URLs, parameter mining, and gf class-triage — then route the candidate surface to the right CWE hunter. Load at the start of a target engagement, before exploitation. Triggers — recon, attack-surface mapping, enumerate the target, map endpoints or subdomains, mine JS bundles, build the candidate surface.
---

# Recon / Attack-Surface Mapping

Recon runs before exploitation and stays strictly in scope. **Public reachability is not
permission** — a discovered subdomain, host, or endpoint is not authorized until it matches
the program policy and the target `contract.yaml` (see
[`SECURITY-RESEARCH-POLICY.md`](../../SECURITY-RESEARCH-POLICY.md)). Throttle to ≤1–2 aggregate
requests/second with ≥1s between API calls, no concurrency; send every required
researcher-identification header; keep automation bounded with a working kill switch; stop on
throttling, instability, or non-researcher data. No DoS/stress/resource-exhaustion, and no
pivot into third-party or cloud infrastructure that is not explicitly in scope. Recon produces
a **candidate surface, not findings** — volume is an activity metric, never a success metric.

## Recon pipeline

A directed pipeline; the value is coverage, not any single tool. Tools are named from the
registry [`knowledge-sources/tools/02-recon-and-scanning-oss.md`](../../knowledge-sources/tools/02-recon-and-scanning-oss.md);
any equivalent enum → probe → crawl → historical → param-mine chain is a valid fallback.

1. **Scope gate first.** Read the program policy and `contract.yaml`; build the in-scope
   allowlist. Set the rate budget, identification headers, and kill switch before any request.
2. **Mine the JS bundles first** (per [`CLAUDE.md`](../../CLAUDE.md)). Pull source maps,
   `webpack`/chunk files, and inline API clients; extract hidden/undocumented endpoints,
   routes, feature flags, parameters, and secret-shaped strings (retire.js / JS Miner). Build
   the surface picture before chasing the first interesting thing.
   *Fallback:* if source maps are stripped, deobfuscate `chunk-*.js` with `prettier` + manual
   regex for route strings and API base paths; if the target uses SSR with no client bundles,
   crawl rendered HTML for `data-*` attributes and inline JSON config blobs.
3. **Passive asset / subdomain discovery.** Primary: `subfinder`. Fallback: `amass passive` →
   `assetfinder`. If all three are unavailable, scrape crt.sh + DNS brute with a small
   targeted wordlist. Weight forgotten, legacy, staging, and acquisition hosts higher — they
   concentrate misconfigurations and stale auth — but confirm each against the allowlist before
   probing.
4. **Live-host probe + triage.** Primary: `httpx`. Fallback: `curl -I` in a loop with
   timeout + status extraction. Either way: capture status, title, and technology fingerprint.
5. **JS-aware crawl.** Primary: `katana`. Fallback: `gospider` or `hakrawler`; if no crawler
   is available, extract links from `curl` output with `grep -oP` on `href`/`src` attributes.
6. **Historical URLs.** Primary: `gau`. Fallback: `waybackurls`; if both are unavailable,
   query the Wayback Machine CDX API directly with `curl`.
7. **Parameter mining.** Primary: `Arjun`. Fallback: `x8` or manual param brute from the
   JS-mined parameter names (step 2). Deduplicate the URL/param corpus.
8. **Class-triage with `gf`.** Run the `gf` pattern packs over the collected URLs to bucket
   candidates per vulnerability class (the routing table below). Fallback: `grep -E` with the
   same regex patterns `gf` uses if the tool is not installed.

Use `interactsh` for any blind-signal confirmation later; recon itself stops at enumeration.

## Surface routing to hunters

Recon's output is a routed candidate surface. Each item is tagged and handed to the hunter that
exercises it (this is the recon-signal → CWE routing map).

| Recon signal / `gf` pattern | Route to |
|---|---|
| `gf ssrf` (`url,dest,redirect,uri,path,continue,domain,callback`) | [`ssrf-hunter`](../ssrf-hunter/SKILL.md) |
| `gf redirect` (open-redirect params) | open-redirect (planned) → chains into `ssrf-hunter` |
| `gf xss` | [`xss-reflected-hunter`](../xss-reflected-hunter/SKILL.md) / [`xss-stored-hunter`](../xss-stored-hunter/SKILL.md) |
| `gf sqli` | [`sqli-hunter`](../sqli-hunter/SKILL.md) |
| path / file / include params, `gf lfi` | [`path-traversal-hunter`](../path-traversal-hunter/SKILL.md) |
| object-id / UUID / multi-tenant params (`org_id`, `account_id`) | [`idor-hunter`](../idor-hunter/SKILL.md) / [`access-control-hunter`](../access-control-hunter/SKILL.md) |
| JS-mined undocumented endpoints, secret-shaped strings, forgotten no-auth hosts | [`info-disclosure-hunter`](../info-disclosure-hunter/SKILL.md) (CWE-200) + [`auth-bypass-hunter`](../auth-bypass-hunter/SKILL.md) (CWE-306) |
| admin / role / privileged routes | [`privesc-hunter`](../privesc-hunter/SKILL.md) |

A routed item enters its hunter as an **observation**, not a finding; promotion to a
vulnerability happens through [`dynamic-poc-validation`](../dynamic-poc-validation/SKILL.md).

## Output: surface map + pre_scan refresh

Resolve the target directory with `tools/_target_discovery.sh`, then:

- **Surface map → `notes/`.** Write the curated, routed surface map to
  `<target>/notes/recon/surface-map.md` (research-time material per `CLAUDE.md`), redacted.
- **`pre_scan.yaml` — refresh only two things.** Update `last_run` and append routed,
  not-yet-triaged items to `unresolved_candidates` / `open_chains_unresolved`. **Never** touch
  `asset_fingerprint` or `known_findings_count` — those are contract-bound to the manifest
  (`OPEN_CONTRACT.yaml` `field_ownership.pre_scan`; the count must equal manifest length).
- Do not invent finding counts or promote candidates here.

After completing the pipeline, explore adjacent surface the steps did not cover — the skill
is a floor, not a ceiling.

## Stop conditions (verified negatives)

Each stop condition below carries one of the 12 categories from
[`skills/references/negative-control-taxonomy.md`](../references/negative-control-taxonomy.md).
Apply ALL applicable labels. Never route or escalate anything that triggers a category below.

**Decision split (apply separately, never collapse):**
- `technically_vulnerable`: is there an actual weakness, or just an endpoint?
- `in_scope`: does the program policy + `contract.yaml` cover this asset?
- `program_reportable`: would the eventual impact meet the program's threshold?
A surface item can be reachable yet out of scope. Do not route on reachability alone.

- `[out_of_scope_asset]` A discovered host/subdomain/endpoint is not in the allowlist — do not
  probe or route it; public reachability is not permission. `[technical_placeholder]`
- `[prohibited_test_method]` Surfacing an item would require brute-force/DoS-level fuzzing or
  concurrency — stop and stay within the rate budget. `[technical_placeholder]`
- `[missing_security_boundary]` / `[expected_product_behavior]` The endpoint is public by
  design and needs no auth — not a finding. `[technical_placeholder]`
- `[theoretical_without_oracle]` A JS-referenced route that does not resolve or authenticate is
  a candidate to test, not evidence of anything. `[technical_placeholder]`

These entries are `[technical_placeholder]`: recon is methodology-seeded, not corpus-mined, so
the taxonomy is their source of authority until curated negatives back them.

## Anti-patterns

- Do not treat public reachability as permission; confirm every host against the allowlist.
- Do not exceed the rate budget, use concurrency, or run any DoS/stress/resource-exhaustion.
- Do not pivot into third-party, cloud-metadata, or acquisition infrastructure that is not
  explicitly in scope; treat every redirect/integration as a new authorization boundary.
- Do not overwrite `pre_scan.yaml` `asset_fingerprint` or `known_findings_count`; recon only
  refreshes `last_run` + `unresolved_candidates`.
- Do not treat URL volume as progress — route candidates to hunters, do not hoard lists.
- Redact secrets, tokens, and internal hostnames before committing a surface map; do not commit
  raw `*.js` trees or giant URL dumps (gitignored) — commit the curated map only.

## Evidence basis and limits

Methodology-seeded, not corpus-mined: the `CLAUDE.md` "mine the JS bundles first" mandate,
`METHODOLOGY.md` dynamic-surface-mapping steps, NahamSec's documented recon pipeline
([`knowledge-sources/creators/03-nahamsec.md`](../../knowledge-sources/creators/03-nahamsec.md)),
the tool registry, and the routing map in
[`knowledge-sources/INTEGRATION-RECOMMENDATIONS.md`](../../knowledge-sources/INTEGRATION-RECOMMENDATIONS.md).
Recon produces candidate surface; every routed item still owes its hunter a dynamic proof.

## AI-assisted augment (NahamSec seed)

Transferable technique from Ben Sadeghipour (NahamSec), public PlexTrac "Homework for Hackers"
webinar (`Ue-OIJoM0bA`); see the creator file linked above. Guardrail: model output is a
hypothesis, not evidence — confirm each candidate against target behavior and never paste
confidential target vocabulary, JS bundles, or evidence into an unapproved model
(`nahamsec-ai-sanitize-before-sharing`, CWE-200).

- **Neighbor path / endpoint / param idea generation (`nahamsec-ai-neighbor-path-ideas`).**
  From observed naming (routes, filenames, product vocabulary, subdomain patterns), ask an
  approved model for likely siblings, abbreviations, translations, and naming transformations
  to widen content discovery beyond generic wordlists. Deduplicate and rank, then probe slowly
  against nonexistent controls within the rate budget; a candidate counts only when its
  response differs materially from a random control.

## Version boundaries

Null — this is a process/foundational skill, not version-bound.
