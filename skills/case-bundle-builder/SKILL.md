---
name: case-bundle-builder
description: Construct a complete case-bundle.yaml from a CVE/GHSA + repo + fix-commit pair, populating all 8 schema sections and marking the 5 star-rated fields for human review. Load when ingesting a vulnerability into the engineering-source layer, or when a hunter asks for the engineering context behind a CVE. Triggers — build a case bundle, ingest a CVE into engineering sources, extract engineering context for a CVE/GHSA.
---

# Case-Bundle Builder

## What this skill is — and is not

Use this build-time meta-skill to construct one complete `case-bundle.yaml` from a CVE/GHSA,
repository, and introduced/fixed commit evidence. Populate all eight canonical schema sections.
Preserve raw evidence separately and make every inference auditable. This is not a target-time
hunt skill, recon skill, exploit generator, or authorization to test a live system. Do not turn
historical PoCs into active probes. The output is engineering-source training material, not a
finding or submission.

## Canonical resources

- Treat `../../knowledge-sources/engineering-sources/CASE-BUNDLE-SCHEMA.md` as canonical.
- Copy and fill `../../knowledge-sources/engineering-sources/templates/case-bundle.yaml`.
- Use `templates/case-bundle.yaml` only as a provenance-preserving convenience snapshot; if it
  differs from the shared template, stop and use the shared template.
- Read `references/case-bundle-schema.md` before mapping fields.
- Read `references/osv-ghsa-lookup.md` before querying OSV or GitHub.
- Read `references/git-diff-patterns.md` before interpreting a patch or tests.

## Preparation — collect inputs

Require at least one of:

- a CVE or GHSA identifier; or
- a repository URL plus an explicit introduced/fixed commit pair.

Collect when available:

- package name and ecosystem for an unambiguous OSV query;
- repository URL, vulnerable commit, fix commit, and default branch;
- maintainer issue, pull request, release-note, or advisory links;
- a public PoC or disclosed H1/VRP report link;
- destination path, stable `case_id`, and reviewer identity.

Never infer a commit solely from a version string. Record missing values as `null` with a reason.
Keep a workspace layout such as `raw/`, `repo/`, `artifacts/`, and `bundle/`. Do not overwrite
previous evidence; use a new case directory or an explicit revision.

## Phase A — OSV/GHSA lookup

Prefer an identifier query when the ID is known:

```bash
curl -sS -X POST 'https://api.osv.dev/v1/query' \
  -H 'Content-Type: application/json' \
  -d '{"id":"CVE-2023-25813"}' \
  -D raw/osv-response.headers \
  -o raw/osv-response.json
```

For a package/version query, include the ecosystem exactly as OSV expects:

```bash
curl -sS -X POST 'https://api.osv.dev/v1/query' \
  -H 'Content-Type: application/json' \
  -d '{"package":{"name":"sequelize","ecosystem":"npm"},"version":"6.19.0"}' \
  -D raw/osv-response.headers \
  -o raw/osv-response.json
```

Extract without flattening away range semantics:

- `id`, `aliases`, `summary`, `details`, and `references`;
- `severity[]` plus `database_specific.severity` when present;
- `affected[].package.{ecosystem,name,purl}`;
- every `affected[].ranges[].{type,repo,events}` entry;
- each `introduced`, `fixed`, `last_affected`, or `limit` event.

Do not equate `introduced: "0"` with a Git commit. In an ecosystem range it means the beginning
of the package's version history. Preserve multiple ranges and database disagreements. Save the
raw response, headers, request body, retrieval time, and hash before creating a normalized
pre-bundle snippet:

```json
{
  "advisory_ids": ["GHSA-…", "CVE-…"],
  "package": {"name": "…", "ecosystem": "…"},
  "ranges": [{"type": "SEMVER", "events": [{"introduced": "…"}, {"fixed": "…"}]}],
  "unresolved": ["vulnerable_commit", "fix_commit"]
}
```

## Phase B — identify repository and commits

Resolve a CVE alias to its GHSA record, then request the global advisory endpoint:

```bash
curl -sS \
  -H 'Accept: application/vnd.github+json' \
  -H 'X-GitHub-Api-Version: 2022-11-28' \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  'https://api.github.com/advisories/GHSA-xxxx-xxxx-xxxx' \
  -D raw/ghsa-response.headers \
  -o raw/ghsa-response.json
```

Inspect `references[]`, `vulnerabilities[]`, identifiers, publication dates, and CWE data. A
repository URL in a reference is a candidate, not proof that it is upstream. Prefer links to a
commit, pull request, compare view, release, or the project's own advisory.

