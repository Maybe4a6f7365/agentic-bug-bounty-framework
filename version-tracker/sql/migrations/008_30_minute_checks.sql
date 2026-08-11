-- Migration 008: check every enabled version source every 30 minutes.
--
-- The scheduler cadence and source due cadence are independent. A */30 cron
-- still skips rows whose check_interval remains 86400, so update the live rows
-- as well as the creation defaults in schema/add_target/enrich.
--
-- Disabled sources retain their explicit cadence. Sources already in failure
-- backoff retain next_check_at so migration never collapses exponential retry
-- delays. Never-checked healthy sources keep a NULL next_check_at so the runner
-- treats them as immediately due. Reapplying this migration is safe and
-- produces the same values.

BEGIN TRANSACTION;

UPDATE version_source
SET check_interval = 1800,
    next_check_at = CASE
        WHEN consecutive_failures > 0 THEN next_check_at
        WHEN last_checked_at IS NULL THEN NULL
        ELSE datetime(last_checked_at, '+1800 seconds')
    END
WHERE enabled = 1;

COMMIT;
