"""
tests/test_checker_package_registry.py — Package/container registry checker unit tests.

Phase 3.  Verifies PyPI, npm, Docker Hub check paths plus error handling,
all with FakeHTTPCache — no real network calls.

Pins bug #8 (enrich dialect mismatch): registry_url-based auto-derivation
of registry + package from PyPI/npm URLs.
"""

import pytest

from tests.support.fakes import (
    load_checker,
    PYPI_REQUESTS,
    PYPI_REQUESTS_V2,
    NPM_REACT,
    NPM_REACT_V2,
    DOCKER_HUB_NGINX,
    DOCKER_HUB_NGINX_V2,
)

# ── Module-level imports (replaces setUpClass) ────────────────────

from checkers import runner  # noqa: E402
CheckerError = runner.CheckerError


class TestPackageRegistryChecker:
    """Canned-HTTP tests for package_registry.check()."""

    # ── PyPI ──────────────────────────────────────────────────────

    def test_pypi_happy_path(self, fake_http) -> None:
        """check({'registry':'pypi', 'package':'requests'}) →
        CheckResult with version='2.32.5' from canned PyPI JSON."""
        fake_http.set("https://pypi.org/pypi/requests/json", PYPI_REQUESTS)
        mod = load_checker("package_registry", http_cache=fake_http)

        result = mod.check({"registry": "pypi", "package": "requests"})

        assert result is not None
        assert result.changed
        assert result.version_value == "2.32.5"
        assert result.change_type == "release_published"
        assert len(fake_http.requests) == 1
        url, headers, _ = fake_http.requests[0]
        assert "pypi.org" in url
        assert headers.get("Accept") == "application/json"
        assert headers["X-HackerOne-Research"]
        assert headers["X-Bug-Bounty"]

    def test_pypi_version_change(self, fake_http) -> None:
        """A new version → different immutable_id → CheckResult, not None."""
        fake_http.set("https://pypi.org/pypi/requests/json", PYPI_REQUESTS_V2)
        mod = load_checker("package_registry", http_cache=fake_http)

        result = mod.check({
            "registry": "pypi",
            "package": "requests",
            "_last_immutable_id": "deadbeefdeadbeef",  # stale
        })

        assert result is not None
        assert result.version_value == "3.0.0"

    def test_pypi_no_change_same_immutable_id(self, fake_http) -> None:
        """Same version → same immutable_id → check() returns None."""
        fake_http.set("https://pypi.org/pypi/requests/json", PYPI_REQUESTS)
        mod = load_checker("package_registry", http_cache=fake_http)

        # First call: get the immutable_id
        result1 = mod.check({"registry": "pypi", "package": "requests"})
        assert result1 is not None

        # Second call: same response, fresh module, same _last_immutable_id
        mod2 = load_checker("package_registry", http_cache=fake_http)

        result2 = mod2.check({
            "registry": "pypi",
            "package": "requests",
            "_last_immutable_id": result1.immutable_identifier,
        })
        assert result2 is None, "same immutable_id → no change"

    def test_pypi_304_unchanged(self, fake_http) -> None:
        """http_cache returns None (304) → check() returns None."""
        fake_http.set_304("https://pypi.org/pypi/requests/json")
        mod = load_checker("package_registry", http_cache=fake_http)

        result = mod.check({"registry": "pypi", "package": "requests"})
        assert result is None

    # ── npm ───────────────────────────────────────────────────────

    def test_npm_happy_path(self, fake_http) -> None:
        """check({'registry':'npm', 'package':'react'}) →
        CheckResult with version='19.2.0' from canned npm JSON."""
        fake_http.set("https://registry.npmjs.org/react/latest", NPM_REACT)
        mod = load_checker("package_registry", http_cache=fake_http)

        result = mod.check({"registry": "npm", "package": "react"})

        assert result is not None
        assert result.version_value == "19.2.0"
        url, headers, _ = fake_http.requests[0]
        assert "registry.npmjs.org" in url
        assert headers.get("Accept") == "application/json"
        assert headers["X-HackerOne-Research"]
        assert headers["X-Bug-Bounty"]

    def test_npm_version_change(self, fake_http) -> None:
        fake_http.set("https://registry.npmjs.org/react/latest", NPM_REACT_V2)
        mod = load_checker("package_registry", http_cache=fake_http)

        result = mod.check({
            "registry": "npm",
            "package": "react",
            "_last_immutable_id": "stale",
        })

        assert result is not None
        assert result.version_value == "20.0.0"

    # ── Docker Hub ────────────────────────────────────────────────

    def test_docker_hub_happy_path(self, fake_http) -> None:
        """Config with registry_url containing hub.docker.com →
        _check_docker_hub path, parses latest tag name."""
        fake_http.set(
            "https://hub.docker.com/v2/repositories/library/nginx/tags/?page_size=1",
            DOCKER_HUB_NGINX,
        )
        mod = load_checker("package_registry", http_cache=fake_http)

        result = mod.check({
            "registry_url": "https://hub.docker.com/v2/repositories/library/nginx/tags",
            "field": "name",
        })

        assert result is not None
        assert result.version_value == "latest"
        assert result.raw_metadata["registry"] == "docker_hub"
        assert result.raw_metadata["repo"] == "library/nginx"

    def test_docker_hub_version_change(self, fake_http) -> None:
        fake_http.set(
            "https://hub.docker.com/v2/repositories/library/nginx/tags/?page_size=1",
            DOCKER_HUB_NGINX_V2,
        )
        mod = load_checker("package_registry", http_cache=fake_http)

        result = mod.check({
            "registry_url": "https://hub.docker.com/v2/repositories/library/nginx/tags",
            "field": "name",
            "_last_immutable_id": "stale",
        })
        assert result is not None
        assert result.version_value == "1.27"

    # ── Bug #8: registry_url derivation ───────────────────────────

    def test_derive_pypi_from_registry_url(self, fake_http) -> None:
        """[FIXED BUG #8] registry_url='https://pypi.org/pypi/requests/json'
        without registry/package keys → auto-derives pypi + requests."""
        fake_http.set("https://pypi.org/pypi/requests/json", PYPI_REQUESTS)
        mod = load_checker("package_registry", http_cache=fake_http)

        result = mod.check({
            "registry_url": "https://pypi.org/pypi/requests/json",
        })

        assert result is not None
        assert result.version_value == "2.32.5"

    def test_derive_npm_from_registry_url(self, fake_http) -> None:
        """[FIXED BUG #8] registry_url='https://registry.npmjs.org/react/latest'
        without registry/package keys → auto-derives npm + react."""
        fake_http.set("https://registry.npmjs.org/react/latest", NPM_REACT)
        mod = load_checker("package_registry", http_cache=fake_http)

        result = mod.check({
            "registry_url": "https://registry.npmjs.org/react/latest",
        })

        assert result is not None
        assert result.version_value == "19.2.0"

    def test_derive_scoped_npm_from_registry_url(self, fake_http) -> None:
        """Scoped npm package @org/name → correctly extracted."""
        fake_http.set(
            "https://registry.npmjs.org/@angular/core/latest",
            b'{"name":"@angular/core","version":"18.0.0","description":"Angular","dist-tags":{},"versions":{}}',
        )
        mod = load_checker("package_registry", http_cache=fake_http)

        result = mod.check({
            "registry_url": "https://registry.npmjs.org/@angular/core/latest",
        })

        assert result is not None
        assert result.version_value == "18.0.0"

    # ── Error branches ────────────────────────────────────────────

    def test_404_raises_storage_moved(self, fake_http) -> None:
        fake_http.set_404("https://pypi.org/pypi/nonexistent/json")
        mod = load_checker("package_registry", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"registry": "pypi", "package": "nonexistent"})
        assert "STORAGE_MOVED" in str(exc_info.value)

    def test_410_raises_storage_moved(self, fake_http) -> None:
        fake_http.set_410("https://pypi.org/pypi/deleted/json")
        mod = load_checker("package_registry", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"registry": "pypi", "package": "deleted"})
        assert "STORAGE_MOVED" in str(exc_info.value)

    def test_429_raises_rate_limited(self, fake_http) -> None:
        fake_http.set_429("https://pypi.org/pypi/requests/json")
        mod = load_checker("package_registry", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"registry": "pypi", "package": "requests"})
        assert "RATE_LIMITED" in str(exc_info.value)

    def test_403_raises_auth_required(self, fake_http) -> None:
        fake_http.set_403("https://pypi.org/pypi/private/json")
        mod = load_checker("package_registry", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"registry": "pypi", "package": "private"})
        assert "AUTH_REQUIRED" in str(exc_info.value)

    def test_timeout_raises_timeout(self, fake_http) -> None:
        fake_http.set_timeout("https://pypi.org/pypi/requests/json")
        mod = load_checker("package_registry", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"registry": "pypi", "package": "requests"})
        assert "TIMEOUT" in str(exc_info.value)

    def test_missing_package_raises_parse_error(self, fake_http) -> None:
        """No registry, no registry_url, no package → PARSE_ERROR."""
        mod = load_checker("package_registry", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"some_other_key": "value"})
        assert "PARSE_ERROR" in str(exc_info.value)

    def test_unsupported_registry_raises_parse_error(self, fake_http) -> None:
        """Unknown registry name → PARSE_ERROR with supported list."""
        mod = load_checker("package_registry", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"registry": "maven_central", "package": "some-lib"})
        assert "PARSE_ERROR" in str(exc_info.value)
        assert "Unsupported registry" in str(exc_info.value)

    def test_broken_docker_hub_url_raises_parse_error(self, fake_http) -> None:
        """Docker Hub URL without a recognizable repo path → PARSE_ERROR."""
        mod = load_checker("package_registry", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({
                "registry_url": "https://hub.docker.com/some/weird/path",
            })
        assert "PARSE_ERROR" in str(exc_info.value)
        assert "Cannot parse repo path" in str(exc_info.value)

    def test_empty_response_raises_empty_response(self, fake_http) -> None:
        """Empty bytes body → EMPTY_RESPONSE."""
        fake_http.set("https://pypi.org/pypi/empty/json", b"")
        mod = load_checker("package_registry", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"registry": "pypi", "package": "empty"})
        assert "EMPTY_RESPONSE" in str(exc_info.value)

    def test_invalid_json_raises_parse_error(self, fake_http) -> None:
        """Garbage bytes → PARSE_ERROR (JSON decode failure)."""
        fake_http.set("https://pypi.org/pypi/broken/json", b"not json")
        mod = load_checker("package_registry", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"registry": "pypi", "package": "broken"})
        assert "PARSE_ERROR" in str(exc_info.value)

    def test_missing_docker_hub_field(self, fake_http) -> None:
        """Docker Hub response missing the configured field → PARSE_ERROR."""
        fake_http.set(
            "https://hub.docker.com/v2/repositories/lib/nginx/tags/?page_size=1",
            b'{"count":1,"results":[{"name":""}]}',
        )
        mod = load_checker("package_registry", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({
                "registry_url": "https://hub.docker.com/v2/repositories/lib/nginx/tags",
                "field": "nonexistent_field",
            })
        assert "PARSE_ERROR" in str(exc_info.value)

    def test_docker_hub_empty_results(self, fake_http) -> None:
        """Docker Hub returns zero tags → PARSE_ERROR."""
        fake_http.set(
            "https://hub.docker.com/v2/repositories/lib/empty/tags/?page_size=1",
            b'{"count":0,"results":[]}',
        )
        mod = load_checker("package_registry", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({
                "registry_url": "https://hub.docker.com/v2/repositories/lib/empty/tags",
            })
        assert "PARSE_ERROR" in str(exc_info.value)
        assert "No tags found" in str(exc_info.value)
