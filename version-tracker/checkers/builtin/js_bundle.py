"""
checkers/builtin/js_bundle.py — JS bundle integrity diff checker.

Config shape:
  {"page_url": "https://example.com/"}
  {"page_url": "https://example.com/", "script_filter": "static/"}

Workflow:
  1. GET page_url → rendered HTML
  2. Extract every <script src=…> URL from the HTML using stdlib html.parser.
  3. GET each same-origin HTTP(S) script URL exactly once. Cross-origin and
     unsupported-scheme script URLs are recorded but never requested. Redirects
     are recorded but never followed. http_cache returns
     None on 304 — the previous hash is reused (we recompute when fetch
     succeeds; otherwise the URL is dropped from this run's bundle).
  4. Emit a canonical-JSON `{url: sha256(body) | record-only marker}`
     mapping plus its own sha256 hash as the immutable identifier.

OSINT boundary:
  The only URLs fetched are (a) the configured public HTTP(S) page_url and (b)
  same-origin HTTP(S) src values found in <script> tags inside that response.
  Cross-origin and unsupported-scheme values are recorded only. Redirects are
  never followed. No URL is guessed, enumerated, or discovered beyond those
  published values. No authentication or payload submission is performed.
  Every fetch carries identity.research_headers() so the program can attribute
  the traffic.

Returns CheckResult when the canonical URL/hash-or-marker map has changed,
or None when http_cache indicates 304 Not Modified (and the runner passes
the same immutable_identifier as last time).

Mirrors checkers/builtin/rss.py's return shape so the runner treats this
checker indistinguishably.
"""

import hashlib
import ipaddress
import json
import socket
import urllib.error
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse


class _Err:
    STORAGE_MOVED = "STORAGE_MOVED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    RATE_LIMITED = "RATE_LIMITED"
    TIMEOUT = "TIMEOUT"
    PARSE_ERROR = "PARSE_ERROR"
    EMPTY_RESPONSE = "EMPTY_RESPONSE"
    UNKNOWN = "UNKNOWN"
    BOT_WALL = "BOT_WALL"


class _ScriptSrcExtractor(HTMLParser):
    """Collect every literal src= value from <script> start tags.

    Deliberately minimal: no link following, no DOM building, no
    <link rel=…> handling. The OSINT boundary is "URLs the page itself
    publishes in its own HTML" — that's <script src=…> and nothing else.
    """

    def __init__(self):
        super().__init__()
        self.srcs = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "script":
            return
        for key, value in attrs:
            if key.lower() == "src" and value:
                self.srcs.append(value)


def _absolutise(page_url: str, src: str) -> str:
    """Resolve a script src against the page URL.

    urljoin handles absolute URLs (returns src unchanged), root-relative
    paths ("/static/app.js" → "https://example.com/static/app.js"), and
    scheme-relative ("//cdn.example/x.js" → "https://cdn.example/x.js").
    Plain fragments ("#x") and javascript: are passed through; the http
    layer will reject them if they are unworkable.
    """
    return urljoin(page_url, src)


class _BlockedRedirect:
    def __init__(self, location):
        self.location = location or ""


def _origin(url: str):
    """Return a normalized HTTP(S) origin tuple, or None for unsafe URLs."""
    try:
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https") or not parsed.hostname:
            return None
        hostname = parsed.hostname.lower()
        if hostname in ("localhost", "localhost.") or hostname.endswith(".localhost"):
            return None
        try:
            if not ipaddress.ip_address(hostname).is_global:
                return None
        except ValueError:
            # inet_aton also recognizes legacy numeric spellings such as
            # 127.1, 2130706433, and 0x7f000001 that URL parsers may expose as
            # hostnames even though the transport resolves them to loopback.
            try:
                legacy_ip = ipaddress.ip_address(socket.inet_aton(hostname))
                if not legacy_ip.is_global:
                    return None
            except OSError:
                pass  # Ordinary DNS hostname; origin equality still applies.
        port = parsed.port
        if port is None:
            port = 443 if scheme == "https" else 80
        return scheme, hostname, port
    except (TypeError, ValueError):
        return None


def _fetch(url: str, req_headers: dict, timeout: int = 30,
           record_redirect: bool = False):
    """http_cache.fetch with the project's standard error mapping.

    Returns bytes on 200, None on 304, raises CheckerError on HTTP error.
    """
    try:
        raw = http_cache.fetch(
            url,
            req_headers,
            timeout=timeout,
            # 2026-08-06 audit: same-origin + same-script-resource policy.
            # Redirects are recorded in  and surface as
            # redirect:not-followed:<Location> markers; they never silently
            # fetch the destination.
            follow_redirects=False,
        )
        if raw is None:
            return None  # 304 Not Modified
        return raw
    except http_cache.RedirectBlockedError as e:
        if record_redirect:
            return _BlockedRedirect(e.location)
        raise CheckerError(
            _Err.STORAGE_MOVED,
            f"Redirect refused for configured page: {url} -> {e.location or '[missing Location]'}",
        )
    except urllib.error.HTTPError as e:
        code_map = {
            404: _Err.STORAGE_MOVED,
            410: _Err.STORAGE_MOVED,
            401: _Err.AUTH_REQUIRED,
            403: _Err.BOT_WALL,
            429: _Err.RATE_LIMITED,
        }
        raise CheckerError(code_map.get(e.code, _Err.UNKNOWN), f"HTTP {e.code}: {url}")
    except urllib.error.URLError as e:
        if "timed out" in str(e).lower():
            raise CheckerError(_Err.TIMEOUT, f"Timeout: {url}")
        raise CheckerError(_Err.UNKNOWN, f"URL error: {e}")


