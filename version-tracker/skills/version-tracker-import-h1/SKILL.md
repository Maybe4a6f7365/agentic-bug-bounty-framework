---
name: version-tracker-import-h1
description: Import HackerOne scope data from arkadiyt/bounty-targets-data JSON into the version-tracker database. Seeds programs, assets, and scope records. Run to bootstrap the target inventory before version checking can begin.
category: bugbounty
---

# version-tracker-import-h1

Import the HackerOne program/scope dataset into the version-tracker SQLite database.

Source: `https://raw.githubusercontent.com/arkadiyt/bounty-targets-data/main/data/hackerone_data.json`

## Trigger

Load this skill when:
- Initializing the target inventory from HackerOne data
- Refreshing scope data (daily/weekly)
- User says "import H1 programs" or "pull in bounty targets data"

## Prerequisites

- Database initialized: `sqlite3 $DB_PATH < schema.sql` (use `version-tracker-db-init`)

## Run

The importer script is at:
`/var/lib/hermes/research/version-tracker/importers/import_h1.py`

```bash
cd /var/lib/hermes/research/version-tracker
python3 importers/import_h1.py
```

## What it does

1. Downloads the JSON from the arkadiyt repo
2. Computes a content hash — if unchanged from the last `source` row, skips entirely
3. For each program in the JSON:
   - Upserts `bug_bounty_platform` (slug='hackerone')
   - Upserts `bug_bounty_program` (keyed on platform_id + external_handle)
   - For each target in `in_scope` / `out_of_scope`:
     - Upserts `scope_record` (keyed on program_id + asset_identifier + asset_type)
     - Creates `scope_observation` with the raw JSON snapshot
     - Detects changes vs previous scope state → writes `scope_change_event`
4. Writes a `source` row with provenance

## Mapping

| JSON field | DB column |
|---|---|
| `handle` | `bug_bounty_program.external_handle` |
| `name` | `bug_bounty_program.name` |
| `url` | `bug_bounty_program.program_url` |
| `website` | `target.main_site_url` (creates target row) |
| `submission_state` | `bug_bounty_program.program_status` |
| `offers_bounties` | `bug_bounty_program.offers_bounties` |
| `managed_program` | `bug_bounty_program.managed_program` |
| `targets.in_scope[].asset_identifier` | `scope_record.asset_identifier` |
| `targets.in_scope[].asset_type` | `scope_record.asset_type` |
| `targets.in_scope[].eligible_for_bounty` | `scope_record.eligible_for_bounty` |
| `targets.in_scope[].eligible_for_submission` | `scope_record.eligible_for_submission` |
| `targets.in_scope[].instruction` | `scope_record.instruction` |

Unmapped fields → `source.raw_payload` as the full program JSON.

## Scope change detection

After importing, the importer compares each scope row against the previous state:
- New `asset_identifier` in the program → `scope_change_event.change_type='asset_added'`
- Removed `asset_identifier` → `scope_change_event.change_type='asset_removed'`
- Changed `eligible_for_bounty` status → `scope_change_event.change_type='eligibility_changed'`
- Changed `instruction` → `scope_change_event.change_type='instruction_changed'`

## Pitfalls

- The JSON is ~15MB. First import takes ~10-15 seconds.
- `hackerone_data.json` has `id: 0` on every record — do NOT use it as a stable key.
- Some programs have 500+ scope entries. The importer uses batch inserts for performance.
- SQLite WAL mode: concurrent readers OK during writes, but avoid concurrent writes.
- The dataset may be stale (updated daily by arkadiyt). Verify timeliness before trusting scope data.
