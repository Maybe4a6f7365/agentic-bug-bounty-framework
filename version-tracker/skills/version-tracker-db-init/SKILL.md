---
name: version-tracker-db-init
description: "Initialize the version-tracker SQLite database. Creates schema, indexes, and seed data. Run once per deployment."
category: bugbounty
---

# version-tracker-db-init

Initialize the version-tracking SQLite database from the canonical schema.

## Trigger

Load this skill when:
- Setting up the version tracker for the first time
- The database file is missing or corrupted
- The schema has been updated and needs re-creation
- User says "init the version tracker DB" or "create the tracking database"

## Schema

The canonical DDL lives at:
`/var/lib/hermes/research/version-tracker/sql/schema.sql`

It creates 16 tables: `bug_bounty_platform`, `bug_bounty_program`, `target`, `asset`, `target_asset`, `scope_record`, `scope_observation`, `scope_change_event`, `version_source`, `version_observation`, `version_change_event`, `error_classification`, `source`, `check_run`, `finding`, `research_note`.

Plus 12 error classification seed rows with auto-actions.

## Run

```bash
DB_PATH="${HOME}/.hermes/version-tracker/version_tracker.db"
mkdir -p "$(dirname "$DB_PATH")"
sqlite3 "$DB_PATH" < /var/lib/hermes/research/version-tracker/sql/schema.sql
echo "Database created at $DB_PATH"
sqlite3 "$DB_PATH" ".tables"
```

No pip install needed — sqlite3 is in Python stdlib and the system sqlite3 CLI.

## Verify

```bash
sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM error_classification;"
# Expected: 12

sqlite3 "$DB_PATH" "SELECT error_code, auto_action FROM error_classification ORDER BY error_code;"
# Expected: STORAGE_MOVED through UNKNOWN

sqlite3 "$DB_PATH" "PRAGMA foreign_keys; PRAGMA journal_mode;"
# Expected: foreign_keys=1, journal_mode=wal
```

## Pitfalls

- `PRAGMA foreign_keys = ON` must be set on every connection. The schema.sql does this, but ad-hoc sqlite3 CLI invocations won't.
- SQLite WAL mode allows concurrent readers during writes. Still avoid concurrent writers.
- Timestamps are ISO 8601 text (`2026-07-26T14:30:00Z`). Not a native type. Sort order is lexicographic, which is correct for ISO 8601.
- JSON is stored as TEXT. Use `json_extract(col, '$.key')` in queries.
- `BOOLEAN` → `INTEGER` (0/1). CHECK constraints enforce valid values.
