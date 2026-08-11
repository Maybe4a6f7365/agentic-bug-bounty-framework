-- Migration 002: Add bot-wall escalation support
-- Expands error_classification auto_action CHECK constraint to include 'trigger_escalation'
-- Adds BOT_WALL, BOT_WALL_UNSOLVABLE, CAPTCHA_GATE error codes
--
-- SQLite doesn't support ALTER TABLE ... ALTER COLUMN to change CHECK constraints,
-- so we rebuild the table.
--
-- Apply: sqlite3 ~/.hermes/version-tracker/version_tracker.db < sql/migrations/002_bot_wall_escalation.sql
-- Verify: SELECT * FROM error_classification WHERE auto_action='trigger_escalation';
--         PRAGMA foreign_key_check;

-- Step 1: Create new table with expanded CHECK
CREATE TABLE error_classification_new (
    error_class_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    error_code            TEXT NOT NULL UNIQUE,
    description           TEXT NOT NULL,
    is_transient          INTEGER NOT NULL,
    auto_action           TEXT NOT NULL DEFAULT 'log'
                          CHECK (auto_action IN (
                              'log','disable_source','trigger_discovery',
                              'trigger_escalation','alert_operator'
                          )),
    discovery_prompt      TEXT,
    max_retries           INTEGER NOT NULL DEFAULT 3,
    created_at            TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Step 2: Copy existing data
INSERT INTO error_classification_new SELECT * FROM error_classification;

-- Step 3: Add new bot-wall error codes
INSERT INTO error_classification_new (error_code, description, is_transient, auto_action, max_retries) VALUES
    ('BOT_WALL',
     'Bot wall detected (captcha, WAF, or CDN block). Escalation ladder will attempt bypass.',
     0, 'trigger_escalation', 1),
    ('BOT_WALL_UNSOLVABLE',
     'Bot wall classified as unsolvable on-box. Needs residential proxy or 2Captcha.',
     0, 'disable_source', 3),
    ('CAPTCHA_GATE',
     'Interactive captcha (hCaptcha/reCAPTCHA) detected. CapSolver will be attempted.',
     0, 'trigger_escalation', 2);

-- Step 4: Swap tables
DROP TABLE error_classification;
ALTER TABLE error_classification_new RENAME TO error_classification;

-- Step 5: Verify FK integrity
PRAGMA foreign_key_check;