For each candidate SHA, preserve commit metadata:

```bash
curl -sS \
  -H 'Accept: application/vnd.github+json' \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  'https://api.github.com/repos/OWNER/REPO/commits/SHA' \
  -o raw/commit-SHA.json
```

Confirm that the fixed commit is reachable from the fixed release tag. Derive the vulnerable
commit from explicit advisory evidence, a parent of a single fix commit, or a tagged vulnerable
release—record which rule was used. For merge commits, determine whether the relevant comparison
is first-parent, PR base/head, or release-to-release; do not silently choose.

For private, deleted, or inaccessible repositories, use public NVD/GHSA references, release
notes, distro patches, or a vendor mirror. Mark the repository/commit relationship as unresolved
when those sources cannot prove it. Never fabricate a SHA.

## Phase C — retrieve and preserve the patch diff

Clone into the case workspace without mutating the upstream repository:

```bash
git clone --filter=blob:none --no-checkout 'https://github.com/OWNER/REPO.git' repo
git -C repo fetch --tags --force
git -C repo cat-file -e 'INTRODUCED_SHA^{commit}'
git -C repo cat-file -e 'FIXED_SHA^{commit}'
git -C repo merge-base --is-ancestor INTRODUCED_SHA FIXED_SHA
```

Inspect the history before selecting the comparison:

```bash
git -C repo log --oneline --decorate --ancestry-path INTRODUCED_SHA..FIXED_SHA
git -C repo show --stat --summary FIXED_SHA
git -C repo diff --find-renames --find-copies \
  INTRODUCED_SHA..FIXED_SHA > artifacts/introduced-to-fixed.patch
```

If `INTRODUCED_SHA` denotes the commit that introduced the defect, compare the vulnerable tree
to the fixed tree; do not assume its parent is the desired vulnerable snapshot. If the advisory
only identifies a fix commit, use `FIXED_SHA^..FIXED_SHA` only after confirming it is a non-merge
single-fix commit. For merge commits, record parent selection and also retain the PR diff if
available.

Keep large diffs outside YAML. Set `engineering_evidence.patch_diff` to a structured reference
containing artifact path, comparison endpoints, format, and SHA-256. Extract short root-cause
motifs into `root_cause_summary`, but never substitute a prose summary for the actual patch.
Separate generated files, vendored code, lockfiles, and unrelated refactors from security-relevant
hunks. Record ambiguity instead of choosing the most dramatic hunk.

## Phase D — collect maintainer discussion

Search locally for issue or PR identifiers attached to the fix:

```bash
git -C repo log --all --decorate --oneline --grep='CVE-\|GHSA-\|security\|injection'
git -C repo show -s --format='%H%n%B%n%N' FIXED_SHA > artifacts/fix-message.txt
```

Search GitHub within the resolved repository and narrow by SHA, advisory ID, package, and fix
terms. Example queries (URL-encode in automation):

```text
GET /search/issues?q=repo:OWNER/REPO+FIXED_SHA
GET /search/issues?q=repo:OWNER/REPO+GHSA-xxxx-xxxx-xxxx
GET /repos/OWNER/REPO/commits/FIXED_SHA/pulls
```

Collect issue/PR URLs, author role, timestamps, review comments, requested tests, severity debate,
rejected approaches, and release/backport decisions. Quote minimally; store raw API responses and
write concise notes with comment permalinks. A HackerOne or other public report may supplement
maintainer discussion but must not be mislabeled as maintainer-authored evidence.

If no discussion is public, set the field to `null` with the searches performed and the result.
The absence of public discussion is not evidence that none occurred. This star field still
requires a human to verify search coverage and interpretation.

## Phase E — identify regression tests

List changed files and classify likely tests:

```bash
git -C repo diff --name-status --find-renames INTRODUCED_SHA..FIXED_SHA \
  > artifacts/changed-files.txt
git -C repo diff --name-only INTRODUCED_SHA..FIXED_SHA | \
  rg '(^|/)(test|tests|spec|specs|__tests__)/|(^|/)(test_|.*[._-](test|spec)\.)'
```

Review candidate hunks to distinguish security regression assertions from fixtures, snapshots,
test helpers, formatting, or unrelated coverage. Identify the assertion that fails on the
vulnerable tree and passes on the fixed tree. Record test path, test name, commit, runner command,
expected vulnerable result, expected fixed result, and execution status.

Do not claim a test was executed unless logs exist. If no test changed, search nearby commits and
the linked PR; otherwise use `null` with the reason `no changed regression test found`. See
`references/git-diff-patterns.md` for language conventions and merge/rename pitfalls.

