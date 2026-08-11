"""
tests/test_checker_rss.py — RSS/Atom feed checker unit tests.

Phase 6.  Verifies Atom entry extraction, RSS item extraction, GUID
fallback logic, HTTP errors, network errors, XML parse errors, feed
format detection, change detection, and edge cases — all with
FakeHTTPCache.  No real HTTP calls.

Covers TEST_PLAN.md §2.2.
"""

import hashlib
import pytest

from tests.support.fakes import load_checker
from checkers import runner  # noqa: E402

CheckerError = runner.CheckerError


# ── Canned Atom Feed Fixtures ─────────────────────────────────────────

ATOM_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Example Changelog</title>
  <link href="https://example.com/atom.xml" rel="self"/>
  <updated>2026-07-01T12:00:00Z</updated>
  <entry>
    <id>urn:uuid:abc-123</id>
    <title>Release v3.2.1</title>
    <link href="https://example.com/releases/v3.2.1" rel="alternate"/>
    <updated>2026-07-01T12:00:00Z</updated>
    <summary>Bug fixes and performance improvements.</summary>
  </entry>
  <entry>
    <id>urn:uuid:def-456</id>
    <title>Release v3.2.0</title>
    <link href="https://example.com/releases/v3.2.0" rel="alternate"/>
    <updated>2026-06-15T12:00:00Z</updated>
    <summary>New features.</summary>
  </entry>
</feed>"""

ATOM_FEED_V2 = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Example Changelog</title>
  <link href="https://example.com/atom.xml" rel="self"/>
  <updated>2026-07-15T12:00:00Z</updated>
  <entry>
    <id>urn:uuid:ghi-789</id>
    <title>Release v4.0.0</title>
    <link href="https://example.com/releases/v4.0.0" rel="alternate"/>
    <updated>2026-07-15T12:00:00Z</updated>
    <summary>Major rewrite.</summary>
  </entry>
</feed>"""

ATOM_FEED_NO_GUID = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Changelog</title>
  <updated>2026-07-01T12:00:00Z</updated>
  <entry>
    <title>Release without ID</title>
    <link href="https://example.com/r1"/>
    <summary>This entry has no id element.</summary>
  </entry>
</feed>"""

ATOM_FEED_NO_GUID_OR_LINK = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Changelog</title>
  <updated>2026-07-01T12:00:00Z</updated>
  <entry>
    <title>No GUID or Link</title>
    <summary>Fallback to title+summary hash.</summary>
  </entry>
</feed>"""

ATOM_FEED_NO_ENTRIES = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Empty Feed</title>
  <updated>2026-07-01T12:00:00Z</updated>
</feed>"""

ATOM_FEED_NO_NAMESPACE = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed>
  <title>No Namespace</title>
  <updated>2026-07-01T12:00:00Z</updated>
  <entry>
    <id>urn:uuid:no-ns-001</id>
    <title>Release v1.0.0</title>
    <link href="https://example.com/r1"/>
    <updated>2026-07-01T12:00:00Z</updated>
    <summary>Atom feed without explicit xmlns.</summary>
  </entry>
</feed>"""


# ── Canned RSS 2.0 Feed Fixtures ──────────────────────────────────────

RSS_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example Changelog</title>
    <link>https://example.com/rss.xml</link>
    <description>Release notes</description>
    <item>
      <title>Release v3.2.1</title>
      <link>https://example.com/releases/v3.2.1</link>
      <guid isPermaLink="false">v3.2.1</guid>
      <pubDate>Mon, 01 Jul 2026 12:00:00 GMT</pubDate>
      <description>Bug fixes and performance improvements.</description>
    </item>
    <item>
      <title>Release v3.2.0</title>
      <link>https://example.com/releases/v3.2.0</link>
      <guid isPermaLink="false">v3.2.0</guid>
      <pubDate>Sat, 15 Jun 2026 12:00:00 GMT</pubDate>
      <description>New features.</description>
    </item>
  </channel>
