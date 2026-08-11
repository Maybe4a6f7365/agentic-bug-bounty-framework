"""
checkers/builtin/package_registry.py — Package / container registry version checker.

Supported registries:
  - PyPI:          {"registry": "pypi", "package": "requests"}
  - npm:           {"registry": "npm", "package": "react"}
  - Docker Hub:    {"registry_url": "https://hub.docker.com/v2/repositories/{repo}/tags", "field": "name"}

Docker Hub detection: if config has a `registry_url` containing "hub.docker.com",
the checker uses the Docker Hub v2 API to fetch the latest tag.

immutable_identifier = hash of version + registry + package (stable identifier).
"""

import hashlib, json, re, urllib.request, urllib.error
from urllib.parse import urlparse

# ── Registry configurations ──────────────────────────────────────

REGISTRIES = {
    "pypi": {
        "url_template": "https://pypi.org/pypi/{package}/json",
        "version_path": ["info", "version"],
        "name_path": ["info", "name"],
        "accept": "application/json",
    },
    "npm": {
        "url_template": "https://registry.npmjs.org/{package}/latest",
        "version_path": ["version"],
        "name_path": ["name"],
        "accept": "application/json",
    },
}


class _Err:
    STORAGE_MOVED   = "STORAGE_MOVED"
    AUTH_REQUIRED   = "AUTH_REQUIRED"
    RATE_LIMITED    = "RATE_LIMITED"
    TIMEOUT         = "TIMEOUT"
    PARSE_ERROR     = "PARSE_ERROR"
    EMPTY_RESPONSE  = "EMPTY_RESPONSE"
    UNKNOWN         = "UNKNOWN"


def _extract_path(data, path_parts: list):
    """Walk nested dict by path. Returns None if any key is missing."""
    current = data
    for key in path_parts:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _fetch_json(url: str, req_headers: dict, timeout: int = 30) -> dict:
    """Fetch JSON from a URL with http_cache and error handling."""
    try:
        raw = http_cache.fetch(
            url, req_headers, timeout=timeout,
            # npm/pypi redirects (e.g., to registry mirrors, version-pinned
            # canonical URLs) are part of the registry protocol. 2026-08-06
            # audit: explicitly opt in to follow.
            follow_redirects=True,
        )
        if raw is None:
            return None  # 304 — content unchanged
    except urllib.error.HTTPError as e:
        code_map = {404: _Err.STORAGE_MOVED, 410: _Err.STORAGE_MOVED,
                    401: _Err.AUTH_REQUIRED, 403: _Err.AUTH_REQUIRED, 429: _Err.RATE_LIMITED}
        raise CheckerError(code_map.get(e.code, _Err.UNKNOWN), f"HTTP {e.code}: {url}")
    except urllib.error.URLError as e:
        if "timed out" in str(e).lower():
            raise CheckerError(_Err.TIMEOUT, f"Timeout: {url}")
        raise CheckerError(_Err.UNKNOWN, f"URL error: {e}")

    if not raw or not raw.strip():
        raise CheckerError(_Err.EMPTY_RESPONSE, f"Empty response from {url}")

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise CheckerError(_Err.PARSE_ERROR, f"Invalid JSON from {url}")


