import json
import sqlite3
from pathlib import Path


MIGRATION = Path(__file__).parents[1] / "sql/migrations/009_rss_item_events.sql"


def _pre_009_db(tmp_path):
    conn = sqlite3.connect(tmp_path / "pre009.db")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript("""
        CREATE TABLE asset (asset_id INTEGER PRIMARY KEY);
        CREATE TABLE version_source (
            version_source_id INTEGER PRIMARY KEY,
            asset_id INTEGER NOT NULL REFERENCES asset(asset_id)
        );
        CREATE TABLE version_observation (
            version_observation_id INTEGER PRIMARY KEY,
            version_source_id INTEGER NOT NULL REFERENCES version_source(version_source_id)
        );
        CREATE TABLE finding (
            finding_id INTEGER PRIMARY KEY,
            version_change_id INTEGER REFERENCES version_change_event(version_change_id)
        );
        CREATE TABLE version_change_event (
            version_change_id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_source_id INTEGER NOT NULL REFERENCES version_source(version_source_id),
            asset_id INTEGER NOT NULL REFERENCES asset(asset_id),
            change_type TEXT NOT NULL CHECK (change_type IN (
                'release_published','commit_advanced','api_version_changed',
                'build_number_changed','changelog_entry_added','content_changed',
                'version_regressed','source_disappeared','security_header_changed',
                'js_bundle_changed','xml_diff_changed'
            )),
            previous_observation_id INTEGER REFERENCES version_observation(version_observation_id),
            current_observation_id INTEGER REFERENCES version_observation(version_observation_id),
            detected_at TEXT NOT NULL DEFAULT (datetime('now')),
            research_status TEXT NOT NULL DEFAULT 'new' CHECK (research_status IN (
                'new','triaged','investigating','not_relevant','queued','complete'
            )),
            notes TEXT,
            UNIQUE(version_source_id, current_observation_id, change_type)
        );
        CREATE INDEX idx_version_change_research
          ON version_change_event(research_status, detected_at DESC);
        CREATE INDEX idx_version_change_source
          ON version_change_event(version_source_id, detected_at DESC);
        INSERT INTO asset VALUES (1);
        INSERT INTO version_source VALUES (1, 1);
        INSERT INTO version_observation VALUES (1, 1);
        INSERT INTO version_observation VALUES (2, 1);
        INSERT INTO version_change_event
          (version_change_id, version_source_id, asset_id, change_type,
           previous_observation_id, current_observation_id, research_status, notes)
        VALUES (7, 1, 1, 'release_published', 1, 2, 'triaged', 'legacy note');
        INSERT INTO finding VALUES (1, 7);
    """)
    conn.commit()
    return conn


def test_migration_009_preserves_rows_and_allows_per_item_events(tmp_path):
    conn = _pre_009_db(tmp_path)
    sql = MIGRATION.read_text()

    conn.executescript(sql)
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(version_change_event)")}
    assert {"item_identifier", "change_details"} <= columns

    legacy = conn.execute(
        "SELECT * FROM version_change_event WHERE version_change_id=7"
    ).fetchone()
    assert legacy["research_status"] == "triaged"
    assert legacy["notes"] == "legacy note"
    assert legacy["item_identifier"] == ""
    assert legacy["change_details"] is None

    for identifier in ("entry-a", "entry-b"):
        details = json.dumps({
            "item_identifier": identifier,
            "change_type": "changelog_entry_added",
        }, sort_keys=True, separators=(",", ":"))
        conn.execute(
            """INSERT INTO version_change_event
               (version_source_id, asset_id, change_type,
                previous_observation_id, current_observation_id,
                notes, item_identifier, change_details)
               VALUES (1, 1, 'changelog_entry_added', 1, 2, ?, ?, ?)""",
            [details, identifier, details],
        )
    conn.commit()

    item_rows = conn.execute(
        """SELECT item_identifier, change_details
           FROM version_change_event
           WHERE change_type='changelog_entry_added'
           ORDER BY item_identifier"""
    ).fetchall()
    assert [row["item_identifier"] for row in item_rows] == ["entry-a", "entry-b"]
    assert all(json.loads(row["change_details"])["item_identifier"] for row in item_rows)
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    indexes = {row["name"] for row in conn.execute("PRAGMA index_list(version_change_event)")}
    assert {"idx_version_change_research", "idx_version_change_source"} <= indexes