</rss>"""

RSS_FEED_V2 = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example Changelog</title>
    <link>https://example.com/rss.xml</link>
    <description>Release notes</description>
    <item>
      <title>Release v4.0.0</title>
      <link>https://example.com/releases/v4.0.0</link>
      <guid isPermaLink="false">v4.0.0</guid>
      <pubDate>Tue, 15 Jul 2026 12:00:00 GMT</pubDate>
      <description>Major rewrite.</description>
    </item>
  </channel>
</rss>"""

RSS_FEED_NO_GUID = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Changelog</title>
    <link>https://example.com/rss</link>
    <description>Releases</description>
    <item>
      <title>No GUID Item</title>
      <link>https://example.com/r1</link>
      <pubDate>Mon, 01 Jul 2026 12:00:00 GMT</pubDate>
      <description>Uses link as GUID fallback.</description>
    </item>
  </channel>
</rss>"""

RSS_FEED_NO_GUID_OR_LINK = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Changelog</title>
    <link>https://example.com/rss</link>
    <description>Releases</description>
    <item>
      <title>No GUID or Link Item</title>
      <pubDate>Mon, 01 Jul 2026 12:00:00 GMT</pubDate>
      <description>Falls back to title+description hash.</description>
    </item>
  </channel>
</rss>"""

RSS_FEED_NO_CHANNEL = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <item>
    <title>Orphan Item</title>
    <link>https://example.com/foo</link>
  </item>
</rss>"""

RSS_FEED_NO_ITEMS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Empty</title>
    <link>https://example.com/rss</link>
    <description>No items here.</description>
  </channel>
</rss>"""


# ── Edge-case fixtures ────────────────────────────────────────────────

INVALID_XML = b"<not>valid<xml>>"

UNKNOWN_FORMAT = b"""<?xml version="1.0" encoding="UTF-8"?>
<someRandomRoot>
  <item><title>Not a feed</title></item>
</someRandomRoot>"""


# ── Canned HTTP URLs ──────────────────────────────────────────────────

URL_ATOM = "https://example.com/atom.xml"
URL_ATOM_V2 = "https://example.com/atom-v2.xml"
URL_ATOM_NO_GUID = "https://example.com/atom-noguid.xml"
URL_ATOM_NO_GUID_OR_LINK = "https://example.com/atom-nolink.xml"
URL_ATOM_NO_ENTRIES = "https://example.com/atom-empty.xml"
URL_ATOM_NO_NS = "https://example.com/atom-nons.xml"
URL_RSS = "https://example.com/rss.xml"
URL_RSS_V2 = "https://example.com/rss-v2.xml"
URL_RSS_NO_GUID = "https://example.com/rss-noguid.xml"
URL_RSS_NO_GUID_OR_LINK = "https://example.com/rss-nolink.xml"
URL_RSS_NO_CHANNEL = "https://example.com/rss-nochannel.xml"
URL_RSS_NO_ITEMS = "https://example.com/rss-noitems.xml"
URL_INVALID_XML = "https://example.com/invalid.xml"
URL_UNKNOWN_FORMAT = "https://example.com/unknown.xml"


def _atom(entries):
    body = "".join(
        f"""<entry><id>{identifier}</id><title>{title}</title>
        <link href=\"https://example.com/{identifier}\"/>
        <updated>{updated}</updated><summary>{summary}</summary></entry>"""
        for identifier, title, updated, summary in entries
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<feed xmlns="http://www.w3.org/2005/Atom"><title>Diff Feed</title>'
        f'{body}</feed>'
    ).encode()


def _atom_content(value):
    return f'''<?xml version="1.0"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry><id>body-entry</id><title>Body</title><summary>same</summary>
      <content type="html">{value}</content></entry>
    </feed>'''.encode()


def _atom_xhtml_content(value):
    return f'''<?xml version="1.0"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry><id>body-entry</id><title>Body</title><summary>same</summary>
      <content type="xhtml"><div xmlns="http://www.w3.org/1999/xhtml"><p>{value}</p></div></content></entry>
    </feed>'''.encode()


def _rss_encoded(value):
    return f'''<?xml version="1.0"?>
    <rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
      <channel><title>Body</title><item><guid>body-entry</guid><title>Body</title>
      <description>same</description><content:encoded>{value}</content:encoded>
      </item></channel>
    </rss>'''.encode()