## Phase F — construct the bundle

Start from the canonical shared template:

```bash
cp knowledge-sources/engineering-sources/templates/case-bundle.yaml \
  WORKSPACE/bundle/case-bundle.yaml
```

Fill every field; use `null` plus a concise reason when evidence is absent. Never delete a schema
field merely because it is unknown.

| Section | Populate from |
|---|---|
| `classification` | GHSA/OSV CWE data, alternatives, and human mapping decision |
| `environment` | affected package, repo language/framework, component, introduced/fixed ranges |
| `researcher_evidence` | public report/PoC, reproduction claim, impact, privileges, preconditions |
| `engineering_evidence` | verified repo/SHAs, patch artifact, tests, discussion, root-cause review |
| `behavioral_model` | patch/test-derived input, boundary, missing control, oracle, safe comparison |
| `agent_guidance` | applicability, hypotheses, safe probes, proof bar, false positives, stops |
| `triage` | independent technical, scope, and reportability labels plus reviewer reasoning |
| `provenance` | source inventory, versions, licenses, retrieval times, hashes, reviewer |

Keep facts and inferences distinct. The patch proves code changed, not automatically that every
listed version is exploitable. The test proves a behavior under its fixture, not universal
reachability. Map `vulnerable_version` and `fixed_version` from ecosystem events; map commit fields
only from repository evidence.

Represent the five star-rated fields with evidence references and an explicit review state:

- `behavioral_model.negative_control`;
- `engineering_evidence.maintainer_discussion`;
- `engineering_evidence.patch_diff`;
- `engineering_evidence.changed_tests`;
- `agent_guidance.false_positive_conditions`.

Append a non-schema review block only if the ingestion system permits extensions; otherwise keep
it in a sibling review file. Never imply that the canonical schema itself defines this block:

```yaml
human_review_required:
  marker: "[HUMAN-REVIEW-REQUIRED]"
  fields:
    - behavioral_model.negative_control
    - engineering_evidence.maintainer_discussion
    - engineering_evidence.patch_diff
    - engineering_evidence.changed_tests
    - agent_guidance.false_positive_conditions
  status: pending
```

Do not promote `classification.mapping_confidence` from `auto` to `reviewed`, fill
`provenance.human_reviewer`, or set the star review to complete without an identified human.

## Phase G — record provenance and integrity

Create a source ledger containing the exact request URL/method, non-secret request body, response
path, status, API version, retrieval timestamp, license, and content hash. Redact authorization
headers and tokens. Preserve OSV lookup time and GitHub response headers relevant to versioning
and rate limits.

Hash every ingested evidence artifact, not just the final YAML:

```bash
sha256sum raw/osv-response.json raw/ghsa-response.json \
  artifacts/introduced-to-fixed.patch bundle/case-bundle.yaml
```

Place stable artifact identifiers in `provenance.content_hashes`, preferably as mappings or
`sha256:<hex>  <relative-path>` strings consistent with the consuming pipeline. Hash the bundle
only after all content is final; changing the embedded bundle hash creates a self-reference, so
store the final bundle hash in the external ledger unless the canonical consumer defines a
detached-hash convention.

Record per-source license, not one blanket license. Use `unknown — review required` when licensing
cannot be established. `retrieved_at` must be ISO 8601 with timezone. Keep commit SHAs and release
tags in `source_versions`; an HTTP retrieval timestamp is not a source version.

## Evidence basis and limits

- Treat OSV/GHSA as indexing evidence, not infallible ground truth.
- Treat Git history, the minimal patch, and regression behavior as primary engineering evidence.
- Flag conflicting aliases, version ranges, repositories, commits, and CWE mappings.
- Do not infer exploitability from a CVSS score or vulnerable dependency presence alone.
- Do not copy a PoC into active execution; describe only what public evidence demonstrates.
- Mark non-public, embargoed, or responsible-disclosure-active patches as unavailable.
- Never attempt to bypass repository access controls or disclosure restrictions.
- Record missing patch, test, or discussion evidence explicitly.
- Remember that the bundle is only as good as its inputs: garbage in, garbage out.
- Require human review of the five star fields even when all automated checks pass.

## Version boundaries

```yaml
version_boundaries: null
```

Reason: this build-time skill defines application logic for what belongs in a case bundle. It is
not bound to a target product version. Version boundaries belong inside each constructed bundle's
`environment` and supporting OSV/GHSA evidence, never in the skill's own applicability metadata.

## Stop conditions

Apply a three-label split before completing a bundle:

