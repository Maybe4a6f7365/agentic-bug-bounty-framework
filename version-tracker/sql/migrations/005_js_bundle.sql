-- Migration 005: add 'js_bundle' to version_source.source_type CHECK
--
-- Adds the 'js_bundle' enum value used by the new
-- checkers/builtin/js_bundle.py checker (Task 0.3 / Phase 1).
--
-- SQLite doesn't support ALTER TABLE ... ALTER COLUMN to change CHECK
-- constraints, so we rebuild the table. The pattern mirrors migration 004.
--
-- Apply:    python -c "import sqlite3; sqlite3.connect('<db>').executescript(open('sql/migrations/005_js_bundle.sql').read())"
-- Verify:   PRAGMA foreign_key_check;                   -- expect empty
--           SELECT * FROM version_source WHERE source_type='js_bundle';  -- CHECK accepts new value

-- Step 1: New table with the extended CHECK (preserves every column of
-- version_source from sql/schema.sql and adds 'js_bundle' to the enum).
-- Column list is kept in lockstep with sql/schema.sql lines 140–183.
CREATE TABLE version_source_new (
    version_source_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id              INTEGER NOT NULL REFERENCES asset(asset_id),
    source_type           TEXT NOT NULL
                          CHECK (source_type IN (
                              'github','github_release','api','rss','css_selector',
                              'android_store','ios_store','package_registry',
                              'changedetection_webhook','custom','manual',
                              'js_bundle'
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

-- Step 2: Copy existing rows untouched. Every row in the prior 11-value
-- enum is still accepted by the new CHECK, so no rewrite is needed.
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

-- Step 4: FK integrity check — must be run inside the same connection
-- (PRAGMA foreign_key_check;) by the executor; SQLite CHECK extensions
-- alone cannot catch orphaned references.
