# OSV and GitHub Advisory lookup reference

## OSV identifier query

Use POST `/v1/query` with a CVE or GHSA identifier:

```bash
curl -sS -X POST 'https://api.osv.dev/v1/query' \
  -H 'Content-Type: application/json' \
  -d '{"id":"GHSA-wrh9-cjv3-2hpw"}' \
  -D raw/osv.headers -o raw/osv.json
```

## OSV package/version query

Use the registered ecosystem spelling and an exact package version:

```bash
curl -sS -X POST 'https://api.osv.dev/v1/query' \
  -H 'Content-Type: application/json' \
  -d '{"package":{"name":"sequelize","ecosystem":"npm"},"version":"6.19.0"}' \
  -D raw/osv-package.headers -o raw/osv-package.json
```

For a source-control commit query:

```bash
curl -sS -X POST 'https://api.osv.dev/v1/query' \
  -H 'Content-Type: application/json' \
  -d '{"commit":"FULL_GIT_SHA"}' \
  -D raw/osv-commit.headers -o raw/osv-commit.json
```

## OSV output model

The query response contains `vulns[]`; an ID query or version query may still return multiple
records. Preserve these fields:

- `id`, `aliases`, `modified`, `published`, `withdrawn`;
- `summary`, `details`, `references[]`;
- `severity[]` entries, including their scoring system;
- `database_specific`, including severity/CWE data when supplied;
- `affected[].package` and `affected[].ecosystem_specific`;
- `affected[].ranges[]` with `type`, optional `repo`, and ordered `events[]`;
- `affected[].versions[]` when present.

Range event meanings depend on range type. `introduced` opens a vulnerable interval; `fixed`
closes it at the first fixed version/commit; `last_affected` is inclusive; `limit` constrains the
range without asserting a fix. Multiple event pairs may describe disjoint intervals. Never sort
semantic versions lexically or collapse ecosystem and Git ranges.

## GitHub global advisory endpoint

Fetch `GET /advisories/{ghsa_id}` after resolving a GHSA alias:

```bash
curl -sS \
  -H 'Accept: application/vnd.github+json' \
  -H 'X-GitHub-Api-Version: 2022-11-28' \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  'https://api.github.com/advisories/GHSA-wrh9-cjv3-2hpw' \
  -D raw/ghsa.headers -o raw/ghsa.json
```

Inspect identifiers, summary/description, severity/CVSS, CWEs, vulnerabilities, references,
publication/update dates, and withdrawal status. `references[]` can contain repository commits,
PRs, issues, releases, vendor advisories, or third-party pages. Verify the upstream repository and
commit reachability independently.

## Commit and pull-request corroboration

```text
GET /repos/{owner}/{repo}/commits/{sha}
GET /repos/{owner}/{repo}/commits/{sha}/pulls
GET /repos/{owner}/{repo}/pulls/{pull_number}
GET /repos/{owner}/{repo}/issues/{issue_number}/comments
GET /repos/{owner}/{repo}/pulls/{pull_number}/reviews
```

Use immutable commit SHAs and comment permalinks in evidence. Record endpoint, API version,
retrieval time, response status, ETag/Last-Modified when present, and response hash. Do not retain
authorization headers.

## Authentication and rate limits

GitHub REST commonly permits 60 requests/hour for unauthenticated requests from an IP and a much
higher authenticated allowance; verify the returned `X-RateLimit-Limit`, `Remaining`, `Reset`, and
`Resource` headers rather than assuming a fixed quota. Use a fine-grained token when needed and
never write it to logs. GitHub Search has separate limits. Respect `Retry-After` and secondary
rate-limit responses; do not parallelize aggressively.

OSV queries do not require an API key, but clients must still cache results, identify themselves
when appropriate, handle 429/5xx responses with bounded backoff, and record retrieval time.

## Failure handling

- Empty response: verify aliases, ecosystem spelling, package name, and version semantics.
- Conflicting records: preserve each record and flag the disagreement for review.
- Private/deleted repo: use public advisory references or vendor/distro patches; do not bypass.
- Missing fix: record `null`, advisory status, and searches performed.
- Withdrawn advisory: preserve the record and stop promotion pending human review.
