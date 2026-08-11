---
name: version-tracker-discover
description: "Auto-triggered when a version checker detects a structural failure (STORAGE_MOVED, PAGE_STRUCTURE, FEED_GONE). Probes known patterns to re-discover where version information now lives, then updates the version_source."
category: bugbounty
---

# version-tracker-discover

Re-discover version sources when a checker reports a structural failure.

## Trigger

Load this skill when:
- The daily check runner reports `should_rediscover=True` for a source
- `error_classification.auto_action='trigger_discovery'` and `consecutive_failures >= max_retries`
- User says "the version checker broke for X" or "find where X publishes versions now"
- Manually invoked: `python3 /var/lib/hermes/research/version-tracker/scripts/discover.py <asset_id>`

## Probe patterns

For each vector type, try these discovery patterns in order:

### github_repository
```
1. Check if repo still exists: GET https://api.github.com/repos/{owner}/{repo}
2. Check /releases/latest, /releases, /tags
3. If 404: search GitHub for similar repos: GET https://api.github.com/search/repositories?q={repo_name}
4. If auth required: flag as likely-privatized
```

### website
```
1. Fetch the base page → look for changelog links:
   - <a href containing "changelog", "release", "version", "whats-new">
2. Try common paths:
   - /changelog, /releases, /docs/changelog, /whats-new, /updates
3. Check for RSS/Atom:
   - <link rel="alternate" type="application/rss+xml">
   - <link rel="alternate" type="application/atom+xml">
   - /feed.xml, /rss.xml, /atom.xml, /feed, /rss
4. Check page structure for version indicators:
   - <meta name="version" content="...">
   - <meta name="generator" content="...">
   - Visible version text matching semver pattern
```

### api
```
1. Probe common version endpoints:
   - GET /version, GET /api/version, GET /health, GET /status
   - GET /openapi.json, GET /swagger.json, GET /api-docs
2. Check response for version field names:
   - version, api_version, build, release, semver
```

### android_app
```
1. google-play-scraper: app({appId: '{canonical_identifier}'})
2. If not found: search Play Store by app name
3. Alternative: check APKMirror, APKPure
```

### ios_app
```
1. iTunes Search API: GET https://itunes.apple.com/lookup?bundleId={canonical_identifier}
2. If not found: search by app name
```

### rss
```
1. Re-fetch the feed URL to confirm it's gone
2. Fetch the parent website → search for new feed links
3. Check common feed paths on the parent domain
```

## Output

For each discovered source, the script:
1. Writes a `research_note` on the `asset` with discovery findings
2. Updates or inserts `version_source` rows with the new `source_url` and `config`
3. Re-enables the version_source (`enabled=TRUE, consecutive_failures=0`)
4. Returns a summary of what was found

## Manual invocation

```bash
# Re-discover for a specific asset
python3 /var/lib/hermes/research/version-tracker/scripts/discover.py <asset_id>

# Re-discover all disabled sources with trigger_discovery policy
python3 /var/lib/hermes/research/version-tracker/scripts/discover.py --all-triggered

# Dry-run: probe but don't update the database
python3 /var/lib/hermes/research/version-tracker/scripts/discover.py --dry-run <asset_id>
```

## Pitfalls

- Discovery makes HTTP requests to target sites. Some may rate-limit or block. Use reasonable delays.
- GitHub search API has a rate limit (10 req/min unauthenticated, 30 req/min authenticated). Use GITHUB_TOKEN.
- CSS selectors from the old page structure may be completely invalid on a redesigned page. Discovery should select the most likely version-bearing element and report confidence.
- The script should NOT automatically trust discovered sources. It writes them with `verification_status='unverified'` and notes `discovery_confidence` in the research_note.
