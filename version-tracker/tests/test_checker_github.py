"""
tests/test_checker_github.py — GitHub release and commit checker unit tests.

Phase 4.  Verifies tag extraction, release extraction, commit detection,
token injection, error branches, field navigation, and edge cases —
all with FakeHTTPCache.  No real GitHub API calls.

Covers TEST_PLAN.md §2.1 (23 tests).
"""

import hashlib
import json

import pytest

from tests.support.fakes import load_checker


# ── Canned GitHub API Responses ──────────────────────────────────────

GITHUB_RELEASE_LATEST = json.dumps({
    "id": 123456789,
    "node_id": "RE_kwDO123456",
    "tag_name": "v3.2.1",
    "target_commitish": "main",
    "name": "Release v3.2.1",
    "draft": False,
    "prerelease": False,
    "created_at": "2026-07-01T12:00:00Z",
    "published_at": "2026-07-01T12:30:00Z",
    "body": "Bug fixes and performance improvements.",
    "html_url": "https://github.com/Shopify/cli/releases/tag/v3.2.1",
}).encode()

GITHUB_RELEASE_LATEST_V2 = json.dumps({
    "id": 123456790,
    "node_id": "RE_kwDO123457",
    "tag_name": "v3.3.0",
    "target_commitish": "main",
    "name": "Release v3.3.0",
    "draft": False,
    "prerelease": False,
    "created_at": "2026-07-15T12:00:00Z",
    "published_at": "2026-07-15T12:30:00Z",
    "body": "New features.",
    "html_url": "https://github.com/Shopify/cli/releases/tag/v3.3.0",
}).encode()

GITHUB_TAGS = json.dumps([
    {
        "name": "v3.2.1",
        "zipball_url": "https://api.github.com/repos/Shopify/cli/zipball/v3.2.1",
        "tarball_url": "https://api.github.com/repos/Shopify/cli/tarball/v3.2.1",
        "commit": {
            "sha": "abc123def456abc123def456abc123def456abc1",
            "url": "https://api.github.com/repos/Shopify/cli/commits/abc123def456abc123def456abc123def456abc1",
        },
        "node_id": "MDM6VGFnMTIz",
    },
    {
        "name": "v3.2.0",
        "zipball_url": "https://api.github.com/repos/Shopify/cli/zipball/v3.2.0",
        "tarball_url": "https://api.github.com/repos/Shopify/cli/tarball/v3.2.0",
        "commit": {
            "sha": "def456abc123def456abc123def456abc123def4",
            "url": "https://api.github.com/repos/Shopify/cli/commits/def456abc123def456abc123def456abc123def4",
        },
        "node_id": "MDM6VGFnMTIy",
    },
]).encode()

GITHUB_COMMIT = json.dumps({
    "sha": "abc123def456abc123def456abc123def456abc1",
    "node_id": "C_kwDO123456",
    "commit": {
        "author": {
            "name": "Test User",
            "email": "test@example.com",
            "date": "2026-07-01T12:00:00Z",
        },
        "committer": {
            "name": "Test User",
            "email": "test@example.com",
            "date": "2026-07-01T12:00:00Z",
        },
        "message": "Fix critical bug in parser",
        "url": "https://api.github.com/repos/Shopify/cli/commits/abc123def456abc123def456abc123def456abc1",
    },
    "html_url": "https://github.com/Shopify/cli/commit/abc123def456abc123def456abc123def456abc1",
}).encode()

GITHUB_RELEASE_NO_TAG = json.dumps({
    "id": 999,
    "node_id": "RE_kwDO999999",
    "tag_name": None,
    "name": "Draft Release",
    "published_at": "2026-07-01T12:00:00Z",
}).encode()


# ── Module-level imports (replaces setUpClass) ────────────────────

from checkers import runner  # noqa: E402
CheckerError = runner.CheckerError


