"""
checkers/builtin/ios_store.py — Apple App Store version checker.

Uses the iTunes lookup API (no key required — public App Store data)
to fetch app metadata by bundle ID.

Config shapes (from enrich.py + add_target.py):
  {"bundle_id": "com.example.app",
   "api_url": "https://itunes.apple.com/lookup?bundleId=com.example.app"}

Fallback: if api_url is missing, constructs it from bundle_id.

Error codes:
  APP_UNLISTED — app not found (empty results)
  PARSE_ERROR  — version could not be extracted
  UNKNOWN      — network failure or unexpected response
"""

import hashlib, json, urllib.request, urllib.error


class _Err:
    APP_UNLISTED   = "APP_UNLISTED"
    PARSE_ERROR    = "PARSE_ERROR"
    TIMEOUT        = "TIMEOUT"
    RATE_LIMITED   = "RATE_LIMITED"
    EMPTY_RESPONSE = "EMPTY_RESPONSE"
    UNKNOWN        = "UNKNOWN"


def check(config: dict):
    bundle_id = config.get("bundle_id", "")
    api_url = config.get("api_url", "")
    last_immutable_id = config.get("_last_immutable_id")

    if not api_url and bundle_id:
        api_url = f"https://itunes.apple.com/lookup?bundleId={bundle_id}"

    if not api_url:
        raise CheckerError(
            _Err.PARSE_ERROR,
            "Missing 'api_url' or 'bundle_id' in config — got keys: "
            + ", ".join(sorted(config.keys())),
        )

    req_headers = identity.tool_headers({"Accept": "application/json"})

    try:
        raw = http_cache.fetch(api_url, req_headers, timeout=30)
        # follow_redirects defaults to False (2026-08-06 audit): the App
        # Store API URL is bound to the operator-typed identifier; a silent
        # redirect is recorded as STORAGE_MOVED.
        if raw is None:
            return None  # 304 Not Modified — content unchanged
    except urllib.error.HTTPError as e:
        code_map = {404: _Err.APP_UNLISTED, 410: _Err.APP_UNLISTED,
                    429: _Err.RATE_LIMITED}
        raise CheckerError(code_map.get(e.code, _Err.UNKNOWN),
                           f"HTTP {e.code}: {api_url}")
    except urllib.error.URLError as e:
        if "timed out" in str(e).lower():
            raise CheckerError(_Err.TIMEOUT, f"Timeout: {api_url}")
        raise CheckerError(_Err.UNKNOWN, f"URL error: {e}")

    if not raw or not raw.strip():
        raise CheckerError(_Err.EMPTY_RESPONSE,
                           f"Empty response from {api_url}")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise CheckerError(_Err.PARSE_ERROR,
                           f"Invalid JSON from {api_url}")

    results = data.get("results", [])
    if not results:
        if bundle_id:
            raise CheckerError(
                _Err.APP_UNLISTED,
                f"App not found on App Store: {bundle_id}",
            )
        raise CheckerError(
            _Err.PARSE_ERROR,
            f"No results in App Store response from {api_url}",
        )

    app = results[0]
    version_value = str(app.get("version", "")).strip()
    if not version_value:
        raise CheckerError(
            _Err.PARSE_ERROR,
            f"No version in App Store result for {bundle_id or api_url}",
        )

    # Immutable identifier: hash of bundle_id + version + trackId
    track_id = app.get("trackId")
    resolved_bundle = app.get("bundleId", bundle_id)
    immutable_id = hashlib.sha256(
        f"ios:{resolved_bundle}:{version_value}:{track_id}".encode()
    ).hexdigest()[:16]

    if last_immutable_id and immutable_id == last_immutable_id:
        return None

    content_hash = hashlib.sha256(raw if isinstance(raw, bytes) else raw.encode()).hexdigest()

    return CheckResult(
        changed=True,
        version_value=version_value,
        immutable_identifier=immutable_id,
        build_number=str(track_id) if track_id else None,
        published_at=app.get("currentVersionReleaseDate"),
        content_hash=content_hash,
        raw_metadata={
            "bundle_id": resolved_bundle,
            "track_name": app.get("trackName"),
            "track_id": track_id,
            "version": version_value,
            "seller_name": app.get("sellerName"),
            "minimum_os_version": app.get("minimumOsVersion"),
            "app_store_url": app.get("trackViewUrl"),
        },
        change_type="release_published",
    )
