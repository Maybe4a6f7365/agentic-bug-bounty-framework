-- Migration 004: Retire the bot-wall escalation ladder.
--
-- Reverses migration 002. The escalation ladder (Playwright with
-- navigator.webdriver spoofing, ScrapingAnt rotating proxies, CapSolver
-- captcha solving) bypassed bot protection on program-owned assets. That
-- conflicts with SECURITY-RESEARCH-POLICY.md — which requires every request
-- to carry researcher-identification headers — and with the traffic
-- attribution programs rely on during triage. Rotating IPs and solving
-- challenges make authorized research indistinguishable from an attacker
-- and put the HackerOne account at risk.
--
-- Bot walls are still DETECTED: checkers continue to raise BOT_WALL on 403.
-- The response is now to stop, disable the source, and file a research_note
-- for a human to triage — auto_action='flag_for_review'.
--
-- Apply: sqlite3 ~/.hermes/version-tracker/version_tracker.db < sql/migrations/004_retire_bot_wall_escalation.sql
-- Verify: SELECT error_code, auto_action FROM error_classification
--           WHERE error_code LIKE 'BOT_WALL%' OR error_code = 'CAPTCHA_GATE';
--         SELECT COUNT(*) FROM error_classification WHERE auto_action='trigger_escalation';  -- expect 0
--         PRAGMA foreign_key_check;

-- Step 1: New table — 'trigger_escalation' dropped, 'flag_for_review' added
CREATE TABLE error_classification_new (
    error_class_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    error_code            TEXT NOT NULL UNIQUE,
    description           TEXT NOT NULL,
    is_transient          INTEGER NOT NULL,
    auto_action           TEXT NOT NULL DEFAULT 'log'
                          CHECK (auto_action IN (
                              'log','disable_source','trigger_discovery',
                              'alert_operator','flag_for_review'
                          )),
    discovery_prompt      TEXT,
    max_retries           INTEGER NOT NULL DEFAULT 3,
    created_at            TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Step 2: Copy, rewriting any escalation rows on the way through.
-- Done in the SELECT so the copy never violates the new CHECK constraint.
INSERT INTO error_classification_new
    (error_class_id, error_code, description, is_transient,
     auto_action, discovery_prompt, max_retries, created_at)
SELECT
    error_class_id,
    error_code,
    CASE
        WHEN auto_action = 'trigger_escalation'
        THEN 'Host is blocking automated access (WAF/CDN/bot manager). Not bypassed — flagged for manual review.'
        ELSE description
    END,
    is_transient,
    CASE WHEN auto_action = 'trigger_escalation' THEN 'flag_for_review' ELSE auto_action END,
    discovery_prompt,
    max_retries,
    created_at
FROM error_classification;

-- Step 3: BOT_WALL_UNSOLVABLE described a residential-proxy/2Captcha next
-- step we no longer take. Same outcome, honest description.
UPDATE error_classification_new
   SET description = 'Host persistently blocks automated access. Source disabled — review by hand.',
       auto_action = 'flag_for_review'
 WHERE error_code = 'BOT_WALL_UNSOLVABLE';

-- Step 4: Ensure both codes exist for DBs created before migration 002
INSERT OR IGNORE INTO error_classification_new
    (error_code, description, is_transient, auto_action, max_retries) VALUES
    ('BOT_WALL',
     'Host is blocking automated access (WAF/CDN/bot manager)',
     0, 'flag_for_review', 2),
    ('CAPTCHA_GATE',
     'Interactive captcha gate. Not solved — needs manual review',
     0, 'flag_for_review', 1);

-- Step 5: Swap
DROP TABLE error_classification;
ALTER TABLE error_classification_new RENAME TO error_classification;

-- Step 6: Re-enable any source disabled purely because the ladder gave up.
-- They get one honest, identified retry; if the wall is real they will land
-- on flag_for_review and be disabled again with a note.
UPDATE version_source
   SET enabled = 1, consecutive_failures = 0, next_check_at = NULL
 WHERE enabled = 0
   AND last_error_code IN ('BOT_WALL', 'BOT_WALL_UNSOLVABLE', 'CAPTCHA_GATE');

PRAGMA foreign_key_check;