```yaml
labels:
  technically_vulnerable: true | false | unknown
  in_scope: true | false | unknown
  reportable: true | false | unknown
```

Stop or downgrade the build when any condition holds:

- `[out_of_scope_asset]` Stop external acquisition when the repository or artifact is explicitly
  excluded, inaccessible without authorization, or outside the ingestion scope; retain only
  already-authorized metadata.
- `[duplicate_root_cause]` Stop creating a second case when multiple CVE/GHSA IDs resolve to the
  same fix and root cause; add aliases to the existing case unless materially distinct behavior
  is proven.
- `[insufficient_version_boundary]` Stop claiming affected versions when no authoritative range
  or reproducible tag boundary exists; keep the technical label `unknown`.
- `[unverifiable_commit_pair]` Stop patch interpretation when either endpoint is missing,
  unreachable, unrelated, or the merge-base/parent choice cannot be justified.
- `[no_public_patch]` Stop code-level extraction when a patch remains private, embargoed, or
  responsible disclosure is active; flag the bundle incomplete without attempting access.
- `[unsafe_or_prohibited_action]` Stop before executing PoCs, live-target probes, destructive
  tests, credential use, or any activity beyond passive build-time evidence collection.
- `[human_review_missing]` Stop promotion to ingestion-ready while any star field is unreviewed,
  provenance is incomplete, or the three triage labels lack reviewer reasoning.

## Completion checklist

- Validate YAML and preserve all eight schema sections.
- Confirm every fact points to a source or local hashed artifact.
- Confirm all five star fields carry `[HUMAN-REVIEW-REQUIRED]` status until reviewed.
- Confirm technical vulnerability, scope, and reportability remain independent.
- Confirm the original engineering-sources schema and template were not modified.
- Report created files, validation results, diff stats, and unresolved evidence honestly.

## Worked example — CVE-2023-25813 / Sequelize SQL injection

This example is a construction illustration based on the repository's curated
`version-boundaries.md`; it is not a live API result. The stored row records
`GHSA-wrh9-cjv3-2hpw`, alias `CVE-2023-25813`, npm package `sequelize`, critical severity,
`introduced: "0"`, `fixed: "6.19.1"`, and SQL injection via `replacements`.

Illustrative normalized OSV excerpt:

```json
{
  "id": "GHSA-wrh9-cjv3-2hpw",
  "aliases": ["CVE-2023-25813"],
  "summary": "SQL injection via replacements",
  "database_specific": {"severity": "CRITICAL"},
  "affected": [{
    "package": {"ecosystem": "npm", "name": "sequelize"},
    "ranges": [{"type": "SEMVER", "events": [
      {"introduced": "0"}, {"fixed": "6.19.1"}
    ]}]
  }]
}
```

Do not invent missing repository commits from that range. A safe pre-review bundle excerpt is:

```yaml
case_id: CASE-CVE-2023-25813
classification:
  cwe_leaf: CWE-89                     # SQL injection; requires human review
  cwe_class: null                      # broader class not established by stored row
  mapping_confidence: auto
  alternative_mappings: []
environment:
  product: sequelize
  framework: Sequelize
  language: js
  component: replacements handling
  vulnerable_version: ">=0 <6.19.1"
  fixed_version: "6.19.1"
engineering_evidence:
  vulnerable_repository: "https://github.com/sequelize/sequelize"
  vulnerable_commit: null              # resolve from primary evidence
  fix_commit: null                     # resolve from primary evidence
  patch_diff: null                     # [HUMAN-REVIEW-REQUIRED]
  changed_tests: null                  # [HUMAN-REVIEW-REQUIRED]
  maintainer_discussion: null          # [HUMAN-REVIEW-REQUIRED]
  root_cause_summary: "Unreviewed advisory claim: SQL injection through replacements"
behavioral_model:
  negative_control: "6.19.1 behavior; exact oracle pending patch/test review" # ★ review
agent_guidance:
  false_positive_conditions:           # ★ review
    - "dependency version alone does not prove the vulnerable call path is reachable"
triage:
  technically_vulnerable: unknown
  in_scope: unknown
  reportable: unknown
provenance:
  sources:
    - "knowledge-sources/engineering-sources/version-boundaries.md"
  source_versions: ["repository snapshot 2026-07-22"]
  licenses: ["CC-BY-4.0 upstream attribution recorded by source"]
  retrieved_at: null                    # set during actual build
  content_hashes: []                    # compute during actual build
  human_reviewer: null
```

Complete the omitted template fields with evidence or `null` reasons during a real build. The
example intentionally leaves commit-derived fields unresolved because this skill build performs
no live CVE lookup.
