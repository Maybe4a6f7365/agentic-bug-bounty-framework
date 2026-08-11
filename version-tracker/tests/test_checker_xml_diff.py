"""
tests/test_checker_xml_diff.py — XML / robots.txt canonical diff checker unit tests.

Phase 1, §11.2 test ID U-XMLDIFF-1 + §11.6 OSINT-CODEREVIEW-2.

Verifies:
- canonicalisation strips comments and whitespace
- same URL + different body → different immutable_identifier
- 304 short-circuits to None
- research_headers() are sent
- immutable_identifier is sha256(canonicalised body)
- change_type == 'xml_diff_changed'
- OSINT-CODEREVIEW-2: the checker hashes the body as a string and
  NEVER descends into <loc>, <url>, <sitemap>, or any other element.
  An attacker.example/<loc> URL must NOT appear in the recorded fetch
  set.

No real HTTP calls.
"""

import hashlib
import json
import unittest.mock as mock

import pytest

from tests.support.fakes import load_checker
from checkers import runner  # noqa: E402

CheckerError = runner.CheckerError


# ── Canned robots.txt / sitemap fixtures ──────────────────────────────

ROBOTS_URL = "https://example.com/robots.txt"

ROBOTS_BASIC = b"""User-agent: *
Disallow: /admin
Disallow: /private

Sitemap: https://example.com/sitemap.xml
"""

# Same content with extra blank lines and comment lines; canonicalisation
# should produce identical output to ROBOTS_BASIC.
ROBOTS_NOISY = b"""
# This is a robots.txt comment
User-agent: *
Disallow: /admin
Disallow: /private


# Another comment

Sitemap: https://example.com/sitemap.xml
"""

# A sitemap-style body that mentions attacker.example in a <loc>. The
# OSINT-CODEREVIEW-2 invariant demands the checker never fetch that URL.
SITEMAP_WITH_ATTACKER = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/home</loc></url>
  <url><loc>http://attacker.example/loot</loc></url>
  <url><loc>https://example.com/about</loc></url>
</urlset>
"""

SITEMAP_V2 = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/home-v2</loc></url>
</urlset>
"""


