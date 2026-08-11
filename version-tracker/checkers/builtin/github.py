"""
checkers/builtin/github.py — GitHub release and commit checker.

Auth: reads GITHUB_TOKEN from environment.
  - With token:     5,000 req/hr  (authenticated)
  - Without token:     60 req/hr  (unauthenticated IP-based)
  Generate at: https://github.com/settings/tokens (classic, no scopes needed for public repos)

Config shape:
  {"repo": "Shopify/cli", "api_endpoint": "/releases/latest", "field": "tag_name"}
  {"repo": "Shopify/cli", "api_endpoint": "/commits/main", "field": "sha"}
  {"repo": "Shopify/cli", "api_endpoint": "/tags", "field": "[0].name"}

Returns None if no change (same immutable_identifier as last observation).
Returns CheckResult if changed.
Raises CheckerError on failure.
"""

import json, os, hashlib, urllib.request, urllib.error

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
API_BASE = "https://api.github.com/repos"


class _Err:
    STORAGE_MOVED   = "STORAGE_MOVED"
    AUTH_REQUIRED   = "AUTH_REQUIRED"
    RATE_LIMITED    = "RATE_LIMITED"
    TIMEOUT         = "TIMEOUT"
    PARSE_ERROR     = "PARSE_ERROR"
    UNKNOWN         = "UNKNOWN"


def check(config: dict):
    repo = config.get("repo", "")
    endpoint = config.get("api_endpoint", "/releases/latest")
    field = config.get("field", "tag_name")
    last_immutable_id = config.get("_last_immutable_id")  # from runner
    if not repo:
        raise CheckerError(_Err.PARSE_ERROR, "Missing 'repo' in config")

    url = f"{API_BASE}/{repo}{endpoint}"
    headers = identity.tool_headers({"Accept": "application/vnd.github+json"})
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    try:
        raw = http_cache.fetch(url, headers, timeout=30)
        # follow_redirects defaults to False (2026-08-06 audit): a github
        # repo URL is bound to operator intent; a silent redirect is
        # recorded as STORAGE_MOVED so the runner can act on it.
        if raw is None:
            return None  # 304 Not Modified — content unchanged
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise CheckerError(_Err.PARSE_ERROR, f"Invalid JSON response from {url}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise CheckerError(_Err.STORAGE_MOVED, f"Repo or endpoint not found: {url}")
        if e.code in (401, 403):
            raise CheckerError(_Err.AUTH_REQUIRED, f"Auth required for {url}")
        if e.code == 429:
            raise CheckerError(_Err.RATE_LIMITED, f"Rate limited: {url}")
        raise CheckerError(_Err.UNKNOWN, f"HTTP {e.code}: {url}")
    except urllib.error.URLError as e:
        if "timed out" in str(e).lower():
            raise CheckerError(_Err.TIMEOUT, f"Timeout: {url}")
        raise CheckerError(_Err.UNKNOWN, f"URL error: {e}")

    # Navigate JSON path for field (supports dotted and array-index notation)
    value = _extract_field(data, field)
    if value is _MISSING:
        raise CheckerError(_Err.PARSE_ERROR, f"Field '{field}' not found in response")
    if value is None:
        value = ""  # JSON null → empty string version

    version_value = str(value) if not isinstance(value, str) else value

    # Immutable identifier: prefer node_id, sha, then content hash of the value
    immutable_id = None
    commit_hash = None
    if isinstance(data, dict):
        if endpoint == "/commits/main" or endpoint.endswith("/commits"):
            immutable_id = data.get("sha")
        else:
            immutable_id = data.get("node_id")
        commit_hash = (data.get("sha")
                       or (data.get("commit") or {}).get("sha")
                       or (data.get("object") or {}).get("sha"))
    if not immutable_id:
        immutable_id = hashlib.sha256(version_value.encode()).hexdigest()[:16]

    # Change detection: compare against last observation
    if last_immutable_id and immutable_id == last_immutable_id:
        return None  # no change

    return CheckResult(
        changed=True,
        version_value=version_value,
        immutable_identifier=immutable_id,
        commit_hash=commit_hash,
        release_id=data.get("id") if isinstance(data, dict) else None,
        published_at=data.get("published_at") or data.get("created_at") if isinstance(data, dict) else None,
        content_hash=hashlib.sha256(raw).hexdigest(),
        raw_metadata={"repo": repo, "endpoint": endpoint, "response_keys": list(data.keys()) if isinstance(data, dict) else "[array]"},
        change_type="release_published" if "release" in endpoint else "commit_advanced",
    )


_MISSING = object()  # sentinel: key/index not found (vs None which means JSON null)


def _extract_field(data, field: str):
    """Extract a value from nested JSON using dotted or array-index notation.
    field='tag_name' → data['tag_name']
    field='[0].name' → data[0]['name']
    field='commit.sha' → data['commit']['sha']

    Returns _MISSING when a key/index is absent, None when the value is JSON null,
    or the resolved value (which can be anything including 0, False, "", etc.).
    """
    parts = field.replace("[", ".[").split(".")
    current = data
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if part.startswith("[") and part.endswith("]"):
            try:
                idx = int(part[1:-1])
            except ValueError:
                raise CheckerError(_Err.PARSE_ERROR,
                                   f"Malformed array index in field '{field}': {part}")
            if not isinstance(current, list) or idx >= len(current):
                return _MISSING
            current = current[idx]
        else:
            if not isinstance(current, dict) or part not in current:
                return _MISSING
            current = current[part]
    return current