class TestGithubChecker:
    """Canned-HTTP tests for github.check()."""

    # ── Parse / config errors ────────────────────────────────────

    def test_missing_repo_raises_parse_error(self, fake_http) -> None:
        """check({}) → CheckerError PARSE_ERROR 'Missing repo'."""
        mod = load_checker("github", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({})
        assert exc_info.value.code == "PARSE_ERROR"
        assert "Missing 'repo'" in str(exc_info.value)

    # ── Defaults ─────────────────────────────────────────────────

    def test_defaults_endpoint_and_field(self, fake_http) -> None:
        """{'repo':'a/b'} → fetched URL is releases/latest; field='tag_name'."""
        fake_http.set(
            "https://api.github.com/repos/Shopify/cli/releases/latest",
            GITHUB_RELEASE_LATEST,
        )
        mod = load_checker("github", http_cache=fake_http)

        result = mod.check({"repo": "Shopify/cli"})

        assert result is not None
        assert result.version_value == "v3.2.1"
        assert len(fake_http.requests) == 1
        url, headers, _ = fake_http.requests[0]
        assert url == "https://api.github.com/repos/Shopify/cli/releases/latest"
        assert headers.get("Accept") == "application/vnd.github+json"
        assert headers["User-Agent"].startswith("version-tracker/")
        # Target-associated OSINT remains attributable even via GitHub's API.
        assert headers["X-HackerOne-Research"]
        assert headers["X-Bug-Bounty"]

    # ── Release path ─────────────────────────────────────────────

    def test_release_uses_node_id_as_immutable_id(self, fake_http) -> None:
        """Release endpoint → immutable_identifier=node_id, release_id=id,
        published_at=published_at, change_type=release_published."""
        fake_http.set(
            "https://api.github.com/repos/Shopify/cli/releases/latest",
            GITHUB_RELEASE_LATEST,
        )
        mod = load_checker("github", http_cache=fake_http)

        result = mod.check({"repo": "Shopify/cli"})

        assert result is not None
        assert result.changed
        assert result.version_value == "v3.2.1"
        assert result.immutable_identifier == "RE_kwDO123456"
        assert result.release_id == 123456789
        assert result.published_at == "2026-07-01T12:30:00Z"
        assert result.change_type == "release_published"

    def test_release_change_detected(self, fake_http) -> None:
        """Different node_id → CheckResult (not None)."""
        fake_http.set(
            "https://api.github.com/repos/Shopify/cli/releases/latest",
            GITHUB_RELEASE_LATEST_V2,
        )
        mod = load_checker("github", http_cache=fake_http)

        result = mod.check({
            "repo": "Shopify/cli",
            "_last_immutable_id": "RE_kwDO123456",  # stale
        })

        assert result is not None
        assert result.version_value == "v3.3.0"

    # ── Commits path ─────────────────────────────────────────────

    def test_commits_endpoint_uses_sha(self, fake_http) -> None:
        """api_endpoint='/commits/main' → immutable_identifier=sha,
        change_type=commit_advanced, commit_hash set."""
        fake_http.set(
            "https://api.github.com/repos/Shopify/cli/commits/main",
            GITHUB_COMMIT,
        )
        mod = load_checker("github", http_cache=fake_http)

        result = mod.check({
            "repo": "Shopify/cli",
            "api_endpoint": "/commits/main",
            "field": "sha",
        })

        assert result is not None
        assert result.immutable_identifier == "abc123def456abc123def456abc123def456abc1"
        assert result.change_type == "commit_advanced"
        assert result.commit_hash == "abc123def456abc123def456abc123def456abc1"

    def test_endpoint_ending_in_commits_uses_sha(self, fake_http) -> None:
        """api_endpoint='/commits' → endswith('/commits') branch,
        immutable_identifier=sha."""
        fake_http.set(
            "https://api.github.com/repos/Shopify/cli/commits",
            GITHUB_COMMIT,
        )
        mod = load_checker("github", http_cache=fake_http)

        result = mod.check({
            "repo": "Shopify/cli",
            "api_endpoint": "/commits",
            "field": "sha",
        })

        assert result is not None
        assert result.immutable_identifier == "abc123def456abc123def456abc123def456abc1"

    # ── Tags array path ──────────────────────────────────────────

    def test_tags_array_field_index(self, fake_http) -> None:
        """field='[0].name' on tags array → version_value=first tag name,
        immutable_id=sha256 of version, release_id=None, published_at=None."""
        repo = "Shopify/cli"
        fake_http.set(
            f"https://api.github.com/repos/{repo}/tags",
            GITHUB_TAGS,
        )
        mod = load_checker("github", http_cache=fake_http)

        result = mod.check({
            "repo": repo,
            "api_endpoint": "/tags",
            "field": "[0].name",
        })

        assert result is not None
        assert result.version_value == "v3.2.1"
        # data is a list, so immutable_id = sha256(version)[:16]
        expected_id = hashlib.sha256("v3.2.1".encode()).hexdigest()[:16]
        assert result.immutable_identifier == expected_id
        assert result.release_id is None
        assert result.published_at is None
        # metadata records it's an array
        assert result.raw_metadata["response_keys"] == "[array]"

    # ── Dotted field path ────────────────────────────────────────

    def test_dotted_field_path(self, fake_http) -> None:
        """field='commit.sha' → navigates nested dict."""
        fake_http.set(
            "https://api.github.com/repos/Shopify/cli/releases/latest",
            GITHUB_RELEASE_LATEST,
        )
        mod = load_checker("github", http_cache=fake_http)

        result = mod.check({
            "repo": "Shopify/cli",
            "field": "target_commitish",
        })

        assert result is not None
        assert result.version_value == "main"

    # ── No-change detection ──────────────────────────────────────

    def test_unchanged_returns_none(self, fake_http) -> None:
        """_last_immutable_id == node_id → returns None."""
        fake_http.set(
            "https://api.github.com/repos/Shopify/cli/releases/latest",
            GITHUB_RELEASE_LATEST,
        )
        mod = load_checker("github", http_cache=fake_http)

        result = mod.check({
            "repo": "Shopify/cli",
            "_last_immutable_id": "RE_kwDO123456",
        })

        assert result is None

    def test_changed_returns_result(self, fake_http) -> None:
        """Different _last_immutable_id → CheckResult.changed is True."""
        fake_http.set(
            "https://api.github.com/repos/Shopify/cli/releases/latest",
            GITHUB_RELEASE_LATEST,
        )
        mod = load_checker("github", http_cache=fake_http)

        result = mod.check({
            "repo": "Shopify/cli",
            "_last_immutable_id": "OLD_STALE_ID",
        })

        assert result is not None
        assert result.changed

    # ── 304 ──────────────────────────────────────────────────────

    def test_304_returns_none(self, fake_http) -> None:
        """http_cache returns None (304) → check() returns None,
        even without _last_immutable_id."""
        fake_http.set_304(
            "https://api.github.com/repos/Shopify/cli/releases/latest",
        )
        mod = load_checker("github", http_cache=fake_http)

        result = mod.check({"repo": "Shopify/cli"})

        assert result is None

    # ── HTTP error codes ─────────────────────────────────────────

    def test_http_404_storage_moved(self, fake_http) -> None:
        fake_http.set_404(
            "https://api.github.com/repos/Shopify/cli/releases/latest",
        )
        mod = load_checker("github", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"repo": "Shopify/cli"})
        assert "STORAGE_MOVED" in str(exc_info.value)

    def test_http_401_auth_required(self, fake_http) -> None:
        """HTTP 401 → AUTH_REQUIRED."""
        url = "https://api.github.com/repos/Shopify/cli/releases/latest"
        fake_http.errors[url] = (401, "Unauthorized")
        mod = load_checker("github", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"repo": "Shopify/cli"})
        assert "AUTH_REQUIRED" in str(exc_info.value)

    def test_http_403_auth_required(self, fake_http) -> None:
        fake_http.set_403(
            "https://api.github.com/repos/Shopify/cli/releases/latest",
        )
        mod = load_checker("github", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"repo": "Shopify/cli"})
        assert "AUTH_REQUIRED" in str(exc_info.value)

    def test_http_429_rate_limited(self, fake_http) -> None:
        fake_http.set_429(
            "https://api.github.com/repos/Shopify/cli/releases/latest",
        )
        mod = load_checker("github", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"repo": "Shopify/cli"})
        assert "RATE_LIMITED" in str(exc_info.value)

    def test_http_500_unknown(self, fake_http) -> None:
        """HTTP 500 → UNKNOWN (not a recognized code in the 4-check block)."""
        url = "https://api.github.com/repos/Shopify/cli/releases/latest"
        fake_http.errors[url] = (500, "Internal Server Error")
        mod = load_checker("github", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"repo": "Shopify/cli"})
        assert "UNKNOWN" in str(exc_info.value)
        assert "500" in str(exc_info.value)

    # ── Network errors ───────────────────────────────────────────

    def test_urlerror_timed_out_maps_timeout(self, fake_http) -> None:
        """URLError('connection timed out') → TIMEOUT."""
        url = "https://api.github.com/repos/Shopify/cli/releases/latest"
        fake_http.errors[url] = "connection timed out"
        mod = load_checker("github", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"repo": "Shopify/cli"})
        assert "TIMEOUT" in str(exc_info.value)

    def test_urlerror_other_unknown(self, fake_http) -> None:
        """URLError('dns error') → UNKNOWN (not 'timed out')."""
        url = "https://api.github.com/repos/Shopify/cli/releases/latest"
        fake_http.errors[url] = "dns error"
        mod = load_checker("github", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"repo": "Shopify/cli"})
        assert "UNKNOWN" in str(exc_info.value)

    # ── Field parsing edge cases ─────────────────────────────────

    def test_missing_field_parse_error(self, fake_http) -> None:
        """field='nope' → PARSE_ERROR with field name in message."""
        fake_http.set(
            "https://api.github.com/repos/Shopify/cli/releases/latest",
            GITHUB_RELEASE_LATEST,
        )
        mod = load_checker("github", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({
                "repo": "Shopify/cli",
                "field": "nonexistent_field",
            })
        assert "PARSE_ERROR" in str(exc_info.value)
        assert "nonexistent_field" in str(exc_info.value)

    def test_field_resolving_to_json_null_parse_error(self, fake_http) -> None:
        """{'tag_name': None} — null is valid JSON, not a missing key.
        [FIXED #19] Null values now resolve to empty string, not PARSE_ERROR."""
        fake_http.set(
            "https://api.github.com/repos/Shopify/cli/releases/latest",
            GITHUB_RELEASE_NO_TAG,
        )
        mod = load_checker("github", http_cache=fake_http)

        # Null tag_name — now treated as empty version, returns CheckResult
        result = mod.check({"repo": "Shopify/cli"})
        assert result is not None
        assert result.version_value == ""
        assert result.immutable_identifier == "RE_kwDO999999"

    def test_malformed_array_index_escapes_as_valueerror(self, fake_http) -> None:
        """field='[abc].name' — malformed array index caught as CheckerError.
        [FIXED #21] ValueError now caught and re-raised as CheckerError(PARSE_ERROR)."""
        fake_http.set(
            "https://api.github.com/repos/Shopify/cli/tags",
            GITHUB_TAGS,
        )
        mod = load_checker("github", http_cache=fake_http)

        # Now caught as CheckerError, not raw ValueError
        with pytest.raises(CheckerError) as exc_info:
            mod.check({
                "repo": "Shopify/cli",
                "api_endpoint": "/tags",
                "field": "[abc].name",
            })
        assert "PARSE_ERROR" in str(exc_info.value)
        assert "Malformed array index" in str(exc_info.value)

    def test_invalid_json_body_escapes_as_jsondecodeerror(self, fake_http) -> None:
        """body b'<html>...' → caught as CheckerError(PARSE_ERROR).
        [FIXED #22] json.JSONDecodeError now caught, matching api_json.py pattern."""
        fake_http.set(
            "https://api.github.com/repos/Shopify/cli/releases/latest",
            b"<html>rate limited by Cloudflare</html>",
        )
        mod = load_checker("github", http_cache=fake_http)

        # Now caught as CheckerError(PARSE_ERROR), not raw JSONDecodeError
        with pytest.raises(CheckerError) as exc_info:
            mod.check({"repo": "Shopify/cli"})
        assert "PARSE_ERROR" in str(exc_info.value)
        assert "Invalid JSON" in str(exc_info.value)

    # ── Token handling ───────────────────────────────────────────

    def test_token_sets_authorization_header(self, fake_http, monkeypatch) -> None:
        """GITHUB_TOKEN in env → Authorization: Bearer *** set."""
        monkeypatch.setenv("GITHUB_TOKEN", "\u00abredacted:ghp_\u2026\u00bb")
        fake_http.set(
            "https://api.github.com/repos/Shopify/cli/releases/latest",
            GITHUB_RELEASE_LATEST,
        )
        mod = load_checker("github", http_cache=fake_http)

        mod.check({"repo": "Shopify/cli"})

        assert len(fake_http.requests) == 1
        _, headers, _ = fake_http.requests[0]
        assert headers.get("Authorization") == "Bearer \u00abredacted:ghp_\u2026\u00bb"

    def test_no_token_omits_authorization_header(self, fake_http) -> None:
        """No GITHUB_TOKEN → Authorization absent, Accept + User-Agent set."""
        # GITHUB_TOKEN is already stripped by tests/__init__.py
        fake_http.set(
            "https://api.github.com/repos/Shopify/cli/releases/latest",
            GITHUB_RELEASE_LATEST,
        )
        mod = load_checker("github", http_cache=fake_http)

        mod.check({"repo": "Shopify/cli"})

        assert len(fake_http.requests) == 1
        _, headers, _ = fake_http.requests[0]
        assert "Authorization" not in headers
        assert headers.get("Accept") == "application/vnd.github+json"
        assert headers["User-Agent"].startswith("version-tracker/")
        # Target-associated OSINT remains attributable even via GitHub's API.
        assert headers["X-HackerOne-Research"]
        assert headers["X-Bug-Bounty"]

    # ── Content hash ─────────────────────────────────────────────

    def test_content_hash_is_sha256_of_raw_bytes(self, fake_http) -> None:
        """content_hash == sha256(raw body bytes).hexdigest()."""
        fake_http.set(
            "https://api.github.com/repos/Shopify/cli/releases/latest",
            GITHUB_RELEASE_LATEST,
        )
        mod = load_checker("github", http_cache=fake_http)

        result = mod.check({"repo": "Shopify/cli"})

        expected = hashlib.sha256(GITHUB_RELEASE_LATEST).hexdigest()
        assert result.content_hash == expected
