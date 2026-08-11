"""
tests/test_checker_api_json.py — JSON API endpoint checker unit tests.

Phase 5.  Verifies version extraction from JSON endpoints, JSONPath
resolution, HTTP error mapping, network error classification, change
detection, content hashing, and edge cases — all against FakeHTTPCache.
No real HTTP calls.

Covers api_json.py check() and _resolve_path().
"""

import pytest
import hashlib
import json

from tests.support.fakes import load_checker, FakeHTTPCache


# ── Canned API JSON Responses ──────────────────────────────────────

API_SIMPLE_JSON = b"""{"version": "3.2.1", "build": "20260701", "name": "my-api"}"""

API_SIMPLE_JSON_V2 = b"""{"version": "3.3.0", "build": "20260715", "name": "my-api"}"""

API_NESTED_JSON = b"""{
"info": {"version": "2.5.0", "release_date": "2026-06-01"},
"status": "ok"
}"""

API_ARRAY_JSON = b"""[
{"version": "1.0.0", "name": "old"},
{"version": "2.0.0", "name": "latest"}
]"""

API_NESTED_ARRAY_JSON = b"""{
"tags": [
    {"name": "v3.2.1", "sha": "abc123"},
    {"name": "v3.2.0", "sha": "def456"}
]
}"""

API_NUMERIC_VERSION = b"""{"version": 789}"""

API_NULL_FIELD = b"""{"version": null, "status": "ok"}"""

API_EMPTY_OBJECT = b"""{}"""

API_BAD_JSON = b"""not json at all"""

API_HTML_BODY = b"""<html><body>Cloudflare rate limit</body></html>"""


from checkers import runner  # noqa: E402
CheckerError = runner.CheckerError


