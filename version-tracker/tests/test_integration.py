"""
tests/test_integration.py — End-to-end integration tests for the version-tracker pipeline.

Phase 11 (FINAL).  Validates the full pipeline from source seeding →
checker dispatch → observation recording for all 7 checker types,
plus error handling, no-change detection, and first-check mode.

Guarded by VT_INTEGRATION=1 — these tests do NOT run in the default
``pytest`` path.  All tests use the ``db`` + ``fake_http`` fixtures —
NO real network calls.

Run:  VT_INTEGRATION=1 .venv/bin/python -m pytest tests/test_integration.py -v
Skip: VT_INTEGRATION=0 .venv/bin/python -m pytest tests/test_integration.py -v
"""

import json
import os
import sys

import pytest

# ── Path setup (mirrors tests/__init__.py) ──────────────────────────
_checkers_dir = os.path.join(os.path.dirname(__file__), "..", "checkers")
if _checkers_dir not in sys.path:
    sys.path.insert(0, _checkers_dir)

from checkers import runner
from checkers.runner import _run_check_on_db, CheckerError
from tests.support.fakes import FIREFOX_APP

# ── Gate: all tests skipped unless VT_INTEGRATION=1 ─────────────────
pytestmark = pytest.mark.skipif(
    os.environ.get("VT_INTEGRATION") != "1",
    reason="Set VT_INTEGRATION=1 to run end-to-end integration tests",
)

# ── Canned HTTP Responses ───────────────────────────────────────────

API_SIMPLE_VERSION = b'{"version": "v3.2.1"}'
API_SIMPLE_VERSION_V2 = b'{"version": "v4.0.0"}' 

