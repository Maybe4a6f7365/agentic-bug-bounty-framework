---
name: version-tracker-daily-check
description: "Run the daily version check across all enabled version sources. SQLite-backed. Dispatches to builtin or custom checkers. On error, classifies failure and may trigger re-discovery or auto-disable the source."
category: bugbounty
---

# version-tracker-daily-check

Run the daily version-check sweep across all enabled sources.

## Trigger

Load this skill when:
- User says "check versions" or "run the daily check"
- Setting up a cron job for automated monitoring
- A checker error triggered re-discovery and you need to run discovery
- User wants to know what changed in the last 24h

## Architecture

```
version_source rows (enabled=1, due for check)
        │
        ▼
  checkers/runner.py  (single writer, sequential)
        │
        ├── source_type='github' ──────────► checkers/builtin/github.py
        ├── source_type='github_release' ───► checkers/builtin/github.py
        ├── source_type='rss' ──────────────► checkers/builtin/rss.py
        ├── source_type='api' ──────────────► checkers/builtin/api_json.py
        ├── source_type='css_selector' ─────► checkers/builtin/css_selector.py
        └── source_type='custom' ───────────► checkers/custom/<check_method>.py
                │
                ▼
         version_observation + version_change_event (on change)
         check_run (always)
         error_classification → auto_action (on failure)
```

## Run

```bash
cd /var/lib/hermes/research/version-tracker
python3 checkers/runner.py
```

No virtualenv needed — uses only stdlib (`sqlite3`, `urllib`, `importlib`, `json`, `hashlib`, `xml.etree`). Optional: `pip install beautifulsoup4` for the css_selector checker.

## Database

SQLite at `~/.hermes/version-tracker/version_tracker.db`.
WAL mode enabled — concurrent readers OK during writes.
Override: `VERSION_TRACKER_DB=/path/to/db python3 checkers/runner.py`

## Error handling (self-healing)

On failure, the runner:
1. Writes `check_run` with `status='failure'` + `error_code`
2. Looks up `error_classification` for the error code
3. Increments `version_source.consecutive_failures`
4. If `consecutive_failures >= error_classification.max_retries`:
   - `auto_action='disable_source'` → sets `enabled=0`
   - `auto_action='trigger_discovery'` → disables source AND prints re-discovery prompt
   - `auto_action='flag_for_review'` → disables source AND writes a research_note for human triage
   - `auto_action='alert_operator'` → logs for operator review

Error codes that trigger re-discovery:
- STORAGE_MOVED (1 failure) — changelog URL returned 301/404
- PAGE_STRUCTURE (2 failures) — HTML selector no longer matches
- FEED_GONE (1 failure) — RSS feed no longer serves XML
- PARSE_ERROR (3 failures) — response structure changed
- EMPTY_RESPONSE (2 failures) — response body empty

Error codes that flag for human review (bot walls are never bypassed):
- BOT_WALL (2 failures) — WAF/CDN/bot manager is blocking automated access.
- CAPTCHA_GATE (1 failure) — interactive captcha. Not solved.
- BOT_WALL_UNSOLVABLE (migrated DBs only) — same handling.

All three disable the source and file a `research_note`. To act on one, find a
documented feed/API for the asset, check it by hand, or drop it — do not proxy
around the wall.

## Morning briefing query

```sql
SELECT vec.change_type, vec.detected_at, vec.research_status,
       a.canonical_identifier, a.vector_type,
       t.canonical_name AS target,
       vs.source_type, vs.check_method
FROM version_change_event vec
JOIN asset a ON a.asset_id = vec.asset_id
JOIN target_asset ta ON ta.asset_id = a.asset_id AND ta.is_current = 1
JOIN target t ON t.target_id = ta.target_id
JOIN version_source vs ON vs.version_source_id = vec.version_source_id
WHERE vec.research_status = 'new'
ORDER BY vec.detected_at DESC;
```

## Cron schedule

```text
Schedule: 0 */6 * * *
Prompt: "Load skill version-tracker-daily-check. Run python3 checkers/runner.py. Then query version_change_event WHERE research_status='new' and report what changed."
Skills: [version-tracker-daily-check]
```

## Pitfalls

- The runner is sequential. Many sources = long runtime. Start with a small set.
- Checkers read `config` JSON from the database. The lookup pattern IS in the DB.
- Custom checkers load dynamically via importlib. Syntax error → only that source fails.
- `consecutive_failures` resets to 0 on next success. Intermittent failures are OK.