def check(config: dict):
    page_url = config.get("page_url", "")
    script_filter = config.get("script_filter")
    last_immutable_id = config.get("_last_immutable_id")

    if not page_url:
        raise CheckerError(_Err.PARSE_ERROR, "Missing 'page_url' in config")
    page_origin = _origin(page_url)
    if page_origin is None:
        raise CheckerError(
            _Err.PARSE_ERROR,
            "page_url must be an absolute public HTTP(S) URL",
        )

    req_headers = identity.research_headers()

    # 1. Fetch the page without following redirects. A redirect is an
    # observable page-state change, not permission to request its destination.
    raw = _fetch(page_url, req_headers, record_redirect=True)
    if isinstance(raw, _BlockedRedirect):
        marker = f"redirect:not-followed:{raw.location}"
        canonical = json.dumps(
            {page_url: marker},
            sort_keys=True,
            separators=(",", ":"),
        )
        immutable_id = hashlib.sha256(canonical.encode()).hexdigest()
        if last_immutable_id and immutable_id == last_immutable_id:
            return None
        return CheckResult(
            changed=True,
            version_value=canonical,
            immutable_identifier=immutable_id,
            content_hash=immutable_id,
            raw_metadata={
                "page_url": page_url,
                "page_redirect": raw.location,
                "script_count": 0,
                "scripts": [],
                "fetched_scripts": [],
                "skipped_cross_origin": [],
                "skipped_unsupported_scheme": [],
                "blocked_redirects": {page_url: raw.location},
            },
            change_type="js_bundle_changed",
        )
    if raw is None:
        return None  # 304 — page itself unchanged
    if not raw.strip():
        raise CheckerError(_Err.EMPTY_RESPONSE, f"Empty response from {page_url}")

    # 2. Extract <script src=…> URLs from the rendered HTML.
    parser = _ScriptSrcExtractor()
    try:
        parser.feed(raw.decode("utf-8", "replace"))
    except Exception:
        raise CheckerError(_Err.PARSE_ERROR, f"Could not parse HTML at {page_url}")

    # Absolutise + de-dupe + sort, then apply optional substring filter.
    # Sort order is stable so the immutable_identifier is deterministic.
    srcs = sorted({_absolutise(page_url, s) for s in parser.srcs})
    if script_filter:
        srcs = [s for s in srcs if script_filter in s]

    # 3. Hash each script body. http_cache returning None means a 304
    # for that URL — the body is unchanged, but we have no fresh bytes to
    # hash this run. Per the project's invariant we drop 304-only entries
    # so the bundle diff stays honest (the previous immutable_identifier
    # comparison below still detects "no change at all" runs).
    bundle = {}
    skipped_cross_origin = []
    skipped_unsupported_scheme = []
    blocked_redirects = {}
    fetched_scripts = []
    for script_url in srcs:
        script_origin = _origin(script_url)
        if script_origin is None:
            bundle[script_url] = "unsupported-scheme:not-fetched"
            skipped_unsupported_scheme.append(script_url)
            continue
        if script_origin != page_origin:
            bundle[script_url] = "cross-origin:not-fetched"
            skipped_cross_origin.append(script_url)
            continue

        body = _fetch(script_url, req_headers, record_redirect=True)
        if isinstance(body, _BlockedRedirect):
            blocked_redirects[script_url] = body.location
            bundle[script_url] = f"redirect:not-followed:{body.location}"
            continue
        if body is None:
            continue
        digest = hashlib.sha256(body).hexdigest()
        bundle[script_url] = digest
        fetched_scripts.append(script_url)

    canonical = json.dumps(bundle, sort_keys=True, separators=(",", ":"))
    immutable_id = hashlib.sha256(canonical.encode()).hexdigest()
    content_hash = hashlib.sha256(canonical.encode()).hexdigest()

    # Change detection — same shape as rss.py.
    if last_immutable_id and immutable_id == last_immutable_id:
        return None

    return CheckResult(
        changed=True,
        version_value=canonical,
        immutable_identifier=immutable_id,
        content_hash=content_hash,
        raw_metadata={
            "page_url": page_url,
            "script_count": len(bundle),
            "scripts": sorted(bundle.keys()),
            "fetched_scripts": fetched_scripts,
            "skipped_cross_origin": skipped_cross_origin,
            "skipped_unsupported_scheme": skipped_unsupported_scheme,
            "blocked_redirects": blocked_redirects,
        },
        change_type="js_bundle_changed",
    )
