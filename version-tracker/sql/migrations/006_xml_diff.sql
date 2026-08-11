-- Migration 006: add 'xml_diff' to version_source.source_type CHECK
--
-- Adds the 'xml_diff' enum value used by the new
-- checkers/builtin/xml_diff.py checker (Task 0.4 / Phase 1).
--
-- SQLite doesn't support ALTER TABLE ... ALTER COLUMN to change CHECK
-- constraints, so we rebuild the table. Same pattern as migration 005.
--
-- Apply:    python -c "import sqlite3; sqlite3.connect('<db>').executescript(open('sql/migrations/006_xml_diff.sql').read())"
-- Verify:   PRAGMA foreign_key_check;                   -- expect empty
--           SELECT * FROM version_source WHERE source_type='xml_diff';  -- CHECK accepts new value

-- Step 1: New table with the extended CHECK (preserves every column of
-- version_source from sql/schema.sql lines 140–183 and adds 'xml_diff'
-- to the enum; 'js_bundle' from migration 005 is also retained).
CREATE TABLE version_source_new (
    version_source_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id              INTEGER NOT NULL REFERENCES asset(asset_id),
    source_type           TEXT NOT NULL
                          CHECK (source_type IN (
                              'github','github_release','api','rss','css_selector',
                              'android_store','ios_store','package_registry',
                              'changedetection_webhook','custom','manual',
                              'js_bundle','xml_diff'
                          )),
    source_url            TEXT,
    source_identifier     TEXT NOT NULL,
    check_method          TEXT NOT NULL,
    config                TEXT,
    enabled               INTEGER NOT NULL DEFAULT 1,
    check_interval        INTEGER NOT NULL DEFAULT 86400,
    on_error_policy       TEXT NOT NULL DEFAULT 'standard'
                          CHECK (on_error_policy IN (
                              'standard',
                              'retry_aggressive',
                              'trigger_discovery',
                              'alert_only',
                              'silent'
                          )),
    last_checked_at       TEXT,
    last_success_at       TEXT,
    last_error_at         TEXT,
    last_error_code       TEXT,
    last_error            TEXT,
    consecutive_failures  INTEGER NOT NULL DEFAULT 0,
    next_check_at         TEXT,
    UNIQUE(asset_id, source_type, check_method, source_identifier)
);

-- Step 2: Copy existing rows untouched (every prior value, including the
-- 'js_bundle' rows inserted after migration 005, is still accepted by
-- the new CHECK).
INSERT INTO version_source_new
    (version_source_id, asset_id, source_type, source_url, source_identifier,
     check_method, config, enabled, check_interval, on_error_policy,
     last_checked_at, last_success_at, last_error_at, last_error_code,
     last_error, consecutive_failures, next_check_at)
SELECT
    version_source_id, asset_id, source_type, source_url, source_identifier,
    check_method, config, enabled, check_interval, on_error_policy,
    last_checked_at, last_success_at, last_error_at, last_error_code,
    last_error, consecutive_failures, next_check_at
FROM version_source;

-- Step 3: Swap
DROP TABLE version_source;
ALTER TABLE version_source_new RENAME TO version_source;
