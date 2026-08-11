"""
checkers/builtin/api_json.py — JSON API version endpoint checker.

Config shape:
  {"api_url": "https://api.example.com/version"}
  {"api_url": "https://api.example.com/version", "path": "$.version", "headers": {"Accept": "application/json"}}
  {"api_url": "https://api.example.com/openapi.json", "path": "$.info.version"}

Extracts version from JSON response at the given JSONPath.
"""

import hashlib, json, urllib.request, urllib.error

class _Err:
    STORAGE_MOVED   = "STORAGE_MOVED"
    AUTH_REQUIRED   = "AUTH_REQUIRED"
    RATE_LIMITED    = "RATE_LIMITED"
    TIMEOUT         = "TIMEOUT"
    PARSE_ERROR     = "PARSE_ERROR"
    EMPTY_RESPONSE  = "EMPTY_RESPONSE"
    UNKNOWN         = "UNKNOWN"
    BOT_WALL        = "BOT_WALL"


def _check_header_diff(config: dict):
    """Security-headers diff branch.

    Config shape:
      {"api_url": "https://example.com/",
       "check_method": "header_diff",
       "headers": ["Content-Security-Policy",
                   "X-Frame-Options",
                   "Strict-Transport-Security"],
       "method": "GET"}

    `headers` is the list of RESPONSE header names to inspect for this
    source — it is NEVER accepted as request headers. The OSINT invariant
    requires that we issue an honest, minimal request (User-Agent +
    attribution headers via identity.research_headers()) and then read
    only response.headers. We never read the response body, never POST,
    and never carry auth credentials.

    Workflow:
      1. GET api_url via urllib.request.urlopen() with identity.research_headers().
      2. Build a dict {header_name: response.headers.get(name)} for every
         name in config['headers']. Drop entries whose value is None.
      3. Canonicalise the dict and sha256 the canonical JSON.
      4. Return CheckResult mirroring rss.py / js_bundle.py's shape.

    Returns:
      - CheckerError on HTTP/URL errors (404→STORAGE_MOVED, 403→BOT_WALL, …).
      - CheckResult on success.

    Note: this branch bypasses http_cache.fetch() because that helper
    returns ``bytes`` (the body only) — header info is read into the
    http_cache DB row but not returned to the caller. Issuing our own
    urlopen keeps the read-headers-only invariant on a single, narrow
    path; the other 5 source_types continue to consume http_cache's
    bytes-return shape unchanged.
    """
    import urllib.request  # local import keeps the function self-contained

    api_url = config.get("api_url", "")
    headers_list = config.get("headers") or []
    method = (config.get("method") or "GET").upper()

    if not api_url:
        raise CheckerError(_Err.PARSE_ERROR, "Missing 'api_url' in config")
    if not isinstance(headers_list, (list, tuple)) or not headers_list:
        raise CheckerError(
            _Err.PARSE_ERROR,
            "Missing 'headers' list in config (response header names to inspect)",
        )
    if method != "GET":
        # Defence-in-depth: the README/spec only supports GET. A config
        # edit can never turn this into a probing POST.
        raise CheckerError(_Err.PARSE_ERROR, "Only GET is supported for header_diff")

    # Sole source of request headers: identity.research_headers(). Never
    # merged with custom config-supplied headers, never authenticated.
    req_headers = identity.research_headers()
    req = urllib.request.Request(api_url, headers=req_headers, method="GET")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            captured = {}
            for name in headers_list:
                try:
                    value = resp.headers.get(name)
                except Exception:
                    value = None
                if value is not None:
                    captured[name] = value
            if not captured:
                # Server returned no headers for any of the names we asked
                # for. Defend against a degenerate response object.
                raise CheckerError(
                    _Err.EMPTY_RESPONSE,
                    f"No headers present on response from {api_url}",
                )
    except urllib.error.HTTPError as e:
        code_map = {
            404: _Err.STORAGE_MOVED,
            410: _Err.STORAGE_MOVED,
            401: _Err.AUTH_REQUIRED,
            403: _Err.BOT_WALL,
            429: _Err.RATE_LIMITED,
        }
        raise CheckerError(code_map.get(e.code, _Err.UNKNOWN), f"HTTP {e.code}: {api_url}")
    except urllib.error.URLError as e:
        if "timed out" in str(e).lower():
            raise CheckerError(_Err.TIMEOUT, f"Timeout: {api_url}")
        raise CheckerError(_Err.UNKNOWN, f"URL error: {e}")

    canonical = json.dumps(captured, sort_keys=True, separators=(",", ":"))
    immutable_id = hashlib.sha256(canonical.encode()).hexdigest()
    content_hash = hashlib.sha256(canonical.encode()).hexdigest()

    if config.get("_last_immutable_id") == immutable_id:
        return None

    return CheckResult(
        changed=True,
        version_value=canonical,
        immutable_identifier=immutable_id,
        content_hash=content_hash,
        raw_metadata={
            "api_url": api_url,
            "method": method,
            "headers": captured,
            "requested_header_names": list(headers_list),
        },
        change_type="security_header_changed",
    )