class TestApiJsonChecker:
    """Canned-HTTP tests for api_json.check()."""

    # ── Config validation ────────────────────────────────────────

    def test_missing_api_url_raises_parse_error(self, fake_http) -> None:
        """check({}) → CheckerError PARSE_ERROR 'Missing api_url'."""
        mod = load_checker("api", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({})
        assert exc_info.value.code == "PARSE_ERROR"
        assert "Missing 'api_url'" in str(exc_info.value)

    def test_missing_api_url_empty_string(self, fake_http) -> None:
        """check({'api_url':''}) → PARSE_ERROR (falsy api_url)."""
        mod = load_checker("api", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"api_url": ""})
        assert exc_info.value.code == "PARSE_ERROR"

    # ── Default path ─────────────────────────────────────────────

    def test_default_path_is_root(self, fake_http) -> None:
        """No 'path' in config → defaults to '$', returns root value."""
        fake_http.set("https://api.example.com/version", API_SIMPLE_JSON)
        mod = load_checker("api", http_cache=fake_http)

        result = mod.check({"api_url": "https://api.example.com/version"})

        assert result is not None
        # Root is a dict, so version_value = str(dict)
        assert "version" in result.version_value
        assert "build" in result.version_value

    # ── Basic path resolution ────────────────────────────────────

    def test_dotted_path_extracts_field(self, fake_http) -> None:
        """path='$.version' → version_value='3.2.1'."""
        fake_http.set("https://api.example.com/version", API_SIMPLE_JSON)
        mod = load_checker("api", http_cache=fake_http)

        result = mod.check({
            "api_url": "https://api.example.com/version",
            "path": "$.version",
        })

        assert result is not None
        assert result.version_value == "3.2.1"

    def test_nested_path_extracts_deep_field(self, fake_http) -> None:
        """path='$.info.version' → version_value='2.5.0'."""
        fake_http.set("https://api.example.com/openapi", API_NESTED_JSON)
        mod = load_checker("api", http_cache=fake_http)

        result = mod.check({
            "api_url": "https://api.example.com/openapi",
            "path": "$.info.version",
        })

        assert result is not None
        assert result.version_value == "2.5.0"

    # ── Array path resolution ────────────────────────────────────

    def test_array_index_path(self, fake_http) -> None:
        """path='$[1].version' → version_value='2.0.0'."""
        fake_http.set("https://api.example.com/releases", API_ARRAY_JSON)
        mod = load_checker("api", http_cache=fake_http)

        result = mod.check({
            "api_url": "https://api.example.com/releases",
            "path": "$[1].version",
        })

        assert result is not None
        assert result.version_value == "2.0.0"

    def test_array_index_first_element(self, fake_http) -> None:
        """path='$[0].version' → version_value='1.0.0'."""
        fake_http.set("https://api.example.com/releases", API_ARRAY_JSON)
        mod = load_checker("api", http_cache=fake_http)

        result = mod.check({
            "api_url": "https://api.example.com/releases",
            "path": "$[0].version",
        })

        assert result is not None
        assert result.version_value == "1.0.0"

    def test_nested_array_path(self, fake_http) -> None:
        """path='$.tags[0].name' → version_value='v3.2.1'."""
        fake_http.set("https://api.example.com/tags", API_NESTED_ARRAY_JSON)
        mod = load_checker("api", http_cache=fake_http)

        result = mod.check({
            "api_url": "https://api.example.com/tags",
            "path": "$.tags[0].name",
        })

        assert result is not None
        assert result.version_value == "v3.2.1"

    # ── Numeric version coercion ─────────────────────────────────

    def test_numeric_version_converted_to_string(self, fake_http) -> None:
        """version=789 (int) → version_value='789'."""
        fake_http.set("https://api.example.com/version", API_NUMERIC_VERSION)
        mod = load_checker("api", http_cache=fake_http)

        result = mod.check({
            "api_url": "https://api.example.com/version",
            "path": "$.version",
        })

        assert result is not None
        assert result.version_value == "789"
        assert isinstance(result.version_value, str)

    # ── Change detection ─────────────────────────────────────────

    def test_unchanged_returns_none(self, fake_http) -> None:
        """_last_immutable_id matches → check() returns None."""
        fake_http.set("https://api.example.com/version", API_SIMPLE_JSON)
        mod = load_checker("api", http_cache=fake_http)

        # First call to learn the immutable_id
        r1 = mod.check({
            "api_url": "https://api.example.com/version",
            "path": "$.version",
        })
        assert r1 is not None

        # Second call with same immutable_id
        r2 = mod.check({
            "api_url": "https://api.example.com/version",
            "path": "$.version",
            "_last_immutable_id": r1.immutable_identifier,
        })

        assert r2 is None

    def test_changed_returns_result(self, fake_http) -> None:
        """Different _last_immutable_id → CheckResult with changed=True."""
        fake_http.set("https://api.example.com/version", API_SIMPLE_JSON)
        mod = load_checker("api", http_cache=fake_http)

        result = mod.check({
            "api_url": "https://api.example.com/version",
            "path": "$.version",
            "_last_immutable_id": "OLD_STALE_ID",
        })

        assert result is not None
        assert result.changed

    def test_version_change_detected(self, fake_http) -> None:
        """Different version → different immutable_id → CheckResult."""
        fake_http.set("https://api.example.com/version", API_SIMPLE_JSON_V2)
        mod = load_checker("api", http_cache=fake_http)

        # First call with stale id from old version
        stale_id = hashlib.sha256(
            "https://api.example.com/version:3.2.1".encode()
        ).hexdigest()[:16]

        result = mod.check({
            "api_url": "https://api.example.com/version",
            "path": "$.version",
            "_last_immutable_id": stale_id,
        })

        assert result is not None
        assert result.version_value == "3.3.0"
        assert result.immutable_identifier != stale_id

    # ── 304 Not Modified ─────────────────────────────────────────

    def test_304_returns_none(self, fake_http) -> None:
        """http_cache returns None (304) → check() returns None."""
        fake_http.set_304("https://api.example.com/version")
        mod = load_checker("api", http_cache=fake_http)

        result = mod.check({"api_url": "https://api.example.com/version"})

        assert result is None

    # ── HTTP error codes ─────────────────────────────────────────

    def test_http_404_storage_moved(self, fake_http) -> None:
        """HTTP 404 → STORAGE_MOVED."""
        fake_http.set_404("https://api.example.com/version")
        mod = load_checker("api", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"api_url": "https://api.example.com/version"})
        assert "STORAGE_MOVED" in str(exc_info.value)

    def test_http_410_storage_moved(self, fake_http) -> None:
        """HTTP 410 → STORAGE_MOVED."""
        fake_http.set_410("https://api.example.com/version")
        mod = load_checker("api", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"api_url": "https://api.example.com/version"})
        assert "STORAGE_MOVED" in str(exc_info.value)

    def test_http_401_auth_required(self, fake_http) -> None:
        """HTTP 401 → AUTH_REQUIRED."""
        url = "https://api.example.com/version"
        fake_http.errors[url] = (401, "Unauthorized")
        mod = load_checker("api", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"api_url": "https://api.example.com/version"})
        assert "AUTH_REQUIRED" in str(exc_info.value)

    def test_http_403_classified_as_bot_wall(self, fake_http) -> None:
        """HTTP 403 → BOT_WALL (intentional product decision, 2026-07-27).

        CDN/WAF bot detection (Akamai, Cloudflare, CloudFront) returns 403
        for non-browser requests.  These are NOT auth failures — the site is
        actively blocking the client, not requesting credentials.

        Distinguished from AUTH_REQUIRED so the runner can route it to
        flag_for_review: disable the source and file a research_note for a
        human. The wall is respected, never bypassed.
        """
        fake_http.set_403("https://api.example.com/version")
        mod = load_checker("api", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"api_url": "https://api.example.com/version"})
        assert "BOT_WALL" in str(exc_info.value)

    def test_http_401_still_auth_required(self, fake_http) -> None:
        """HTTP 401 → AUTH_REQUIRED (enum member still reachable).

        Guards against accidental BOT_WALL creep — 401 (genuine
        authentication failure) must NOT be reclassified as BOT_WALL.
        """
        url = "https://api.example.com/version"
        fake_http.errors[url] = (401, "Unauthorized")
        mod = load_checker("api", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"api_url": "https://api.example.com/version"})
        assert "AUTH_REQUIRED" in str(exc_info.value)

    def test_http_429_rate_limited(self, fake_http) -> None:
        """HTTP 429 → RATE_LIMITED."""
        fake_http.set_429("https://api.example.com/version")
        mod = load_checker("api", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"api_url": "https://api.example.com/version"})
        assert "RATE_LIMITED" in str(exc_info.value)

    def test_http_500_unknown(self, fake_http) -> None:
        """HTTP 500 → UNKNOWN."""
        url = "https://api.example.com/version"
        fake_http.errors[url] = (500, "Internal Server Error")
        mod = load_checker("api", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"api_url": "https://api.example.com/version"})
        assert "UNKNOWN" in str(exc_info.value)
        assert "500" in str(exc_info.value)

    # ── Network errors ───────────────────────────────────────────

    def test_urlerror_timed_out_maps_timeout(self, fake_http) -> None:
        """URLError('connection timed out') → TIMEOUT."""
        url = "https://api.example.com/version"
        fake_http.set_timeout(url, "connection timed out")
        mod = load_checker("api", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"api_url": "https://api.example.com/version"})
        assert "TIMEOUT" in str(exc_info.value)

    def test_urlerror_other_unknown(self, fake_http) -> None:
        """URLError('dns error') → UNKNOWN."""
        url = "https://api.example.com/version"
        fake_http.errors[url] = "dns error"
        mod = load_checker("api", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"api_url": "https://api.example.com/version"})
        assert "UNKNOWN" in str(exc_info.value)

    # ── Empty / invalid body ─────────────────────────────────────

    def test_empty_response_body(self, fake_http) -> None:
        """Empty body '' → EMPTY_RESPONSE."""
        fake_http.set("https://api.example.com/version", b"")
        mod = load_checker("api", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"api_url": "https://api.example.com/version"})
        assert exc_info.value.code == "EMPTY_RESPONSE"

    def test_whitespace_only_body(self, fake_http) -> None:
        """Body '   ' → EMPTY_RESPONSE (strip() → '')."""
        fake_http.set("https://api.example.com/version", b"   \n  ")
        mod = load_checker("api", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"api_url": "https://api.example.com/version"})
        assert exc_info.value.code == "EMPTY_RESPONSE"

    def test_invalid_json_parse_error(self, fake_http) -> None:
        """Body 'not json' → PARSE_ERROR."""
        fake_http.set("https://api.example.com/version", API_BAD_JSON)
        mod = load_checker("api", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"api_url": "https://api.example.com/version"})
        assert exc_info.value.code == "PARSE_ERROR"
        assert "Invalid JSON" in str(exc_info.value)

    def test_html_body_parse_error(self, fake_http) -> None:
        """Body '<html>...' → PARSE_ERROR (caught, unlike github.py #22)."""
        fake_http.set("https://api.example.com/version", API_HTML_BODY)
        mod = load_checker("api", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"api_url": "https://api.example.com/version"})
        assert exc_info.value.code == "PARSE_ERROR"

    # ── Path resolution edge cases ───────────────────────────────

    def test_path_not_found_parse_error(self, fake_http) -> None:
        """path='$.nope' on dict without 'nope' → PARSE_ERROR."""
        fake_http.set("https://api.example.com/version", API_SIMPLE_JSON)
        mod = load_checker("api", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({
                "api_url": "https://api.example.com/version",
                "path": "$.nonexistent",
            })
        assert exc_info.value.code == "PARSE_ERROR"
        assert "not found" in str(exc_info.value)

    def test_path_into_non_dict_parse_error(self, fake_http) -> None:
        """path='$.version.broken' — version is string, can't drill further."""
        fake_http.set("https://api.example.com/version", API_SIMPLE_JSON)
        mod = load_checker("api", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({
                "api_url": "https://api.example.com/version",
                "path": "$.version.broken",
            })
        assert exc_info.value.code == "PARSE_ERROR"

    def test_array_index_out_of_bounds_parse_error(self, fake_http) -> None:
        """path='$[99]' on 2-element array → PARSE_ERROR."""
        fake_http.set("https://api.example.com/releases", API_ARRAY_JSON)
        mod = load_checker("api", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({
                "api_url": "https://api.example.com/releases",
                "path": "$[99]",
            })
        assert exc_info.value.code == "PARSE_ERROR"

    def test_null_field_returns_parse_error(self, fake_http) -> None:
        """path='$.version' → null — null is valid JSON, not a missing key.
        [FIXED #23] Null values now resolve to empty string, not PARSE_ERROR."""
        fake_http.set("https://api.example.com/version", API_NULL_FIELD)
        mod = load_checker("api", http_cache=fake_http)

        # Null version → now treated as empty version, returns CheckResult
        result = mod.check({
            "api_url": "https://api.example.com/version",
            "path": "$.version",
        })
        assert result is not None
        assert result.version_value == ""
        assert result.change_type == "api_version_changed"

    def test_malformed_array_index_escapes_as_valueerror(self, fake_http) -> None:
        """path='$[abc].version' — caught as CheckerError(PARSE_ERROR).
        [FIXED #23] ValueError now wrapped and raised as CheckerError."""
        fake_http.set("https://api.example.com/releases", API_ARRAY_JSON)
        mod = load_checker("api", http_cache=fake_http)

        # Now caught as CheckerError, not raw ValueError
        with pytest.raises(CheckerError) as exc_info:
            mod.check({
                "api_url": "https://api.example.com/releases",
                "path": "$[abc].version",
            })
        assert "PARSE_ERROR" in str(exc_info.value)

    def test_array_index_on_non_list_returns_none(self, fake_http) -> None:
        """path='$[0]' on dict → _resolve_path returns None → PARSE_ERROR."""
        fake_http.set("https://api.example.com/version", API_SIMPLE_JSON)
        mod = load_checker("api", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({
                "api_url": "https://api.example.com/version",
                "path": "$[0]",
            })
        assert exc_info.value.code == "PARSE_ERROR"

    # ── Header handling ──────────────────────────────────────────

    def test_default_headers_set(self, fake_http) -> None:
        """Program-owned APIs get researcher-identifying headers."""
        fake_http.set("https://api.example.com/version", API_SIMPLE_JSON)
        mod = load_checker("api", http_cache=fake_http)

        mod.check({"api_url": "https://api.example.com/version"})

        assert len(fake_http.requests) == 1
        _, headers, _ = fake_http.requests[0]
        assert headers["User-Agent"].startswith("version-tracker/")
        assert "Mozilla" not in headers["User-Agent"]
        assert headers["X-HackerOne-Research"]
        assert headers["X-Bug-Bounty"]
        assert headers.get("Accept") == "application/json"

    def test_custom_headers_merged_with_defaults(self, fake_http) -> None:
        """Custom headers override defaults, new keys added."""
        fake_http.set("https://api.example.com/version", API_SIMPLE_JSON)
        mod = load_checker("api", http_cache=fake_http)

        mod.check({
            "api_url": "https://api.example.com/version",
            "headers": {
                "Accept": "application/vnd.api+json",
                "Authorization": "Bearer test-token",
            },
        })

        assert len(fake_http.requests) == 1
        _, headers, _ = fake_http.requests[0]
        # Custom Accept overrides default
        assert headers.get("Accept") == "application/vnd.api+json"
        # Defaults survive — including the identification headers, which a
        # per-source config must not be able to drop.
        assert headers["User-Agent"].startswith("version-tracker/")
        assert headers["X-HackerOne-Research"]
        # Custom headers added
        assert headers.get("Authorization") == "Bearer test-token"

    # ── Content hash ─────────────────────────────────────────────

    def test_content_hash_is_sha256_of_raw_bytes(self, fake_http) -> None:
        """content_hash == sha256(raw_bytes).hexdigest()."""
        fake_http.set("https://api.example.com/version", API_SIMPLE_JSON)
        mod = load_checker("api", http_cache=fake_http)

        result = mod.check({"api_url": "https://api.example.com/version"})

        expected = hashlib.sha256(API_SIMPLE_JSON).hexdigest()
        assert result.content_hash == expected

    # ── Immutable identifier format ──────────────────────────────

    def test_immutable_id_is_sha256_truncated(self, fake_http) -> None:
        """immutable_id = sha256(api_url:version_value)[:16]."""
        fake_http.set("https://api.example.com/version", API_SIMPLE_JSON)
        mod = load_checker("api", http_cache=fake_http)

        result = mod.check({
            "api_url": "https://api.example.com/version",
            "path": "$.version",
        })

        expected = hashlib.sha256(
            "https://api.example.com/version:3.2.1".encode()
        ).hexdigest()[:16]
        assert result.immutable_identifier == expected
        assert len(result.immutable_identifier) == 16

    def test_different_url_different_immutable_id(self, fake_http) -> None:
        """Same version, different url → different immutable_id."""
        fake_http1 = FakeHTTPCache()
        fake_http2 = FakeHTTPCache()
        fake_http1.set("https://api.foo.com/version", API_SIMPLE_JSON)
        fake_http2.set("https://api.bar.com/version", API_SIMPLE_JSON)

        mod1 = load_checker("api", http_cache=fake_http1)
        mod2 = load_checker("api", http_cache=fake_http2)

        r1 = mod1.check({
            "api_url": "https://api.foo.com/version",
            "path": "$.version",
        })
        r2 = mod2.check({
            "api_url": "https://api.bar.com/version",
            "path": "$.version",
        })

        assert r1.version_value == r2.version_value
        assert r1.immutable_identifier != r2.immutable_identifier

    # ── Metadata ─────────────────────────────────────────────────

    def test_metadata_includes_api_url_and_path(self, fake_http) -> None:
        """raw_metadata contains api_url and json_path."""
        fake_http.set("https://api.example.com/status", API_SIMPLE_JSON)
        mod = load_checker("api", http_cache=fake_http)

        result = mod.check({
            "api_url": "https://api.example.com/status",
            "path": "$.build",
        })

        assert result.raw_metadata is not None
        assert result.raw_metadata["api_url"] == "https://api.example.com/status"
        assert result.raw_metadata["json_path"] == "$.build"

    def test_metadata_response_type_is_dict(self, fake_http) -> None:
        """response_type = 'dict' for a JSON object."""
        fake_http.set("https://api.example.com/version", API_SIMPLE_JSON)
        mod = load_checker("api", http_cache=fake_http)

        result = mod.check({"api_url": "https://api.example.com/version"})

        assert result.raw_metadata["response_type"] == "dict"

    def test_metadata_response_type_is_list(self, fake_http) -> None:
        """response_type = 'list' for a JSON array."""
        fake_http.set("https://api.example.com/releases", API_ARRAY_JSON)
        mod = load_checker("api", http_cache=fake_http)

        result = mod.check({
            "api_url": "https://api.example.com/releases",
            "path": "$[0].version",
        })

        assert result.raw_metadata["response_type"] == "list"

    def test_metadata_keys_capped_at_20(self, fake_http) -> None:
        """response_keys lists up to 20 top-level keys for dict responses."""
        # Use the standard canned response (3 keys: version, build, name)
        fake_http.set("https://api.example.com/version", API_SIMPLE_JSON)
        mod = load_checker("api", http_cache=fake_http)

        result = mod.check({"api_url": "https://api.example.com/version"})

        keys = result.raw_metadata["response_keys"]
        assert isinstance(keys, list)
        assert "version" in keys
        assert "build" in keys
        assert "name" in keys

    def test_change_type_api_version_changed(self, fake_http) -> None:
        """change_type = 'api_version_changed'."""
        fake_http.set("https://api.example.com/version", API_SIMPLE_JSON)
        mod = load_checker("api", http_cache=fake_http)

        result = mod.check({
            "api_url": "https://api.example.com/version",
            "path": "$.version",
        })

        assert result.change_type == "api_version_changed"

    # ── Request properties ───────────────────────────────────────

    def test_correct_url_fetched(self, fake_http) -> None:
        """check() fetches the api_url exactly as given."""
        url = "https://status.example.com/api/v3/version.json"
        fake_http.set(url, API_SIMPLE_JSON)
        mod = load_checker("api", http_cache=fake_http)

        mod.check({"api_url": url})

        assert len(fake_http.requests) == 1
        fetched_url, _, _ = fake_http.requests[0]
        assert fetched_url == url

    def test_timeout_30_seconds(self, fake_http) -> None:
        """Timeout passed to http_cache is 30 seconds."""
        fake_http.set("https://api.example.com/version", API_SIMPLE_JSON)
        mod = load_checker("api", http_cache=fake_http)

        mod.check({"api_url": "https://api.example.com/version"})

        _, _, timeout = fake_http.requests[0]
        assert timeout == 30

    # ── GAP: fallback_paths not consumed ─────────────────────────

    def test_fallback_paths_ignored_by_checker(self, fake_http) -> None:
        """config includes 'fallback_paths' — checker now uses them.
        [FIXED #24] Fallback paths are consumed when primary path fails."""
        # Response with no 'version' key — api_version exists instead
        body = b"""{"api_version": "4.0.0", "status": "ok"}"""
        fake_http.set("https://api.example.com/version", body)
        mod = load_checker("api", http_cache=fake_http)

        # Config as enrich.py writes it — fallback paths now work
        result = mod.check({
            "api_url": "https://api.example.com/version",
            "path": "$.version",
            "fallback_paths": [
                "$.api_version", "$.build", "$.release",
            ],
        })
        assert result is not None
        assert result.version_value == "4.0.0"
        # First fallback path ($.api_version) was used


class TestResolvePath:
    """Direct unit tests for _resolve_path()."""

    @staticmethod
    def _mod(fake_http):
        return load_checker("api", http_cache=fake_http)

    def test_dollar_only_returns_root(self, fake_http) -> None:
        mod = self._mod(fake_http)
        data = {"key": "value"}
        assert mod._resolve_path(data, "$") == data

    def test_single_key(self, fake_http) -> None:
        mod = self._mod(fake_http)
        assert mod._resolve_path({"name": "test"}, "$.name") == "test"

    def test_nested_key(self, fake_http) -> None:
        mod = self._mod(fake_http)
        assert mod._resolve_path(
            {"info": {"version": "1.0"}}, "$.info.version",
        ) == "1.0"

    def test_array_index_first(self, fake_http) -> None:
        mod = self._mod(fake_http)
        assert mod._resolve_path(["a", "b"], "$[0]") == "a"

    def test_array_index_second(self, fake_http) -> None:
        mod = self._mod(fake_http)
        assert mod._resolve_path(["a", "b", "c"], "$[1]") == "b"

    def test_array_then_key(self, fake_http) -> None:
        mod = self._mod(fake_http)
        data = {"items": [{"id": 1}, {"id": 2}]}
        assert mod._resolve_path(data, "$.items[0].id") == 1

    def test_array_then_key_second(self, fake_http) -> None:
        mod = self._mod(fake_http)
        data = {"items": [{"id": 1}, {"id": 2}]}
        assert mod._resolve_path(data, "$.items[1].id") == 2

    def test_key_missing_returns_none(self, fake_http) -> None:
        mod = self._mod(fake_http)
        assert mod._resolve_path({"a": 1}, "$.b") is mod._MISSING

    def test_nested_key_missing_returns_none(self, fake_http) -> None:
        mod = self._mod(fake_http)
        assert mod._resolve_path(
            {"info": {"version": "1.0"}}, "$.info.name",
        ) is mod._MISSING

    def test_array_oob_returns_none(self, fake_http) -> None:
        mod = self._mod(fake_http)
        assert mod._resolve_path(["a"], "$[5]") is mod._MISSING

    def test_array_index_on_dict_returns_none(self, fake_http) -> None:
        mod = self._mod(fake_http)
        assert mod._resolve_path({"key": "value"}, "$[0]") is mod._MISSING

    def test_key_on_list_returns_none(self, fake_http) -> None:
        mod = self._mod(fake_http)
        assert mod._resolve_path(["a", "b"], "$.name") is mod._MISSING

    def test_null_value_returned_as_none(self, fake_http) -> None:
        """_resolve_path returns None for a JSON null — indistinguishable
        from missing key. [GAP]"""
        mod = self._mod(fake_http)
        assert mod._resolve_path({"version": None}, "$.version") is None

    def test_empty_array_index_malformed(self, fake_http) -> None:
        """Empty brackets '[]' → caught as CheckerError(PARSE_ERROR).
        [FIXED #23] ValueError now caught in _resolve_path and raised as CheckerError."""
        mod = self._mod(fake_http)
        with pytest.raises(CheckerError) as exc_info:
            mod._resolve_path(["a"], "$[].name")
        assert "PARSE_ERROR" in str(exc_info.value)

    def test_boolean_value_returned(self, fake_http) -> None:
        """Boolean true → Python True."""
        mod = self._mod(fake_http)
        assert mod._resolve_path({"active": True}, "$.active") is True

    def test_zero_is_valid_value(self, fake_http) -> None:
        """0 is truthy in JSON context — should not be treated as None."""
        mod = self._mod(fake_http)
        assert mod._resolve_path({"count": 0}, "$.count") == 0

    def test_false_is_valid_value(self, fake_http) -> None:
        """False is valid — should not be treated as None."""
        mod = self._mod(fake_http)
        assert mod._resolve_path({"enabled": False}, "$.enabled") is False