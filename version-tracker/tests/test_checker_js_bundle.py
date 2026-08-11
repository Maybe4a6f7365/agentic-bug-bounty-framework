"""
tests/test_checker_js_bundle.py — JS bundle integrity checker unit tests.

Phase 1, §11.2 test ID U-JSBUNDLE-1 + §11.6 OSINT-CODEREVIEW-1.

Verifies:
- canonical JSON mapping of <script src=…> URLs to hashes or record-only markers
- script_filter narrows the set to a substring
- 304 short-circuits to None
- research_headers() are sent on every request
- immutable_identifier is sha256(canonical_json)
- change_type == 'js_bundle_changed'
- OSINT-CODEREVIEW-1: the checker fetches only page_url and same-origin
  HTTP(S) script URLs. Cross-origin/unsupported URLs and redirects are
  recorded without follow-up requests.

No real HTTP calls; FakeHTTPCache is injected via the fixture.
"""

import hashlib
import json
import unittest.mock as mock

import pytest

from tests.support.fakes import load_checker
from checkers import runner  # noqa: E402

CheckerError = runner.CheckerError


# ── Canned HTML fixtures ──────────────────────────────────────────────

PAGE_URL = "https://example.com/"

PAGE_THREE_SCRIPTS = """<!doctype html>
<html>
  <head>
    <script src="/static/app.js"></script>
    <script src="/static/runtime.js"></script>
    <script src="https://cdn.example.com/lib.js"></script>
  </head>
  <body>Hello.</body>
</html>
"""

PAGE_NO_SCRIPTS = """<!doctype html>
<html><head><title>Static</title></head><body>Plain.</body></html>
"""

PAGE_FIVE_SCRIPTS_FILTER_TWO = """<!doctype html>
<html><head>
<script src="/static/one.js"></script>
<script src="/static/two.js"></script>
<script src="https://cdn1.example.com/a.js"></script>
<script src="https://cdn2.example.com/b.js"></script>
<script src="https://cdn3.example.com/c.js"></script>
</head><body>Multi.</body></html>
"""


def _js_body_hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


