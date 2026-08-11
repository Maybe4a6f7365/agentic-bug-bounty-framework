"""
tests/test_checker_ios_store.py — iOS App Store (iTunes Lookup API) checker unit tests.

Phase 7.  Verifies bundle_id resolution, API URL construction, version extraction,
immutable-id hashing, metadata extraction, HTTP error mapping, network error
classification, change detection, and edge cases — all with FakeHTTPCache.
No real HTTP calls.

Covers ios_store.py check().
"""

import hashlib
import json
import pytest

from tests.support.fakes import load_checker


# ── Canned iTunes Lookup API Responses ─────────────────────────────

ITUNES_RESPONSE = json.dumps({
    "resultCount": 1,
    "results": [{
        "bundleId": "com.example.app",
        "version": "1.2.3",
        "trackId": 123456789,
        "trackName": "Example App",
        "trackViewUrl": "https://apps.apple.com/us/app/example-app/id123456789",
        "sellerName": "Example Corp",
        "minimumOsVersion": "15.0",
        "currentVersionReleaseDate": "2026-07-01T12:00:00Z",
    }],
}).encode()

ITUNES_RESPONSE_V2 = json.dumps({
    "resultCount": 1,
    "results": [{
        "bundleId": "com.example.app",
        "version": "2.0.0",
        "trackId": 123456789,
        "trackName": "Example App",
        "trackViewUrl": "https://apps.apple.com/us/app/example-app/id123456789",
        "sellerName": "Example Corp",
        "minimumOsVersion": "16.0",
        "currentVersionReleaseDate": "2026-08-15T12:00:00Z",
    }],
}).encode()

ITUNES_EMPTY_RESULTS = json.dumps({
    "resultCount": 0,
    "results": [],
}).encode()

ITUNES_MISSING_VERSION = json.dumps({
    "resultCount": 1,
    "results": [{
        "bundleId": "com.example.app",
        "trackId": 123456789,
        "trackName": "Example App",
    }],
}).encode()

ITUNES_NULL_VERSION = json.dumps({
    "resultCount": 1,
    "results": [{
        "bundleId": "com.example.app",
        "version": None,
        "trackId": 123456789,
        "trackName": "Example App",
    }],
}).encode()

ITUNES_NO_TRACKID = json.dumps({
    "resultCount": 1,
    "results": [{
        "bundleId": "com.example.app",
        "version": "1.2.3",
        "trackName": "Example App",
    }],
}).encode()

ITUNES_DIFFERENT_BUNDLE = json.dumps({
    "resultCount": 1,
    "results": [{
        "bundleId": "com.other.bundle",
        "version": "1.2.3",
        "trackId": 987654321,
        "trackName": "Other App",
        "trackViewUrl": "https://apps.apple.com/us/app/other-app/id987654321",
        "sellerName": "Other Corp",
        "minimumOsVersion": "14.0",
        "currentVersionReleaseDate": "2026-06-01T00:00:00Z",
    }],
}).encode()


ITUNES_LOOKUP_URL = "https://itunes.apple.com/lookup?bundleId=com.example.app"
ITUNES_LOOKUP_URL_OTHER = "https://itunes.apple.com/lookup?bundleId=com.other.bundle"


from checkers import runner  # noqa: E402
CheckerError = runner.CheckerError