def _previous_config(result):
    return {
        "feed_url": URL_ATOM,
        "_last_immutable_id": result.immutable_identifier,
        "_last_raw_metadata": result.raw_metadata,
    }


class TestRssChecker:
    """Canned-HTTP tests for rss.check()."""

    # ── Parse / config errors ────────────────────────────────────

    def test_missing_feed_url_raises_parse_error(self, fake_http) -> None:
        """check({}) → PARSE_ERROR 'Missing feed_url'."""
        mod = load_checker("rss", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({})
        assert exc_info.value.code == "PARSE_ERROR"
        assert "Missing 'feed_url'" in str(exc_info.value)

    # ── Atom feed extraction ─────────────────────────────────────

    def test_atom_extracts_first_entry(self, fake_http) -> None:
        """Atom feed → most recent entry used. guid=id, title extracted."""
        fake_http.set(URL_ATOM, ATOM_FEED)
        mod = load_checker("rss", http_cache=fake_http)

        result = mod.check({"feed_url": URL_ATOM})

        assert result is not None
        assert result.changed
        assert result.version_value == "Release v3.2.1"
        assert result.immutable_identifier == "urn:uuid:abc-123"
        assert result.published_at == "2026-07-01T12:00:00Z"
        assert result.change_type == "changelog_entry_added"

    def test_atom_metadata(self, fake_http) -> None:
        """Atom metadata: feed_type='atom', entry_count, latest_link, all_guids."""
        fake_http.set(URL_ATOM, ATOM_FEED)
        mod = load_checker("rss", http_cache=fake_http)

        result = mod.check({"feed_url": URL_ATOM})

        assert result.raw_metadata["feed_type"] == "atom"
        assert result.raw_metadata["entry_count"] == 2
        assert result.raw_metadata["latest_link"] == "https://example.com/releases/v3.2.1"
        assert result.raw_metadata["all_guids"] == ["urn:uuid:abc-123", "urn:uuid:def-456"]

    def test_atom_no_namespace(self, fake_http) -> None:
        """Atom feed without xmlns — uses plain tag names."""
        fake_http.set(URL_ATOM_NO_NS, ATOM_FEED_NO_NAMESPACE)
        mod = load_checker("rss", http_cache=fake_http)

        result = mod.check({"feed_url": URL_ATOM_NO_NS})

        assert result is not None
        assert result.version_value == "Release v1.0.0"
        assert result.immutable_identifier == "urn:uuid:no-ns-001"

    # ── Atom GUID fallback ───────────────────────────────────────

    def test_atom_no_guid_uses_link(self, fake_http) -> None:
        """Atom entry without <id> → guid=link URL."""
        fake_http.set(URL_ATOM_NO_GUID, ATOM_FEED_NO_GUID)
        mod = load_checker("rss", http_cache=fake_http)

        result = mod.check({"feed_url": URL_ATOM_NO_GUID})

        assert result is not None
        assert result.immutable_identifier == "https://example.com/r1"

    def test_atom_no_guid_or_link_uses_hash(self, fake_http) -> None:
        """Atom entry with no id and no link → guid=sha256(title+summary)[:16]."""
        fake_http.set(URL_ATOM_NO_GUID_OR_LINK, ATOM_FEED_NO_GUID_OR_LINK)
        mod = load_checker("rss", http_cache=fake_http)

        result = mod.check({"feed_url": URL_ATOM_NO_GUID_OR_LINK})

        assert result is not None
        expected = hashlib.sha256(
            b"No GUID or LinkFallback to title+summary hash."
        ).hexdigest()[:16]
        assert result.immutable_identifier == expected

    def test_atom_no_entries_raises_parse_error(self, fake_http) -> None:
        """Atom feed with zero entries → PARSE_ERROR."""
        fake_http.set(URL_ATOM_NO_ENTRIES, ATOM_FEED_NO_ENTRIES)
        mod = load_checker("rss", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"feed_url": URL_ATOM_NO_ENTRIES})
        assert "PARSE_ERROR" in str(exc_info.value)
        assert "No entries found" in str(exc_info.value)

    # ── RSS feed extraction ──────────────────────────────────────

    def test_rss_extracts_first_item(self, fake_http) -> None:
        """RSS 2.0 → first <item> used. guid extracted."""
        fake_http.set(URL_RSS, RSS_FEED)
        mod = load_checker("rss", http_cache=fake_http)

        result = mod.check({"feed_url": URL_RSS})

        assert result is not None
        assert result.changed
        assert result.version_value == "Release v3.2.1"
        assert result.immutable_identifier == "v3.2.1"
        assert result.published_at == "Mon, 01 Jul 2026 12:00:00 GMT"

    def test_rss_metadata(self, fake_http) -> None:
        """RSS metadata: feed_type='rss', entry_count, latest_link, all_guids."""
        fake_http.set(URL_RSS, RSS_FEED)
        mod = load_checker("rss", http_cache=fake_http)

        result = mod.check({"feed_url": URL_RSS})

        assert result.raw_metadata["feed_type"] == "rss"
        assert result.raw_metadata["entry_count"] == 2
        assert result.raw_metadata["latest_link"] == "https://example.com/releases/v3.2.1"
        assert result.raw_metadata["all_guids"] == ["v3.2.1", "v3.2.0"]

    # ── RSS GUID fallback ────────────────────────────────────────

    def test_rss_no_guid_uses_link(self, fake_http) -> None:
        """RSS item without <guid> → guid=link."""
        fake_http.set(URL_RSS_NO_GUID, RSS_FEED_NO_GUID)
        mod = load_checker("rss", http_cache=fake_http)

        result = mod.check({"feed_url": URL_RSS_NO_GUID})

        assert result is not None
        assert result.immutable_identifier == "https://example.com/r1"

    def test_rss_no_guid_or_link_uses_hash(self, fake_http) -> None:
        """RSS item with no guid and no link → guid=sha256(title+description)[:16]."""
        fake_http.set(URL_RSS_NO_GUID_OR_LINK, RSS_FEED_NO_GUID_OR_LINK)
        mod = load_checker("rss", http_cache=fake_http)

        result = mod.check({"feed_url": URL_RSS_NO_GUID_OR_LINK})

        assert result is not None
        expected = hashlib.sha256(
            b"No GUID or Link ItemFalls back to title+description hash."
        ).hexdigest()[:16]
        assert result.immutable_identifier == expected

    def test_rss_no_channel_raises_parse_error(self, fake_http) -> None:
        """RSS with no <channel> → PARSE_ERROR."""
        fake_http.set(URL_RSS_NO_CHANNEL, RSS_FEED_NO_CHANNEL)
        mod = load_checker("rss", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"feed_url": URL_RSS_NO_CHANNEL})
        assert "PARSE_ERROR" in str(exc_info.value)
        assert "No <channel>" in str(exc_info.value)

    def test_rss_no_items_raises_parse_error(self, fake_http) -> None:
        """RSS with channel but no items → PARSE_ERROR."""
        fake_http.set(URL_RSS_NO_ITEMS, RSS_FEED_NO_ITEMS)
        mod = load_checker("rss", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"feed_url": URL_RSS_NO_ITEMS})
        assert "PARSE_ERROR" in str(exc_info.value)
        assert "No entries found" in str(exc_info.value)

    # ── Change detection ─────────────────────────────────────────

    def test_atom_unchanged_returns_none(self, fake_http) -> None:
        """_last_immutable_id matches latest guid → None."""
        fake_http.set(URL_ATOM, ATOM_FEED)
        mod = load_checker("rss", http_cache=fake_http)

        result = mod.check({
            "feed_url": URL_ATOM,
            "_last_immutable_id": "urn:uuid:abc-123",
        })

        assert result is None

    def test_atom_changed_returns_result(self, fake_http) -> None:
        """Different _last_immutable_id → changed=True."""
        fake_http.set(URL_ATOM, ATOM_FEED)
        mod = load_checker("rss", http_cache=fake_http)

        result = mod.check({
            "feed_url": URL_ATOM,
            "_last_immutable_id": "urn:uuid:old-stale",
        })

        assert result is not None
        assert result.changed

    def test_rss_unchanged_returns_none(self, fake_http) -> None:
        """RSS: _last_immutable_id matches → None."""
        fake_http.set(URL_RSS, RSS_FEED)
        mod = load_checker("rss", http_cache=fake_http)

        result = mod.check({
            "feed_url": URL_RSS,
            "_last_immutable_id": "v3.2.1",
        })

        assert result is None

    def test_rss_changed_returns_result(self, fake_http) -> None:
        """RSS: different _last_immutable_id → changed=True."""
        fake_http.set(URL_RSS, RSS_FEED)
        mod = load_checker("rss", http_cache=fake_http)

        result = mod.check({
            "feed_url": URL_RSS,
            "_last_immutable_id": "v1.0.0",
        })

        assert result is not None
        assert result.changed

    def test_reordered_entries_are_unchanged(self, fake_http) -> None:
        entries = [
            ("one", "One", "2026-08-01T00:00:00Z", "First"),
            ("two", "Two", "2026-08-02T00:00:00Z", "Second"),
        ]
        fake_http.set(URL_ATOM, _atom(entries))
        mod = load_checker("rss", http_cache=fake_http)
        previous = mod.check({"feed_url": URL_ATOM})

        fake_http.set(URL_ATOM, _atom(list(reversed(entries))))
        assert mod.check(_previous_config(previous)) is None

    def test_multiple_added_entries_each_become_change_items(self, fake_http) -> None:
        original = [("one", "One", "2026-08-01T00:00:00Z", "First")]
        current = original + [
            ("two", "Two", "2026-08-02T00:00:00Z", "Second"),
            ("three", "Three", "2026-08-03T00:00:00Z", "Third"),
        ]
        fake_http.set(URL_ATOM, _atom(original))
        mod = load_checker("rss", http_cache=fake_http)
        previous = mod.check({"feed_url": URL_ATOM})

        fake_http.set(URL_ATOM, _atom(current))
        result = mod.check(_previous_config(previous))

        assert [(item["item_identifier"], item["change_type"])
                for item in result.change_items] == [
            ("three", "changelog_entry_added"),
            ("two", "changelog_entry_added"),
        ]

    @pytest.mark.parametrize(
        "feed_factory", [_atom_content, _atom_xhtml_content, _rss_encoded]
    )
    def test_entry_body_edit_is_detected(self, fake_http, feed_factory) -> None:
        fake_http.set(URL_ATOM, feed_factory("OLD"))
        mod = load_checker("rss", http_cache=fake_http)
        previous = mod.check({"feed_url": URL_ATOM})

        fake_http.set(URL_ATOM, feed_factory("NEW"))
        result = mod.check(_previous_config(previous))

        assert len(result.change_items) == 1
        assert result.change_items[0]["item_identifier"] == "body-entry"
        assert result.change_items[0]["change_type"] == "content_changed"

    def test_same_identifier_content_edit_is_detected(self, fake_http) -> None:
        original = [("one", "One", "2026-08-01T00:00:00Z", "Original")]
        edited = [("one", "One revised", "2026-08-01T00:00:00Z", "Corrected")]
        fake_http.set(URL_ATOM, _atom(original))
        mod = load_checker("rss", http_cache=fake_http)
        previous = mod.check({"feed_url": URL_ATOM})

        fake_http.set(URL_ATOM, _atom(edited))
        result = mod.check(_previous_config(previous))

        assert len(result.change_items) == 1
        item = result.change_items[0]
        assert item["item_identifier"] == "one"
        assert item["change_type"] == "content_changed"
        assert item["old"]["title"] == "One"
        assert item["new"]["title"] == "One revised"

    def test_removed_entry_is_detected_regardless_of_order(self, fake_http) -> None:
        original = [
            ("one", "One", "2026-08-01T00:00:00Z", "First"),
            ("two", "Two", "2026-08-02T00:00:00Z", "Second"),
        ]
        fake_http.set(URL_ATOM, _atom(original))
        mod = load_checker("rss", http_cache=fake_http)
        previous = mod.check({"feed_url": URL_ATOM})

        fake_http.set(URL_ATOM, _atom([original[1]]))
        result = mod.check(_previous_config(previous))

        assert [(item["item_identifier"], item["change_type"])
                for item in result.change_items] == [
            ("one", "source_disappeared"),
        ]

    def test_partial_legacy_guid_metadata_refreshes_without_false_additions(self, fake_http) -> None:
        fake_http.set(URL_ATOM, ATOM_FEED)
        mod = load_checker("rss", http_cache=fake_http)

        result = mod.check({
            "feed_url": URL_ATOM,
            "_last_immutable_id": "urn:uuid:abc-123",
            "_last_raw_metadata": {
                "entry_count": 239,
                "all_guids": ["urn:uuid:abc-123", "urn:uuid:def-456"],
            },
        })

        assert result is not None
        assert result.baseline_only is True
        assert result.change_items == []
        assert set(result.raw_metadata["entries"]) == {
            "urn:uuid:abc-123", "urn:uuid:def-456",
        }

    def test_complete_legacy_guid_metadata_reports_only_safe_additions(self, fake_http) -> None:
        fake_http.set(URL_ATOM, ATOM_FEED)
        mod = load_checker("rss", http_cache=fake_http)

        result = mod.check({
            "feed_url": URL_ATOM,
            "_last_raw_metadata": {
                "entry_count": 1,
                "all_guids": ["urn:uuid:abc-123"],
            },
        })

        assert [(item["item_identifier"], item["change_type"])
                for item in result.change_items] == [
            ("urn:uuid:def-456", "changelog_entry_added"),
        ]

    # ── 304 Not Modified ─────────────────────────────────────────

    def test_304_returns_none(self, fake_http) -> None:
        """http_cache returns None (304) → check() returns None."""
        fake_http.set_304(URL_ATOM)
        mod = load_checker("rss", http_cache=fake_http)

        result = mod.check({"feed_url": URL_ATOM})

        assert result is None

    def test_304_even_without_last_immutable_id(self, fake_http) -> None:
        """304 → None even without _last_immutable_id."""
        fake_http.set_304(URL_RSS)
        mod = load_checker("rss", http_cache=fake_http)

        result = mod.check({"feed_url": URL_RSS})

        assert result is None

    # ── HTTP error codes ─────────────────────────────────────────

    def test_http_404_feed_gone(self, fake_http) -> None:
        """HTTP 404 → FEED_GONE."""
        fake_http.set_404(URL_ATOM)
        mod = load_checker("rss", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"feed_url": URL_ATOM})
        assert "FEED_GONE" in str(exc_info.value)

    def test_http_410_feed_gone(self, fake_http) -> None:
        """HTTP 410 → FEED_GONE."""
        fake_http.set_410(URL_RSS)
        mod = load_checker("rss", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"feed_url": URL_RSS})
        assert "FEED_GONE" in str(exc_info.value)

    def test_http_301_storage_moved(self, fake_http) -> None:
        """HTTP 301 → STORAGE_MOVED."""
        fake_http.errors[URL_ATOM] = (301, "Moved Permanently")
        mod = load_checker("rss", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"feed_url": URL_ATOM})
        assert "STORAGE_MOVED" in str(exc_info.value)

    def test_http_302_storage_moved(self, fake_http) -> None:
        """HTTP 302 → STORAGE_MOVED."""
        fake_http.errors[URL_RSS] = (302, "Found")
        mod = load_checker("rss", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"feed_url": URL_RSS})
        assert "STORAGE_MOVED" in str(exc_info.value)

    def test_http_401_auth_required(self, fake_http) -> None:
        fake_http.errors[URL_ATOM] = (401, "Unauthorized")
        mod = load_checker("rss", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"feed_url": URL_ATOM})
        assert "AUTH_REQUIRED" in str(exc_info.value)

    def test_http_403_classified_as_bot_wall(self, fake_http) -> None:
        """HTTP 403 → BOT_WALL (intentional product decision, 2026-07-27).

        CDN/WAF bot detection returns 403 for non-browser requests.
        Distinguished from AUTH_REQUIRED so the runner can route it to
        flag_for_review: disable the source and file a research_note for a
        human. The wall is respected, never bypassed.
        """
        fake_http.set_403(URL_RSS)
        mod = load_checker("rss", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"feed_url": URL_RSS})
        assert "BOT_WALL" in str(exc_info.value)

    def test_http_401_still_auth_required(self, fake_http) -> None:
        """HTTP 401 → AUTH_REQUIRED (enum member still reachable)."""
        fake_http.errors[URL_ATOM] = (401, "Unauthorized")
        mod = load_checker("rss", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"feed_url": URL_ATOM})
        assert "AUTH_REQUIRED" in str(exc_info.value)

    def test_http_500_unknown(self, fake_http) -> None:
        fake_http.errors[URL_ATOM] = (500, "Internal Server Error")
        mod = load_checker("rss", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"feed_url": URL_ATOM})
        assert "UNKNOWN" in str(exc_info.value)

    # ── Network errors ───────────────────────────────────────────

    def test_urlerror_timed_out_maps_timeout(self, fake_http) -> None:
        fake_http.set_timeout(URL_ATOM, "connection timed out")
        mod = load_checker("rss", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"feed_url": URL_ATOM})
        assert "TIMEOUT" in str(exc_info.value)

    def test_urlerror_other_unknown(self, fake_http) -> None:
        fake_http.set_timeout(URL_RSS, "dns error")
        mod = load_checker("rss", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"feed_url": URL_RSS})
        assert "UNKNOWN" in str(exc_info.value)

    # ── XML parse errors ─────────────────────────────────────────

    def test_invalid_xml_raises_feed_gone(self, fake_http) -> None:
        """XML parse error → FEED_GONE."""
        fake_http.set(URL_INVALID_XML, INVALID_XML)
        mod = load_checker("rss", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"feed_url": URL_INVALID_XML})
        assert "FEED_GONE" in str(exc_info.value)
        assert "XML parse error" in str(exc_info.value)

    def test_unknown_format_raises_feed_gone(self, fake_http) -> None:
        """Valid XML but not Atom or RSS → FEED_GONE."""
        fake_http.set(URL_UNKNOWN_FORMAT, UNKNOWN_FORMAT)
        mod = load_checker("rss", http_cache=fake_http)

        with pytest.raises(CheckerError) as exc_info:
            mod.check({"feed_url": URL_UNKNOWN_FORMAT})
        assert "FEED_GONE" in str(exc_info.value)
        assert "Unknown feed format" in str(exc_info.value)

    # ── Content hash ─────────────────────────────────────────────

    def test_content_hash(self, fake_http) -> None:
        """content_hash = sha256(title + summary) hex."""
        fake_http.set(URL_ATOM, ATOM_FEED)
        mod = load_checker("rss", http_cache=fake_http)

        result = mod.check({"feed_url": URL_ATOM})

        expected = hashlib.sha256(
            b"Release v3.2.1 Bug fixes and performance improvements."
        ).hexdigest()
        assert result.content_hash == expected

    # ── Title truncation ─────────────────────────────────────────

    def test_title_truncated_to_200_chars(self, fake_http) -> None:
        """version_value is title[:200]."""
        fake_http.set(URL_ATOM, ATOM_FEED)
        mod = load_checker("rss", http_cache=fake_http)

        result = mod.check({"feed_url": URL_ATOM})

        assert len(result.version_value) <= 200

    # ── Headers ──────────────────────────────────────────────────

    def test_user_agent_header_set(self, fake_http) -> None:
        """Feeds are program-owned: identify the researcher on every request."""
        fake_http.set(URL_ATOM, ATOM_FEED)
        mod = load_checker("rss", http_cache=fake_http)

        mod.check({"feed_url": URL_ATOM})

        _, headers, _ = fake_http.requests[0]
        assert headers["User-Agent"].startswith("version-tracker/")
        assert "Mozilla" not in headers["User-Agent"]
        assert headers["X-HackerOne-Research"]
        assert headers["X-Bug-Bounty"]

    # ── all_guids capped at 20 ───────────────────────────────────

    def test_all_guids_capped_at_twenty(self, fake_http) -> None:
        """all_guids list is sliced to 20 entries."""
        fake_http.set(URL_ATOM, ATOM_FEED)
        mod = load_checker("rss", http_cache=fake_http)

        result = mod.check({"feed_url": URL_ATOM})

        assert len(result.raw_metadata["all_guids"]) == 2
        assert len(result.raw_metadata["all_guids"]) <= 20