class TestJsBundleChecker:
    """Canned-HTTP tests for js_bundle.check()."""

    # ── U-JSBUNDLE-1 / basic ──────────────────────────────────────

    def test_basic_records_cross_origin_without_fetching_it(self, fake_http) -> None:
        """Same-origin scripts are hashed; cross-origin scripts are record-only."""
        fake_http.set(PAGE_URL, PAGE_THREE_SCRIPTS.encode())
        body_a = "// app.js contents\nvar a = 1;\n"
        body_b = "// runtime.js contents\nvar b = 2;\n"
        fake_http.set("https://example.com/static/app.js", body_a.encode())
        fake_http.set("https://example.com/static/runtime.js", body_b.encode())

        mod = load_checker("js_bundle", http_cache=fake_http)
        result = mod.check({"page_url": PAGE_URL})

        assert result is not None
        assert result.changed
        parsed = json.loads(result.version_value)
        assert parsed == {
            "https://cdn.example.com/lib.js": "cross-origin:not-fetched",
            "https://example.com/static/app.js": _js_body_hash(body_a),
            "https://example.com/static/runtime.js": _js_body_hash(body_b),
        }
        assert len(parsed) == 3
        assert result.raw_metadata["skipped_cross_origin"] == [
            "https://cdn.example.com/lib.js"
        ]

    # ── U-JSBUNDLE-1 / OSINT-CODEREVIEW-1 ─────────────────────────

    def test_no_crawling_outside_page_response(self, fake_http) -> None:
        """OSINT-CODEREVIEW-1 negative test.

        Wrap http_cache.fetch with a recording fake and assert the checker
        requests only ``page_url`` plus same-origin HTTP(S) script URLs.
        Cross-origin references must remain record-only; any extra request,
        redirect follow, sitemap probe, HEAD, OPTIONS, or POST fails the test.
        """
        fake_http.set(PAGE_URL, PAGE_THREE_SCRIPTS.encode())
        fake_http.set("https://example.com/static/app.js", b"// app")
        fake_http.set("https://example.com/static/runtime.js", b"// runtime")

        # Wrap with a recording proxy to capture every URL the checker
        # actually requests.
        recorded = []

        def recording_fetch(url, headers=None, timeout=30, **kwargs):
            recorded.append(url)
            return fake_http.fetch(url, headers=headers, timeout=timeout, **kwargs)

        mod = load_checker("js_bundle", http_cache=fake_http)
        with mock.patch.object(mod, "http_cache", wraps=fake_http) as wrapped_mod_cache:
            # Inject the recording fetch via a wrapper.
            original_fetch = fake_http.fetch

            def fetch_with_recording(url, headers=None, timeout=30, **kwargs):
                recorded.append(url)
                return original_fetch(url, headers=headers, timeout=timeout, **kwargs)

            wrapped_mod_cache.fetch = fetch_with_recording

            mod.check({"page_url": PAGE_URL})

        fetched = set(recorded)
        expected = {
            PAGE_URL,
            "https://example.com/static/app.js",
            "https://example.com/static/runtime.js",
        }
        # Cross-origin script URLs are recorded, never requested.
        assert fetched == expected, (
            f"OSINT-CODEREVIEW-1 violated: fetched URLs differ.\n"
            f"  expected: {sorted(expected)}\n"
            f"  actual:   {sorted(fetched)}\n"
            f"  extra:    {sorted(fetched - expected)}"
        )

    # ── script_filter ─────────────────────────────────────────────

    def test_script_filter_narrows_to_substring(self, fake_http) -> None:
        """5 script tags but only 2 contain '/static/' → 2 entries."""
        fake_http.set(PAGE_URL, PAGE_FIVE_SCRIPTS_FILTER_TWO.encode())
        # Only 2 scripts actually fetched (the filtered set).
        fake_http.set("https://example.com/static/one.js", b"// one")
        fake_http.set("https://example.com/static/two.js", b"// two")
        # The other 3 URLs are never fetched — leave them out deliberately.

        mod = load_checker("js_bundle", http_cache=fake_http)
        result = mod.check({
            "page_url": PAGE_URL,
            "script_filter": "/static/",
        })

        assert result is not None
        parsed = json.loads(result.version_value)
        assert len(parsed) == 2
        # Every key must contain the substring '/static/'
        for url in parsed:
            assert "/static/" in url

    def test_empty_page_only_fetches_page_url(self, fake_http) -> None:
        """No <script src=…> tags → only {page_url} is fetched."""
        fake_http.set(PAGE_URL, PAGE_NO_SCRIPTS.encode())
        mod = load_checker("js_bundle", http_cache=fake_http)

        result = mod.check({"page_url": PAGE_URL})

        assert result is not None
        assert result.version_value == "{}"
        assert json.loads(result.version_value) == {}

        # Recorded fetches must be exactly {page_url}.
        fetched_urls = {req[0] for req in fake_http.requests}
        assert fetched_urls == {PAGE_URL}

    # ── 304 short-circuit ─────────────────────────────────────────

    def test_304_returns_none(self, fake_http) -> None:
        """http_cache returns None for page_url → checker returns None."""
        fake_http.set_304(PAGE_URL)
        mod = load_checker("js_bundle", http_cache=fake_http)

        result = mod.check({"page_url": PAGE_URL})

        assert result is None

    # ── request attribution ───────────────────────────────────────

    def test_research_headers_used(self, fake_http) -> None:
        """Every fetch carries X-HackerOne-Research + X-Bug-Bounty."""
        fake_http.set(PAGE_URL, PAGE_THREE_SCRIPTS.encode())
        fake_http.set("https://example.com/static/app.js", b"// app")
        fake_http.set("https://example.com/static/runtime.js", b"// runtime")
        mod = load_checker("js_bundle", http_cache=fake_http)

        mod.check({"page_url": PAGE_URL})

        # Every recorded request must carry the research attribution.
        for _, headers, _ in fake_http.requests:
            assert "X-HackerOne-Research" in headers
            assert "X-Bug-Bounty" in headers
        assert all(not option["follow_redirects"] for option in fake_http.fetch_options)

    # ── hash invariants ──────────────────────────────────────────

    def test_immutable_identifier_is_sha256_of_canonical_json(self, fake_http) -> None:
        """immutable_identifier == sha256(version_value)."""
        fake_http.set(PAGE_URL, PAGE_THREE_SCRIPTS.encode())
        fake_http.set("https://example.com/static/app.js", b"// a")
        fake_http.set("https://example.com/static/runtime.js", b"// b")
        mod = load_checker("js_bundle", http_cache=fake_http)

        result = mod.check({"page_url": PAGE_URL})

        assert result is not None
        expected = hashlib.sha256(result.version_value.encode()).hexdigest()
        assert result.immutable_identifier == expected

    # ── change_type / contract ────────────────────────────────────

    def test_change_type(self, fake_http) -> None:
        """change_type == 'js_bundle_changed'."""
        fake_http.set(PAGE_URL, b"<html><head><script src='/static/a.js'></script></head></html>")
        fake_http.set("https://example.com/static/a.js", b"// a")
        mod = load_checker("js_bundle", http_cache=fake_http)

        result = mod.check({"page_url": PAGE_URL})

        assert result is not None
        assert result.change_type == "js_bundle_changed"

    # ── bonus: missing config ─────────────────────────────────────

    def test_missing_page_url_raises_parse_error(self, fake_http) -> None:
        """No page_url → CheckerError PARSE_ERROR."""
        mod = load_checker("js_bundle", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({})
        assert exc_info.value.code == "PARSE_ERROR"
        assert "Missing 'page_url'" in str(exc_info.value)

    def test_unchanged_returns_none(self, fake_http) -> None:
        """_last_immutable_id matches → checker returns None."""
        fake_http.set(PAGE_URL, PAGE_THREE_SCRIPTS.encode())
        fake_http.set("https://example.com/static/app.js", b"// app")
        fake_http.set("https://example.com/static/runtime.js", b"// runtime")
        mod = load_checker("js_bundle", http_cache=fake_http)

        r1 = mod.check({"page_url": PAGE_URL})
        assert r1 is not None

        r2 = mod.check({
            "page_url": PAGE_URL,
            "_last_immutable_id": r1.immutable_identifier,
        })

        assert r2 is None

    def test_non_http_script_urls_are_recorded_without_fetching(self, fake_http) -> None:
        page = b"""<script src='javascript:alert(1)'></script>
        <script src='file:///etc/passwd'></script>
        <script src='/safe.js'></script>"""
        fake_http.set(PAGE_URL, page)
        fake_http.set("https://example.com/safe.js", b"safe")
        mod = load_checker("js_bundle", http_cache=fake_http)

        result = mod.check({"page_url": PAGE_URL})
        parsed = json.loads(result.version_value)

        assert parsed["javascript:alert(1)"] == "unsupported-scheme:not-fetched"
        assert parsed["file:///etc/passwd"] == "unsupported-scheme:not-fetched"
        assert {req[0] for req in fake_http.requests} == {
            PAGE_URL, "https://example.com/safe.js"
        }

    def test_script_redirect_is_recorded_and_not_followed(self, fake_http) -> None:
        script_url = "https://example.com/redirect.js"
        destination = "https://cdn.example.net/real.js"
        fake_http.set(PAGE_URL, b"<script src='/redirect.js'></script>")
        fake_http.set_redirect(script_url, destination)
        mod = load_checker("js_bundle", http_cache=fake_http)

        result = mod.check({"page_url": PAGE_URL})
        parsed = json.loads(result.version_value)

        assert parsed[script_url] == f"redirect:not-followed:{destination}"
        assert result.raw_metadata["blocked_redirects"] == {
            script_url: destination
        }
        assert {req[0] for req in fake_http.requests} == {PAGE_URL, script_url}
        assert all(not option["follow_redirects"] for option in fake_http.fetch_options)

    def test_page_redirect_is_recorded_without_following(self, fake_http) -> None:
        destination = "/en-eu/"
        fake_http.set_redirect(PAGE_URL, destination)
        mod = load_checker("js_bundle", http_cache=fake_http)

        result = mod.check({"page_url": PAGE_URL})

        assert json.loads(result.version_value) == {
            PAGE_URL: f"redirect:not-followed:{destination}"
        }
        assert result.raw_metadata["page_redirect"] == destination
        assert {req[0] for req in fake_http.requests} == {PAGE_URL}
        assert fake_http.fetch_options == [{"follow_redirects": False}]

        unchanged = mod.check({
            "page_url": PAGE_URL,
            "_last_immutable_id": result.immutable_identifier,
        })
        assert unchanged is None

    @pytest.mark.parametrize("page_url", [
        "file:///etc/passwd",
        "ftp://example.com/index.html",
        "javascript:alert(1)",
        "http://127.0.0.1/index.html",
        "http://127.1/index.html",
        "http://2130706433/index.html",
        "http://0x7f000001/index.html",
        "http://0177.0.0.1/index.html",
        "http://[::1]/index.html",
        "http://localhost/index.html",
    ])
    def test_page_url_must_be_public_http_or_https(self, fake_http, page_url) -> None:
        mod = load_checker("js_bundle", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"page_url": page_url})

        assert exc_info.value.code == "PARSE_ERROR"

    def test_explicit_port_zero_is_not_treated_as_default_port(self, fake_http) -> None:
        script_url = "https://example.com:0/port-zero.js"
        fake_http.set(
            PAGE_URL,
            b"<script src='https://example.com:0/port-zero.js'></script>",
        )
        mod = load_checker("js_bundle", http_cache=fake_http)

        result = mod.check({"page_url": PAGE_URL})

        assert json.loads(result.version_value)[script_url] == "cross-origin:not-fetched"
        assert {req[0] for req in fake_http.requests} == {PAGE_URL}