class TestIosStoreChecker:
    """Canned-HTTP tests for ios_store.check()."""

    # ── Config validation ──────────────────────────────────────────

    def test_missing_api_url_and_bundle_id_raises_parse_error(self, fake_http) -> None:
        """check({}) → CheckerError PARSE_ERROR 'Missing api_url or bundle_id'."""
        mod = load_checker("ios_store", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({})
        assert exc_info.value.code == "PARSE_ERROR"
        assert "Missing" in str(exc_info.value)

    def test_missing_api_url_and_empty_bundle_id_raises_parse_error(self, fake_http) -> None:
        """check({'bundle_id': ''}) → CheckerError PARSE_ERROR."""
        mod = load_checker("ios_store", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"bundle_id": ""})
        assert exc_info.value.code == "PARSE_ERROR"

    def test_api_url_constructed_from_bundle_id(self, fake_http) -> None:
        """bundle_id present but api_url missing → URL constructed from bundle_id."""
        fake_http.set(ITUNES_LOOKUP_URL, ITUNES_RESPONSE)
        mod = load_checker("ios_store", http_cache=fake_http)

        result = mod.check({"bundle_id": "com.example.app"})

        assert result is not None
        assert len(fake_http.requests) == 1
        url, _, _ = fake_http.requests[0]
        assert url == ITUNES_LOOKUP_URL

    def test_explicit_api_url_takes_precedence(self, fake_http) -> None:
        """Explicit api_url is used directly (no construction from bundle_id)."""
        custom_url = "https://custom.lookup.example.com/api"
        fake_http.set(custom_url, ITUNES_RESPONSE)
        mod = load_checker("ios_store", http_cache=fake_http)

        result = mod.check({
            "api_url": custom_url,
            "bundle_id": "com.ignored.bundle",
        })

        assert result is not None
        assert len(fake_http.requests) == 1
        url, _, _ = fake_http.requests[0]
        assert url == custom_url

    # ── Successful lookup ──────────────────────────────────────────

    def test_successful_lookup_extracts_version(self, fake_http) -> None:
        """Successful lookup → version_value extracted from results[0].version."""
        fake_http.set(ITUNES_LOOKUP_URL, ITUNES_RESPONSE)
        mod = load_checker("ios_store", http_cache=fake_http)

        result = mod.check({"bundle_id": "com.example.app"})

        assert result is not None
        assert result.changed
        assert result.version_value == "1.2.3"

    # ── Empty results ──────────────────────────────────────────────

    def test_empty_results_with_bundle_id_raises_app_unlisted(self, fake_http) -> None:
        """resultCount=0 with bundle_id → APP_UNLISTED."""
        fake_http.set(ITUNES_LOOKUP_URL, ITUNES_EMPTY_RESULTS)
        mod = load_checker("ios_store", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"bundle_id": "com.example.app"})
        assert exc_info.value.code == "APP_UNLISTED"
        assert "com.example.app" in str(exc_info.value)

    def test_empty_results_without_bundle_id_raises_parse_error(self, fake_http) -> None:
        """resultCount=0 without bundle_id → PARSE_ERROR."""
        custom_url = "https://custom.api/version"
        fake_http.set(custom_url, ITUNES_EMPTY_RESULTS)
        mod = load_checker("ios_store", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"api_url": custom_url})
        assert exc_info.value.code == "PARSE_ERROR"
        assert "No results" in str(exc_info.value)

    # ── Missing version field ──────────────────────────────────────

    def test_missing_version_field_raises_parse_error(self, fake_http) -> None:
        """results[0] without 'version' key → PARSE_ERROR."""
        fake_http.set(ITUNES_LOOKUP_URL, ITUNES_MISSING_VERSION)
        mod = load_checker("ios_store", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"bundle_id": "com.example.app"})
        assert exc_info.value.code == "PARSE_ERROR"
        assert "No version" in str(exc_info.value)

    def test_null_version_field_returns_none_string(self, fake_http) -> None:
        """results[0].version = null → str(None) → version_value='None'."""
        fake_http.set(ITUNES_LOOKUP_URL, ITUNES_NULL_VERSION)
        mod = load_checker("ios_store", http_cache=fake_http)

        result = mod.check({"bundle_id": "com.example.app"})

        assert result is not None
        assert result.version_value == "None"

    # ── HTTP error codes ───────────────────────────────────────────

    def test_http_404_raises_app_unlisted(self, fake_http) -> None:
        """HTTP 404 → APP_UNLISTED."""
        fake_http.set_404(ITUNES_LOOKUP_URL)
        mod = load_checker("ios_store", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"bundle_id": "com.example.app"})
        assert exc_info.value.code == "APP_UNLISTED"

    def test_http_410_raises_app_unlisted(self, fake_http) -> None:
        """HTTP 410 → APP_UNLISTED."""
        fake_http.set_410(ITUNES_LOOKUP_URL)
        mod = load_checker("ios_store", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"bundle_id": "com.example.app"})
        assert exc_info.value.code == "APP_UNLISTED"

    def test_http_429_raises_rate_limited(self, fake_http) -> None:
        """HTTP 429 → RATE_LIMITED."""
        fake_http.set_429(ITUNES_LOOKUP_URL)
        mod = load_checker("ios_store", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"bundle_id": "com.example.app"})
        assert exc_info.value.code == "RATE_LIMITED"

    def test_http_500_raises_unknown(self, fake_http) -> None:
        """HTTP 500 (unrecognized code) → UNKNOWN."""
        fake_http.errors[ITUNES_LOOKUP_URL] = (500, "Internal Server Error")
        mod = load_checker("ios_store", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"bundle_id": "com.example.app"})
        assert exc_info.value.code == "UNKNOWN"
        assert "500" in str(exc_info.value)

    def test_http_403_raises_unknown(self, fake_http) -> None:
        """HTTP 403 (unrecognized code for ios_store) → UNKNOWN."""
        fake_http.set_403(ITUNES_LOOKUP_URL)
        mod = load_checker("ios_store", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"bundle_id": "com.example.app"})
        assert exc_info.value.code == "UNKNOWN"

    # ── Network errors ─────────────────────────────────────────────

    def test_timeout_raises_timeout(self, fake_http) -> None:
        """URLError('connection timed out') → TIMEOUT."""
        fake_http.set_timeout(ITUNES_LOOKUP_URL, "connection timed out")
        mod = load_checker("ios_store", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"bundle_id": "com.example.app"})
        assert exc_info.value.code == "TIMEOUT"
        assert "Timeout" in str(exc_info.value)

    def test_other_urlerror_raises_unknown(self, fake_http) -> None:
        """URLError('dns error') → UNKNOWN."""
        fake_http.errors[ITUNES_LOOKUP_URL] = "dns error"
        mod = load_checker("ios_store", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"bundle_id": "com.example.app"})
        assert exc_info.value.code == "UNKNOWN"

    # ── Empty response ─────────────────────────────────────────────

    def test_empty_response_raises_empty_response(self, fake_http) -> None:
        """Empty body '' → EMPTY_RESPONSE."""
        fake_http.set(ITUNES_LOOKUP_URL, b"")
        mod = load_checker("ios_store", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"bundle_id": "com.example.app"})
        assert exc_info.value.code == "EMPTY_RESPONSE"

    def test_whitespace_only_response_raises_empty_response(self, fake_http) -> None:
        """Body '   \n  ' → EMPTY_RESPONSE."""
        fake_http.set(ITUNES_LOOKUP_URL, b"   \n  ")
        mod = load_checker("ios_store", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"bundle_id": "com.example.app"})
        assert exc_info.value.code == "EMPTY_RESPONSE"

    # ── Invalid JSON ───────────────────────────────────────────────

    def test_invalid_json_raises_parse_error(self, fake_http) -> None:
        """Body 'not json' → PARSE_ERROR."""
        fake_http.set(ITUNES_LOOKUP_URL, b"not json at all")
        mod = load_checker("ios_store", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"bundle_id": "com.example.app"})
        assert exc_info.value.code == "PARSE_ERROR"
        assert "Invalid JSON" in str(exc_info.value)

    def test_html_body_raises_parse_error(self, fake_http) -> None:
        """Body '<html>...' → PARSE_ERROR (caught by json.JSONDecodeError)."""
        fake_http.set(ITUNES_LOOKUP_URL, b"<html><body>error</body></html>")
        mod = load_checker("ios_store", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"bundle_id": "com.example.app"})
        assert exc_info.value.code == "PARSE_ERROR"

    # ── 304 Not Modified ───────────────────────────────────────────

    def test_304_returns_none(self, fake_http) -> None:
        """http_cache returns None (304) → check() returns None."""
        fake_http.set_304(ITUNES_LOOKUP_URL)
        mod = load_checker("ios_store", http_cache=fake_http)

        result = mod.check({"bundle_id": "com.example.app"})

        assert result is None

    # ── Change detection ───────────────────────────────────────────

    def test_unchanged_same_immutable_id_returns_none(self, fake_http) -> None:
        """_last_immutable_id matches current immutable_id → returns None."""
        fake_http.set(ITUNES_LOOKUP_URL, ITUNES_RESPONSE)
        mod = load_checker("ios_store", http_cache=fake_http)

        # First call to get the immutable_id
        r1 = mod.check({"bundle_id": "com.example.app"})
        assert r1 is not None

        # Second call with same immutable_id
        r2 = mod.check({
            "bundle_id": "com.example.app",
            "_last_immutable_id": r1.immutable_identifier,
        })

        assert r2 is None

    def test_changed_different_immutable_id_returns_result(self, fake_http) -> None:
        """Different _last_immutable_id → CheckResult with changed=True."""
        fake_http.set(ITUNES_LOOKUP_URL, ITUNES_RESPONSE_V2)
        mod = load_checker("ios_store", http_cache=fake_http)

        # Compute the stale immutable_id from the old version
        stale_id = hashlib.sha256(
            b"ios:com.example.app:1.2.3:123456789"
        ).hexdigest()[:16]

        result = mod.check({
            "bundle_id": "com.example.app",
            "_last_immutable_id": stale_id,
        })

        assert result is not None
        assert result.changed
        assert result.version_value == "2.0.0"

    def test_unchanged_without_last_id_returns_result(self, fake_http) -> None:
        """No _last_immutable_id → returns CheckResult (first check baseline)."""
        fake_http.set(ITUNES_LOOKUP_URL, ITUNES_RESPONSE)
        mod = load_checker("ios_store", http_cache=fake_http)

        result = mod.check({"bundle_id": "com.example.app"})

        assert result is not None
        assert result.changed

    # ── Immutable ID format ────────────────────────────────────────

    def test_immutable_id_format(self, fake_http) -> None:
        """immutable_id = sha256('ios:{bundle_id}:{version}:{track_id}')[:16]."""
        fake_http.set(ITUNES_LOOKUP_URL, ITUNES_RESPONSE)
        mod = load_checker("ios_store", http_cache=fake_http)

        result = mod.check({"bundle_id": "com.example.app"})

        expected_id = hashlib.sha256(
            b"ios:com.example.app:1.2.3:123456789"
        ).hexdigest()[:16]

        assert result.immutable_identifier == expected_id
        assert len(result.immutable_identifier) == 16

    def test_immutable_id_without_track_id(self, fake_http) -> None:
        """trackId missing → immutable_id uses 'None' in hash string."""
        fake_http.set(ITUNES_LOOKUP_URL, ITUNES_NO_TRACKID)
        mod = load_checker("ios_store", http_cache=fake_http)

        result = mod.check({"bundle_id": "com.example.app"})

        # track_id is None from response, so f-string uses 'None'
        expected_id = hashlib.sha256(
            b"ios:com.example.app:1.2.3:None"
        ).hexdigest()[:16]

        assert result.immutable_identifier == expected_id

    # ── Metadata fields ────────────────────────────────────────────

    def test_build_number_is_str_track_id(self, fake_http) -> None:
        """build_number = str(track_id)."""
        fake_http.set(ITUNES_LOOKUP_URL, ITUNES_RESPONSE)
        mod = load_checker("ios_store", http_cache=fake_http)

        result = mod.check({"bundle_id": "com.example.app"})

        assert result.build_number == "123456789"
        assert isinstance(result.build_number, str)

    def test_build_number_none_when_track_id_missing(self, fake_http) -> None:
        """trackId missing → build_number = None."""
        fake_http.set(ITUNES_LOOKUP_URL, ITUNES_NO_TRACKID)
        mod = load_checker("ios_store", http_cache=fake_http)

        result = mod.check({"bundle_id": "com.example.app"})

        assert result.build_number is None

    def test_published_at_from_response(self, fake_http) -> None:
        """published_at = currentVersionReleaseDate."""
        fake_http.set(ITUNES_LOOKUP_URL, ITUNES_RESPONSE)
        mod = load_checker("ios_store", http_cache=fake_http)

        result = mod.check({"bundle_id": "com.example.app"})

        assert result.published_at == "2026-07-01T12:00:00Z"

    def test_raw_metadata_contains_all_fields(self, fake_http) -> None:
        """raw_metadata has bundle_id, track_name, track_id, version,
        seller_name, minimum_os_version, app_store_url."""
        fake_http.set(ITUNES_LOOKUP_URL, ITUNES_RESPONSE)
        mod = load_checker("ios_store", http_cache=fake_http)

        result = mod.check({"bundle_id": "com.example.app"})

        meta = result.raw_metadata
        assert meta["bundle_id"] == "com.example.app"
        assert meta["track_name"] == "Example App"
        assert meta["track_id"] == 123456789
        assert meta["version"] == "1.2.3"
        assert meta["seller_name"] == "Example Corp"
        assert meta["minimum_os_version"] == "15.0"
        assert meta["app_store_url"] == "https://apps.apple.com/us/app/example-app/id123456789"

    def test_change_type_is_release_published(self, fake_http) -> None:
        """change_type = 'release_published'."""
        fake_http.set(ITUNES_LOOKUP_URL, ITUNES_RESPONSE)
        mod = load_checker("ios_store", http_cache=fake_http)

        result = mod.check({"bundle_id": "com.example.app"})

        assert result.change_type == "release_published"

    # ── Header handling ────────────────────────────────────────────

    def test_default_headers_set(self, fake_http) -> None:
        """Target-associated iTunes OSINT keeps UA and H1 attribution."""
        fake_http.set(ITUNES_LOOKUP_URL, ITUNES_RESPONSE)
        mod = load_checker("ios_store", http_cache=fake_http)

        mod.check({"bundle_id": "com.example.app"})

        assert len(fake_http.requests) == 1
        _, headers, _ = fake_http.requests[0]
        assert headers["User-Agent"].startswith("version-tracker/")
        assert headers["X-HackerOne-Research"]
        assert headers["X-Bug-Bounty"]
        assert headers.get("Accept") == "application/json"

    # ── Resolved bundle_id from API response ───────────────────────

    def test_resolved_bundle_from_api_overrides_config(self, fake_http) -> None:
        """API response bundleId overrides config bundle_id in raw_metadata
        and immutable_id hash."""
        fake_http.set(ITUNES_LOOKUP_URL_OTHER, ITUNES_DIFFERENT_BUNDLE)
        mod = load_checker("ios_store", http_cache=fake_http)

        result = mod.check({"bundle_id": "com.other.bundle"})

        meta = result.raw_metadata
        # resolved_bundle comes from API response, not config
        assert meta["bundle_id"] == "com.other.bundle"

        # immutable_id uses resolved_bundle
        expected_id = hashlib.sha256(
            b"ios:com.other.bundle:1.2.3:987654321"
        ).hexdigest()[:16]
        assert result.immutable_identifier == expected_id

    def test_content_hash_included(self, fake_http) -> None:
        """result has a content_hash (sha256 of raw response)."""
        fake_http.set(ITUNES_LOOKUP_URL, ITUNES_RESPONSE)
        mod = load_checker("ios_store", http_cache=fake_http)

        result = mod.check({"bundle_id": "com.example.app"})

        expected_hash = hashlib.sha256(ITUNES_RESPONSE).hexdigest()
        assert result.content_hash == expected_hash

    # ── Timeout parameter ──────────────────────────────────────────

    def test_fetch_called_with_timeout_30(self, fake_http) -> None:
        """http_cache.fetch called with timeout=30."""
        fake_http.set(ITUNES_LOOKUP_URL, ITUNES_RESPONSE)
        mod = load_checker("ios_store", http_cache=fake_http)

        mod.check({"bundle_id": "com.example.app"})

        assert len(fake_http.requests) == 1
        _, _, timeout = fake_http.requests[0]
        assert timeout == 30