class TestXmlDiffChecker:
    """Canned-HTTP tests for xml_diff.check()."""

    # ── U-XMLDIFF-1 / basic canonicalisation ──────────────────────

    def test_basic_canonicalizes_whitespace_and_strips_comments(self, fake_http) -> None:
        """robots.txt with blank lines + '#' comments → canonical form stripped."""
        fake_http.set(ROBOTS_URL, ROBOTS_NOISY)
        mod = load_checker("xml_diff", http_cache=fake_http)

        result = mod.check({
            "feed_url": ROBOTS_URL,
            "content_type_hint": "text/plain",
        })

        assert result is not None
        # The version_value is a JSON envelope wrapping the canonical body.
        envelope = json.loads(result.version_value)
        canonical = envelope["canonical_body"]
        assert "#" not in canonical  # comments gone
        # Multiple blank lines collapsed — single blank line between blocks.
        assert "\n\n\n" not in canonical
        # Single comment-prefixed line was dropped entirely.
        for line in canonical.splitlines():
            # No '# comment' lines should remain. A '#' is only valid as a
            # URL fragment, e.g. `https://x/page#frag`. We use '# stand-alone'
            # checks for any leading-# (the canonical form trims trailing
            # whitespace, not 'Disallow: /something#tag').
            stripped = line.lstrip()
            if stripped.startswith("#"):
                pytest.fail(f"Found unstripped comment line in canonical: {line!r}")
        # Essential data preserved.
        assert "Disallow: /admin" in canonical
        assert "Disallow: /private" in canonical
        assert "Sitemap: https://example.com/sitemap.xml" in canonical

    # ── U-XMLDIFF-1 / OSINT-CODEREVIEW-2 ─────────────────────────

    def test_no_loc_following_in_sitemap(self, fake_http) -> None:
        """OSINT-CODEREVIEW-2 negative test.

        Feed a sitemap whose ``<loc>`` includes ``http://attacker.example/loot``.
        The checker's recorded URL set must contain ONLY ``{feed_url}`` —
        never ``attacker.example`` and never the parsed ``<loc>`` URLs.
        This proves the checker treats the XML body as opaque text and
        does not descend into element data.
        """
        fake_http.set("https://example.com/sitemap.xml", SITEMAP_WITH_ATTACKER)
        mod = load_checker("xml_diff", http_cache=fake_http)

        result = mod.check({
            "feed_url": "https://example.com/sitemap.xml",
            "content_type_hint": "application/xml",
        })

        assert result is not None
        fetched_urls = {req[0] for req in fake_http.requests}
        # The set of fetched URLs must be EXACTLY {feed_url}.
        # No <loc> derivations, no sitemap references to robots.txt, etc.
        assert fetched_urls == {"https://example.com/sitemap.xml"}, (
            f"OSINT-CODEREVIEW-2 violated: fetched URLs differ.\n"
            f"  actual: {sorted(fetched_urls)}"
        )
        # Explicit attacker.example check (the spec's negative control).
        assert not any(
            "attacker.example" in u for u in fetched_urls
        ), f"OSINT-CODEREVIEW-2 violated: fetched attacker.example in {fetched_urls!r}"

    # ── plain text robots → URL set ──────────────────────────────

    def test_plain_text_robots_does_not_parse_xml(self, fake_http) -> None:
        """robots.txt is text — only feed_url is fetched."""
        fake_http.set(ROBOTS_URL, ROBOTS_BASIC)
        mod = load_checker("xml_diff", http_cache=fake_http)

        mod.check({
            "feed_url": ROBOTS_URL,
            "content_type_hint": "text/plain",
        })

        fetched_urls = {req[0] for req in fake_http.requests}
        assert fetched_urls == {ROBOTS_URL}

    # ── body change → hash change ────────────────────────────────

    def test_xml_body_changes_immutable_identifier(self, fake_http) -> None:
        """Same URL, different body → different immutable_identifier."""
        fake_http.set("https://example.com/sitemap.xml", SITEMAP_WITH_ATTACKER)
        mod = load_checker("xml_diff", http_cache=fake_http)

        r1 = mod.check({
            "feed_url": "https://example.com/sitemap.xml",
            "content_type_hint": "application/xml",
        })
        assert r1 is not None

        # Now swap the canned body and re-check — immutable_id must differ.
        fake_http.set("https://example.com/sitemap.xml", SITEMAP_V2)
        r2 = mod.check({
            "feed_url": "https://example.com/sitemap.xml",
            "content_type_hint": "application/xml",
        })
        assert r2 is not None

        assert r1.immutable_identifier != r2.immutable_identifier

    # ── 304 short-circuit ─────────────────────────────────────────

    def test_304_returns_none(self, fake_http) -> None:
        """http_cache returns None (304) → check() returns None."""
        fake_http.set_304(ROBOTS_URL)
        mod = load_checker("xml_diff", http_cache=fake_http)

        result = mod.check({
            "feed_url": ROBOTS_URL,
            "content_type_hint": "text/plain",
        })

        assert result is None

    # ── request attribution ───────────────────────────────────────

    def test_research_headers_used(self, fake_http) -> None:
        """Every fetch carries X-HackerOne-Research + X-Bug-Bounty."""
        fake_http.set(ROBOTS_URL, ROBOTS_BASIC)
        mod = load_checker("xml_diff", http_cache=fake_http)

        mod.check({
            "feed_url": ROBOTS_URL,
            "content_type_hint": "text/plain",
        })

        for _, headers, _ in fake_http.requests:
            assert "X-HackerOne-Research" in headers
            assert "X-Bug-Bounty" in headers

    # ── hash invariants ──────────────────────────────────────────

    def test_immutable_identifier_is_sha256_of_canonicalized_body(self, fake_http) -> None:
        """immutable_identifier is sha256(canonical body bytes)."""
        fake_http.set(ROBOTS_URL, ROBOTS_BASIC)
        mod = load_checker("xml_diff", http_cache=fake_http)

        result = mod.check({
            "feed_url": ROBOTS_URL,
            "content_type_hint": "text/plain",
        })
        assert result is not None

        # Decode the canonical body and re-hash it independently.
        envelope = json.loads(result.version_value)
        canonical = envelope["canonical_body"]
        expected = hashlib.sha256(canonical.encode()).hexdigest()
        assert result.immutable_identifier == expected

    # ── change_type contract ──────────────────────────────────────

    def test_change_type(self, fake_http) -> None:
        """change_type == 'xml_diff_changed'."""
        fake_http.set(ROBOTS_URL, ROBOTS_BASIC)
        mod = load_checker("xml_diff", http_cache=fake_http)

        result = mod.check({
            "feed_url": ROBOTS_URL,
            "content_type_hint": "text/plain",
        })

        assert result is not None
        assert result.change_type == "xml_diff_changed"

    # ── bonus: missing config ─────────────────────────────────────

    def test_missing_feed_url_raises_parse_error(self, fake_http) -> None:
        """No feed_url → CheckerError PARSE_ERROR."""
        mod = load_checker("xml_diff", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({})
        assert exc_info.value.code == "PARSE_ERROR"
        assert "Missing 'feed_url'" in str(exc_info.value)

    def test_xml_canonicalizes_comments_and_whitespace(self, fake_http) -> None:
        """XML body with <!-- comments --> → comments stripped.

        Variant of test_basic_canonicalizes_whitespace_and_strips_comments
        for the XML path (content_type_hint = application/xml).
        """
        body_with_comments = b"""<?xml version="1.0" encoding="UTF-8"?>
<!-- top-level admin note -->
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <!-- an entry -->
  <url><loc>https://example.com/home</loc></url>
</urlset>
"""
        fake_http.set("https://example.com/sitemap.xml", body_with_comments)
        mod = load_checker("xml_diff", http_cache=fake_http)

        result = mod.check({
            "feed_url": "https://example.com/sitemap.xml",
            "content_type_hint": "application/xml",
        })

        assert result is not None
        envelope = json.loads(result.version_value)
        canonical = envelope["canonical_body"]
        # XML comments must be stripped, regardless of placement.
        assert "<!--" not in canonical
        assert "-->" not in canonical
        # Body content preserved.
        assert "https://example.com/home" in canonical