def check(config: dict):
    # Dispatch: the 'api' source_type covers two check_methods:
    #   (default) JSONPath extraction into a JSON response body, and
    #   'header_diff' — security-headers / CSP diff on the public response.
    # The runner only injects `config` (parsed from the DB row's `config`
    # column) so the source's check_method must travel in the config dict.
    if (config.get("check_method") or "").lower() == "header_diff":
        return _check_header_diff(config)

    api_url = config.get("api_url", "")
    json_path = config.get("path", "$")
    headers = config.get("headers", {})
    last_immutable_id = config.get("_last_immutable_id")

    if not api_url:
        raise CheckerError(_Err.PARSE_ERROR, "Missing 'api_url' in config")

    req_headers = identity.merge_custom(
        identity.research_headers({"Accept": "application/json"}), headers
    )

    try:
        raw = http_cache.fetch(api_url, req_headers, timeout=30)
        # follow_redirects defaults to False (2026-08-06 audit):
        # API clients are bound to the URL the operator typed. A silent
        # redirect is recorded as a STORAGE_MOVED-style change.
        if raw is None:
            return None  # 304 Not Modified — content unchanged
    except urllib.error.HTTPError as e:
        code_map = {404: _Err.STORAGE_MOVED, 410: _Err.STORAGE_MOVED,
                    401: _Err.AUTH_REQUIRED, 403: _Err.BOT_WALL, 429: _Err.RATE_LIMITED}
        raise CheckerError(code_map.get(e.code, _Err.UNKNOWN), f"HTTP {e.code}: {api_url}")
    except urllib.error.URLError as e:
        if "timed out" in str(e).lower():
            raise CheckerError(_Err.TIMEOUT, f"Timeout: {api_url}")
        raise CheckerError(_Err.UNKNOWN, f"URL error: {e}")

    if not raw or not raw.strip():
        raise CheckerError(_Err.EMPTY_RESPONSE, f"Empty response from {api_url}")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise CheckerError(_Err.PARSE_ERROR, f"Invalid JSON from {api_url}")

    value = _resolve_path(data, json_path)
    if value is _MISSING:
        # Try fallback paths if primary path not found
        fallback_paths = config.get("fallback_paths", [])
        for fb_path in fallback_paths:
            value = _resolve_path(data, fb_path)
            if value is not _MISSING:
                break
    if value is _MISSING:
        raise CheckerError(_Err.PARSE_ERROR, f"JSONPath '{json_path}' not found in response from {api_url}")
    if value is None:
        value = ""  # JSON null → empty string version

    version_value = str(value) if not isinstance(value, str) else value
    content_hash = hashlib.sha256(raw).hexdigest()
    immutable_id = hashlib.sha256(f"{api_url}:{version_value}".encode()).hexdigest()[:16]

    # Change detection
    if last_immutable_id and immutable_id == last_immutable_id:
        return None

    return CheckResult(
        changed=True,
        version_value=version_value,
        immutable_identifier=immutable_id,
        content_hash=content_hash,
        raw_metadata={
            "api_url": api_url,
            "json_path": json_path,
            "response_type": type(data).__name__,
            "response_keys": list(data.keys())[:20] if isinstance(data, dict) else f"[{type(data).__name__}]",
        },
        change_type="api_version_changed",
    )


_MISSING = object()  # sentinel: key/index not found (vs None which means JSON null)


def _resolve_path(data, path: str):
    """Resolve a simple JSONPath-like expression.
    Supports: $.key, $.key.subkey, $.key[0], $.key[0].subkey, $[0]
    Does NOT support full JSONPath filters or wildcards.

    Returns _MISSING when a key/index is absent, None when the value is JSON null,
    or the resolved value (which can be anything including 0, False, "", etc.).
    """
    if path == "$":
        return data

    current = data
    parts = path.lstrip("$").replace("[", ".[").split(".")

    for part in parts:
        part = part.strip()
        if not part:
            continue
        if part.startswith("[") and part.endswith("]"):
            try:
                idx = int(part[1:-1])
            except ValueError:
                raise CheckerError(_Err.PARSE_ERROR,
                                   f"Malformed array index in path '{path}': {part}")
            if not isinstance(current, list) or idx >= len(current):
                return _MISSING
            current = current[idx]
        else:
            if not isinstance(current, dict) or part not in current:
                return _MISSING
            current = current[part]

    return current