GITHUB_RELEASE = json.dumps({
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

ATOM_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Example Changelog</title>
  <updated>2026-07-01T12:00:00Z</updated>
  <entry>
    <id>urn:uuid:abc-123</id>
    <title>Release v3.2.1</title>
    <link href="https://example.com/releases/v3.2.1" rel="alternate"/>
    <updated>2026-07-01T12:00:00Z</updated>
    <summary>Bug fixes and performance improvements.</summary>
  </entry>
</feed>"""

ATOM_FEED_DIFF = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Example Changelog</title>
  <entry><id>urn:uuid:abc-123</id><title>Release v3.2.1 corrected</title>
    <link href="https://example.com/releases/v3.2.1"/><updated>2026-07-01T12:00:00Z</updated>
    <summary>Corrected release notes.</summary></entry>
  <entry><id>urn:uuid:def-456</id><title>Release v3.2.2</title>
    <link href="https://example.com/releases/v3.2.2"/><updated>2026-07-02T12:00:00Z</updated>
    <summary>Patch.</summary></entry>
  <entry><id>urn:uuid:ghi-789</id><title>Release v4.0.0</title>
    <link href="https://example.com/releases/v4.0.0"/><updated>2026-07-03T12:00:00Z</updated>
    <summary>Major.</summary></entry>
</feed>"""

API_JSON_VERSION = b'{"version": "3.2.1", "build": "20260701", "name": "my-api"}'

PYPI_REQUESTS = b'{"info":{"name":"requests","version":"2.32.5","summary":"Python HTTP for Humans.","author":"Kenneth Reitz","home_page":"https://requests.readthedocs.io","package_url":"https://pypi.org/project/requests/"},"last_serial":26829414,"urls":[]}'

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


# ── Helpers ─────────────────────────────────────────────────────────

def _seed_asset(db_conn, canonical_identifier="example.com", vector_type="website"):
    """Seed an asset row and return its asset_id."""
    cur = db_conn.execute(
        "INSERT INTO asset (vector_type, canonical_identifier, display_name) VALUES (?, ?, ?)",
        [vector_type, canonical_identifier, canonical_identifier],
    )
    db_conn.commit()
    return cur.lastrowid


def _seed_version_source(db_conn, asset_id, source_type="api",
                          check_method="json_path", config=None,
                          consecutive_failures=0, enabled=1,
                          source_identifier=None):
    """Seed a version_source row and return its version_source_id."""
    if config is None:
        config = {"api_url": "https://example.com/version",
                  "path": "$.version"}
    if source_identifier is None:
        source_identifier = f"{source_type}:{check_method}"
    cur = db_conn.execute(
        """INSERT INTO version_source
           (asset_id, source_type, source_identifier, check_method, config,
            enabled, check_interval, consecutive_failures)
           VALUES (?, ?, ?, ?, ?, ?, 86400, ?)""",
        [asset_id, source_type, source_identifier, check_method,
         json.dumps(config), enabled, consecutive_failures],
    )
    db_conn.commit()
    return cur.lastrowid


def _row(db_conn, vs_id):
    """Re-fetch a version_source row by id."""
    return db_conn.execute(
        "SELECT * FROM version_source WHERE version_source_id=?", [vs_id]
    ).fetchone()


# ── Tests ───────────────────────────────────────────────────────────

class TestEndToEndPipeline:
    """End-to-end pipeline tests: source seeding → checker dispatch → observation."""

    # ── 1. api full pipeline ─────────────────────────────────────

    def test_full_pipeline_api(self, db, fake_http, monkeypatch):
        """api source: seed → check → observation + check_run + change_event."""
        monkeypatch.setattr(runner, "http_cache", fake_http)
        fake_http.set("https://example.com/version", API_SIMPLE_VERSION)
        asset_id = _seed_asset(db, canonical_identifier="example.com")
        config = {"api_url": "https://example.com/version",
                  "path": "$.version"}
        vs_id = _seed_version_source(db, asset_id, source_type="api",
                                     check_method="json_path", config=config)

        result = _run_check_on_db(db, _row(db, vs_id), first_check_mode=False)

        assert result["status"] == "success"
        assert result["changed"]
        assert "observation_id" in result

        # Observation written
        obs = db.execute(
            "SELECT * FROM version_observation WHERE version_observation_id=?",
            [result["observation_id"]],
        ).fetchone()
        assert obs["version_value"] == "v3.2.1"
        assert obs["is_current"] == 1
        assert obs["version_source_id"] == vs_id

        # Check_run with status='success'
        cr = db.execute(
            "SELECT * FROM check_run WHERE check_run_id=?",
            [result["check_run_id"]],
        ).fetchone()
        assert cr["status"] == "success"
        assert cr["changed"] == 1
        assert cr["version_source_id"] == vs_id

        # Change_event written
        events = db.execute(
            "SELECT * FROM version_change_event WHERE version_source_id=?", [vs_id]
        ).fetchall()
        assert len(events) == 1
        assert events[0]["change_type"] == "api_version_changed"
        assert events[0]["research_status"] == "new"

        # Version_source updated
        vs = _row(db, vs_id)
        assert vs["consecutive_failures"] == 0
        assert vs["last_checked_at"] is not None
        assert vs["last_success_at"] is not None
        assert vs["last_error"] is None

    # ── 2. github full pipeline ──────────────────────────────────

    def test_full_pipeline_github(self, db, fake_http, monkeypatch):
        """github source: release detection, immutable_identifier from node_id."""
        monkeypatch.setattr(runner, "http_cache", fake_http)
        url = "https://api.github.com/repos/Shopify/cli/releases/latest"
        fake_http.set(url, GITHUB_RELEASE)

        asset_id = _seed_asset(db, canonical_identifier="github.com/Shopify/cli",
                               vector_type="github_repository")
        config = {"repo": "Shopify/cli", "api_endpoint": "/releases/latest", "field": "tag_name"}
        vs_id = _seed_version_source(db, asset_id, source_type="github",
                                     check_method="tags", config=config,
                                     source_identifier="github:tags:Shopify/cli")

        result = _run_check_on_db(db, _row(db, vs_id), first_check_mode=False)

        assert result["status"] == "success"
        assert result["changed"]
        assert "observation_id" in result
        assert result["change_type"] == "release_published"

        obs = db.execute(
            "SELECT * FROM version_observation WHERE version_observation_id=?",
            [result["observation_id"]],
        ).fetchone()
        assert obs["version_value"] == "v3.2.1"
        # GitHub checker uses node_id as immutable_identifier
        assert obs["immutable_identifier"] is not None
        assert obs["is_current"] == 1

        # Check_run
        cr = db.execute(
            "SELECT * FROM check_run WHERE check_run_id=?",
            [result["check_run_id"]],
        ).fetchone()
        assert cr["status"] == "success"
        assert cr["changed"] == 1

        # Change event type specific to github
        events = db.execute(
            "SELECT * FROM version_change_event WHERE version_source_id=?", [vs_id]
        ).fetchall()
        assert len(events) == 1
        assert events[0]["change_type"] == "release_published"

        vs = _row(db, vs_id)
        assert vs["consecutive_failures"] == 0
        assert vs["last_success_at"] is not None

    # ── 3. RSS feed full pipeline ────────────────────────────────

    def test_full_pipeline_rss(self, db, fake_http, monkeypatch):
        """RSS feed source: entry detection, immutable_identifier from GUID."""
        monkeypatch.setattr(runner, "http_cache", fake_http)
        fake_http.set("https://example.com/changelog.xml", ATOM_FEED)

        asset_id = _seed_asset(db, canonical_identifier="example.com",
                               vector_type="website")
        config = {"feed_url": "https://example.com/changelog.xml"}
        vs_id = _seed_version_source(db, asset_id, source_type="rss",
                                     check_method="rss", config=config)

        result = _run_check_on_db(db, _row(db, vs_id), first_check_mode=False)

        assert result["status"] == "success"
        assert result["changed"]
        assert "observation_id" in result
        assert result["change_type"] == "changelog_entry_added"

        obs = db.execute(
            "SELECT * FROM version_observation WHERE version_observation_id=?",
            [result["observation_id"]],
        ).fetchone()
        assert obs["version_value"] == "Release v3.2.1"
        assert obs["immutable_identifier"] is not None
        assert obs["is_current"] == 1

        cr = db.execute(
            "SELECT * FROM check_run WHERE check_run_id=?",
            [result["check_run_id"]],
        ).fetchone()
        assert cr["status"] == "success"
        assert cr["changed"] == 1

        events = db.execute(
            "SELECT * FROM version_change_event WHERE version_source_id=?", [vs_id]
        ).fetchall()
        assert len(events) == 1
        assert events[0]["change_type"] == "changelog_entry_added"

        vs = _row(db, vs_id)
        assert vs["consecutive_failures"] == 0

    def test_rss_diff_writes_one_event_per_changed_entry(self, db, fake_http, monkeypatch):
        monkeypatch.setattr(runner, "http_cache", fake_http)
        url = "https://example.com/changelog.xml"
        fake_http.set(url, ATOM_FEED)
        asset_id = _seed_asset(db, canonical_identifier="rss-diff.example")
        vs_id = _seed_version_source(
            db,
            asset_id,
            source_type="rss",
            check_method="rss",
            config={"feed_url": url},
            source_identifier="rss:diff:example",
        )

        baseline = _run_check_on_db(db, _row(db, vs_id), first_check_mode=True)
        assert baseline["changed"] is False

        fake_http.set(url, ATOM_FEED_DIFF)
        changed = _run_check_on_db(db, _row(db, vs_id), first_check_mode=True)
        assert changed["changed"] is True

        events = db.execute(
            """SELECT change_type, item_identifier, change_details
               FROM version_change_event
               WHERE version_source_id=? ORDER BY item_identifier""",
            [vs_id],
        ).fetchall()
        assert [(row["item_identifier"], row["change_type"]) for row in events] == [
            ("urn:uuid:abc-123", "content_changed"),
            ("urn:uuid:def-456", "changelog_entry_added"),
            ("urn:uuid:ghi-789", "changelog_entry_added"),
        ]
        assert all(json.loads(row["change_details"])["item_identifier"] for row in events)
        assert len({row["item_identifier"] for row in events}) == 3

    def test_partial_legacy_rss_snapshot_is_refreshed_without_events(
        self, db, fake_http, monkeypatch
    ):
        monkeypatch.setattr(runner, "http_cache", fake_http)
        url = "https://example.com/legacy.xml"
        fake_http.set(url, ATOM_FEED_DIFF)
        asset_id = _seed_asset(db, canonical_identifier="legacy-rss.example")
        vs_id = _seed_version_source(
            db,
            asset_id,
            source_type="rss",
            check_method="rss",
            config={"feed_url": url},
            source_identifier="rss:legacy:example",
        )
        db.execute(
            """INSERT INTO version_observation
               (version_source_id, asset_id, version_value, immutable_identifier,
                raw_metadata, is_current)
               VALUES (?, ?, 'old', 'urn:uuid:abc-123', ?, 1)""",
            [vs_id, asset_id, json.dumps({
                "entry_count": 239,
                "all_guids": ["urn:uuid:abc-123"],
            })],
        )
        db.commit()

        result = _run_check_on_db(db, _row(db, vs_id), first_check_mode=True)

        assert result["changed"] is False
        assert result["event_count"] == 0
        assert db.execute(
            "SELECT COUNT(*) FROM version_change_event WHERE version_source_id=?",
            [vs_id],
        ).fetchone()[0] == 0
        current = db.execute(
            """SELECT raw_metadata FROM version_observation
               WHERE version_source_id=? AND is_current=1""",
            [vs_id],
        ).fetchone()
        assert len(json.loads(current["raw_metadata"])["entries"]) == 3

    # ── 4. API JSON full pipeline ────────────────────────────────

    def test_full_pipeline_api_json(self, db, fake_http, monkeypatch):
        """api source (dispatches to api_json): JSON path extraction."""
        monkeypatch.setattr(runner, "http_cache", fake_http)
        fake_http.set("https://api.example.com/version", API_JSON_VERSION)

        asset_id = _seed_asset(db, canonical_identifier="api.example.com",
                               vector_type="api")
        config = {"api_url": "https://api.example.com/version", "path": "$.version"}
        vs_id = _seed_version_source(db, asset_id, source_type="api",
                                     check_method="json_path", config=config,
                                     source_identifier="api:json_path:api.example.com")

        result = _run_check_on_db(db, _row(db, vs_id), first_check_mode=False)

        assert result["status"] == "success"
        assert result["changed"]
        assert result["change_type"] == "api_version_changed"

        obs = db.execute(
            "SELECT * FROM version_observation WHERE version_observation_id=?",
            [result["observation_id"]],
        ).fetchone()
        assert obs["version_value"] == "3.2.1"
        assert obs["is_current"] == 1

        cr = db.execute(
            "SELECT * FROM check_run WHERE check_run_id=?",
            [result["check_run_id"]],
        ).fetchone()
        assert cr["status"] == "success"
        assert cr["changed"] == 1

        vs = _row(db, vs_id)
        assert vs["consecutive_failures"] == 0
        assert vs["last_success_at"] is not None

    # ── 5. No-change detection ───────────────────────────────────

    def test_full_pipeline_no_change(self, db, fake_http, monkeypatch):
        """When content is unchanged (HTTP 304), no new observation is written,
        existing observation stays current."""
        monkeypatch.setattr(runner, "http_cache", fake_http)
        fake_http.set("https://example.com/version", API_SIMPLE_VERSION)
        asset_id = _seed_asset(db, canonical_identifier="example.com")
        config = {"api_url": "https://example.com/version",
                  "path": "$.version"}
        vs_id = _seed_version_source(db, asset_id, source_type="api",
                                     check_method="json_path", config=config)

        # First check: creates baseline observation
        _run_check_on_db(db, _row(db, vs_id), first_check_mode=False)

        obs_count_before = db.execute(
            "SELECT COUNT(*) AS n FROM version_observation WHERE version_source_id=?",
            [vs_id],
        ).fetchone()["n"]
        assert obs_count_before == 1

        # Second check: simulate 304 (content unchanged)
        fake_http.set_304("https://example.com/version")
        result = _run_check_on_db(db, _row(db, vs_id), first_check_mode=False)

        assert result["status"] == "success"
        assert not result["changed"]

        # No new observation
        obs_count_after = db.execute(
            "SELECT COUNT(*) AS n FROM version_observation WHERE version_source_id=?",
            [vs_id],
        ).fetchone()["n"]
        assert obs_count_after == obs_count_before

        # Existing observation still is_current=1
        obs = db.execute(
            "SELECT * FROM version_observation WHERE version_source_id=? AND is_current=1",
            [vs_id],
        ).fetchone()
        assert obs is not None
        assert obs["version_value"] == "v3.2.1"

        # Check_run has changed=0
        cr = db.execute(
            "SELECT * FROM check_run WHERE check_run_id=?",
            [result["check_run_id"]],
        ).fetchone()
        assert cr["status"] == "success"
        assert cr["changed"] == 0

        # consecutive_failures stays 0 (no-change is not a failure)
        vs = _row(db, vs_id)
        assert vs["consecutive_failures"] == 0

    # ── 6. Error handling ───────────────────────────────────────

    def test_full_pipeline_error_handling(self, db, fake_http, monkeypatch):
        """Invalid config → CheckerError → check_run with error_code,
        consecutive_failures incremented."""
        monkeypatch.setattr(runner, "http_cache", fake_http)
        # Seed source with missing 'api_url' → PARSE_ERROR from the checker
        asset_id = _seed_asset(db, canonical_identifier="example.com")
        config = {"path": "$.version"}  # missing api_url
        vs_id = _seed_version_source(db, asset_id, source_type="api",
                                     check_method="json_path", config=config,
                                     consecutive_failures=0)

        result = _run_check_on_db(db, _row(db, vs_id), first_check_mode=False)

        assert result["status"] == "failure"
        assert "error_code" in result
        assert result["consecutive_failures"] > 0

        # Check_run with error
        cr = db.execute(
            "SELECT * FROM check_run WHERE check_run_id=?",
            [result["check_run_id"]],
        ).fetchone()
        assert cr["status"] == "failure"
        assert cr["error_code"] is not None
        assert cr["error_message"] is not None

        # Version_source updated with error info
        vs = _row(db, vs_id)
        assert vs["consecutive_failures"] == 1
        assert vs["last_error"] is not None
        assert vs["last_error_code"] is not None
        assert vs["last_error_at"] is not None

        # No observation written
        obs_count = db.execute(
            "SELECT COUNT(*) AS n FROM version_observation WHERE version_source_id=?",
            [vs_id],
        ).fetchone()["n"]
        assert obs_count == 0

    # ── 7. First-check mode ──────────────────────────────────────

    def test_full_pipeline_first_check(self, db, fake_http, monkeypatch):
        """first_check_mode=True: observation written as baseline,
        NO change_event created."""
        monkeypatch.setattr(runner, "http_cache", fake_http)
        fake_http.set("https://example.com/version", API_SIMPLE_VERSION)
        asset_id = _seed_asset(db, canonical_identifier="example.com")
        config = {"api_url": "https://example.com/version",
                  "path": "$.version"}
        vs_id = _seed_version_source(db, asset_id, source_type="api",
                                     check_method="json_path", config=config)

        result = _run_check_on_db(db, _row(db, vs_id), first_check_mode=True)

        assert result["status"] == "success"
        assert result["first_check"]
        assert not result["changed"]  # changed=False in first-check mode

        # Observation IS written (baseline)
        assert "observation_id" in result
        obs = db.execute(
            "SELECT * FROM version_observation WHERE version_observation_id=?",
            [result["observation_id"]],
        ).fetchone()
        assert obs is not None
        assert obs["is_current"] == 1
        assert obs["version_value"] == "v3.2.1"

        # NO change_event for baseline
        events = db.execute(
            "SELECT * FROM version_change_event WHERE version_source_id=?", [vs_id]
        ).fetchall()
        assert len(events) == 0, \
            "First-check mode must not write a change_event"

        # Check_run has changed=0 for baseline
        cr = db.execute(
            "SELECT * FROM check_run WHERE check_run_id=?",
            [result["check_run_id"]],
        ).fetchone()
        assert cr["changed"] == 0

        # Version_source updated successfully
        vs = _row(db, vs_id)
        assert vs["consecutive_failures"] == 0
        assert vs["last_success_at"] is not None

    # ── 8. All checker types dispatch ────────────────────────────

    def test_all_checker_types_dispatch(self, db, fake_http, fake_gps, monkeypatch):
        """Seed one source for each of the 7 checker types, verify each
        dispatches to the correct module and produces a result."""
        monkeypatch.setattr(runner, "http_cache", fake_http)
        monkeypatch.setitem(sys.modules, "google_play_scraper", fake_gps)
        fake_gps.app.set("org.mozilla.firefox", FIREFOX_APP)

        # Checker types and their configs + canned data
        types_and_configs = [
            # (source_type, check_method, config, url, canned_data, vector_type, source_identifier)
            ("github", "tags",
             {"repo": "Shopify/cli", "api_endpoint": "/releases/latest", "field": "tag_name"},
             "https://api.github.com/repos/Shopify/cli/releases/latest", GITHUB_RELEASE,
             "github_repository", "github:tags:Shopify/cli"),
            ("rss", "rss",
             {"feed_url": "https://example.com/feed.xml"},
             "https://example.com/feed.xml", ATOM_FEED, "website",
             "rss:rss:example.com/feed"),
            ("api", "json_path",
             {"api_url": "https://api.example.com/v", "path": "$.version"},
             "https://api.example.com/v", API_JSON_VERSION, "api",
             "api:json_path:api.example.com/v"),
            ("package_registry", "pypi",
             {"registry": "pypi", "package": "requests"},
             "https://pypi.org/pypi/requests/json", PYPI_REQUESTS, "other",
             "package_registry:pypi:requests"),
            ("ios_store", "app_store_lookup",
             {"bundle_id": "com.example.app"},
             "https://itunes.apple.com/lookup?bundleId=com.example.app",
             ITUNES_RESPONSE, "ios_app",
             "ios_store:app_store_lookup:com.example.app"),
            ("android_store", "play_store",
             {"app_id": "org.mozilla.firefox"},
             None,  # android_store uses google_play_scraper, not http_cache
             None, "android_app",
             "android_store:play_store:org.mozilla.firefox"),
        ]

        for (source_type, check_method, config, url, canned_data,
             vector_type, source_identifier) in types_and_configs:

            asset_id = _seed_asset(
                db,
                canonical_identifier=f"{source_type}-test.example.com",
                vector_type=vector_type or "website",
            )

            if canned_data is not None and url is not None:
                fake_http.set(url, canned_data)

            vs_id = _seed_version_source(
                db, asset_id,
                source_type=source_type,
                check_method=check_method,
                config=config,
                source_identifier=source_identifier,
            )

            result = _run_check_on_db(
                db, _row(db, vs_id), first_check_mode=False,
            )

            # Verify the check was attempted (check_run exists)
            assert "check_run_id" in result, \
                f"checker {source_type} did not produce check_run_id"
            cr = db.execute(
                "SELECT * FROM check_run WHERE check_run_id=?",
                [result["check_run_id"]],
            ).fetchone()
            assert cr is not None, \
                f"checker {source_type} has no check_run row"
            assert cr["version_source_id"] == vs_id, \
                f"checker {source_type} check_run references wrong source"

            # All should succeed (we set up valid canned data)
            assert result["status"] == "success", \
                f"checker {source_type} did not succeed: {result}"

            # Verify each was marked changed (first check with new data)
            assert result["changed"], \
                f"checker {source_type} should detect change on first check"

            # Observation written
            assert "observation_id" in result, \
                f"checker {source_type}: no observation_id in result"
            obs = db.execute(
                "SELECT * FROM version_observation WHERE version_observation_id=?",
                [result["observation_id"]],
            ).fetchone()
            assert obs is not None, \
                f"checker {source_type}: no observation written"
            assert obs["is_current"] == 1, \
                f"checker {source_type}: observation not current"
            assert obs["immutable_identifier"] is not None, \
                f"checker {source_type}: no immutable_identifier"