def _check_docker_hub(config: dict, last_immutable_id: str):
    """Check Docker Hub for latest tag.

    Config: {"registry_url": "https://hub.docker.com/v2/repositories/{repo}/tags",
             "field": "name"}
    """
    registry_url = config.get("registry_url", "")
    field = config.get("field", "name")

    if not registry_url:
        raise CheckerError(_Err.PARSE_ERROR, "Missing 'registry_url' in Docker Hub config")

    # Parse the repo path from the URL
    # URL pattern: /v2/repositories/<namespace>/<repo>/tags
    parsed = urlparse(registry_url)
    match = re.search(r'/v2/repositories/(.+?)/tags', parsed.path)
    if not match:
        raise CheckerError(_Err.PARSE_ERROR,
                           f"Cannot parse repo path from Docker Hub URL: {registry_url}")
    repo_path = match.group(1)

    # Build fetch URL — append ?page_size=1 for latest tag only
    fetch_url = registry_url.rstrip("/")
    if "?" not in fetch_url:
        fetch_url += "/?page_size=1"
    elif "page_size" not in fetch_url:
        fetch_url += "&page_size=1"

    req_headers = identity.tool_headers({"Accept": "application/json"})

    data = _fetch_json(fetch_url, req_headers)
    if data is None:
        return None  # 304 unchanged

    results = data.get("results", [])
    if not results:
        raise CheckerError(_Err.PARSE_ERROR,
                           f"No tags found for {repo_path} on Docker Hub")

    latest = results[0]
    version_value = str(latest.get(field, ""))
    if not version_value:
        raise CheckerError(_Err.PARSE_ERROR,
                           f"Field '{field}' not found in Docker Hub tag result for {repo_path}")

    immutable_id = hashlib.sha256(
        f"docker:{repo_path}:{version_value}".encode()
    ).hexdigest()[:16]

    if last_immutable_id and immutable_id == last_immutable_id:
        return None

    content_hash = hashlib.sha256(json.dumps(data).encode()).hexdigest()

    return CheckResult(
        changed=True,
        version_value=version_value,
        immutable_identifier=immutable_id,
        published_at=latest.get("last_updated"),
        content_hash=content_hash,
        raw_metadata={
            "registry": "docker_hub",
            "repo": repo_path,
            "tag_count": data.get("count"),
            "latest_tag": version_value,
            "tag_id": latest.get("id"),
            "tag_status": latest.get("tag_status"),
        },
        change_type="release_published",
    )


def _check_named_registry(config: dict, registry_name: str, package: str,
                          last_immutable_id: str):
    """Check a named registry (pypi, npm) for the latest package version."""
    reg = REGISTRIES.get(registry_name)
    if not reg:
        supported = ", ".join(REGISTRIES.keys())
        raise CheckerError(_Err.PARSE_ERROR,
                           f"Unsupported registry '{registry_name}'. Supported: {supported}")

    url = reg["url_template"].format(package=package)
    req_headers = identity.tool_headers({"Accept": reg["accept"]})

    data = _fetch_json(url, req_headers)
    if data is None:
        return None  # 304 unchanged

    version = _extract_path(data, reg["version_path"])
    if version is None:
        raise CheckerError(_Err.PARSE_ERROR,
                           f"Version not found at path {reg['version_path']} in response")

    version_value = str(version)
    package_name = _extract_path(data, reg["name_path"]) or package
    content_hash = hashlib.sha256(json.dumps(data).encode()).hexdigest()
    immutable_id = hashlib.sha256(
        f"{registry_name}:{package}:{version_value}".encode()
    ).hexdigest()[:16]

    if last_immutable_id and immutable_id == last_immutable_id:
        return None

    return CheckResult(
        changed=True,
        version_value=version_value,
        immutable_identifier=immutable_id,
        content_hash=content_hash,
        raw_metadata={
            "registry": registry_name,
            "package": package,
            "package_name": package_name,
            "url": url,
            "response_keys": list(data.keys())[:20] if isinstance(data, dict) else f"[{type(data).__name__}]",
        },
        change_type="release_published",
    )


def check(config: dict):
    last_immutable_id = config.get("_last_immutable_id")

    # ── Detect Docker Hub from registry_url ──
    registry_url = config.get("registry_url", "")
    if registry_url and "hub.docker.com" in registry_url:
        return _check_docker_hub(config, last_immutable_id)

    # ── Derive registry/package from registry_url when missing (bug #8) ──
    registry_name = config.get("registry", "").lower()
    package = config.get("package", "") or config.get("repo", "")

    if registry_url and (not registry_name or not package):
        parsed = urlparse(registry_url)
        # PyPI: https://pypi.org/pypi/{package}/json
        if "pypi.org" in parsed.netloc:
            if not registry_name:
                registry_name = "pypi"
            if not package:
                m = re.match(r"/pypi/([^/]+)/json", parsed.path)
                if m:
                    package = m.group(1)
        # npm: https://registry.npmjs.org/{package}/latest
        elif "registry.npmjs.org" in parsed.netloc:
            if not registry_name:
                registry_name = "npm"
            if not package:
                m = re.match(r"/(@[^/]+/[^/]+|[^/]+)/latest", parsed.path)
                if m:
                    package = m.group(1)

    # ── Named registries (pypi, npm) ──
    if not registry_name:
        registry_name = "pypi"

    if not package:
        raise CheckerError(_Err.PARSE_ERROR,
                           "Missing 'package' in config — got keys: " +
                           ", ".join(sorted(config.keys())))

    return _check_named_registry(config, registry_name, package, last_immutable_id)
