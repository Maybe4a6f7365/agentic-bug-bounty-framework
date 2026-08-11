-- Migration 009: per-entry RSS diff events.
--
-- Adds an item identity and structured detail payload to version_change_event,
-- and extends uniqueness so one feed snapshot can emit several events of the
-- same change type. This is a one-time table-rebuild migration from schema
-- version 008; apply it exactly once after taking a database backup.

PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

DROP TABLE IF EXISTS version_change_event_new;
CREATE TABLE version_change_event_new (
    version_change_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    version_source_id         INTEGER NOT NULL REFERENCES version_source(version_source_id),
    asset_id                  INTEGER NOT NULL REFERENCES asset(asset_id),
    change_type               TEXT NOT NULL
                              CHECK (change_type IN (
                                  'release_published','commit_advanced',
                                  'api_version_changed','build_number_changed',
                                  'changelog_entry_added','content_changed',
                                  'version_regressed','source_disappeared',
                                  'security_header_changed','js_bundle_changed',
                                  'xml_diff_changed'
                              )),
    previous_observation_id   INTEGER REFERENCES version_observation(version_observation_id),
    current_observation_id    INTEGER REFERENCES version_observation(version_observation_id),
    detected_at               TEXT NOT NULL DEFAULT (datetime('now')),
    research_status           TEXT NOT NULL DEFAULT 'new'
                              CHECK (research_status IN (
                                  'new','triaged','investigating','not_relevant','queued','complete'
                              )),
    notes                     TEXT,
    item_identifier           TEXT NOT NULL DEFAULT '',
    change_details            TEXT,
    UNIQUE(version_source_id, current_observation_id, change_type, item_identifier)
);

INSERT INTO version_change_event_new
    (version_change_id, version_source_id, asset_id, change_type,
     previous_observation_id, current_observation_id, detected_at,
     research_status, notes, item_identifier, change_details)
SELECT
    version_change_id, version_source_id, asset_id, change_type,
    previous_observation_id, current_observation_id, detected_at,
    research_status, notes, '', NULL
FROM version_change_event;

DROP TABLE version_change_event;
ALTER TABLE version_change_event_new RENAME TO version_change_event;

CREATE INDEX idx_version_change_research
    ON version_change_event(research_status, detected_at DESC);
CREATE INDEX idx_version_change_source
    ON version_change_event(version_source_id, detected_at DESC);

COMMIT;
PRAGMA foreign_keys = ON;
