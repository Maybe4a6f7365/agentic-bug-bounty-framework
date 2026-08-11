---
name: version-tracker-add-target
description: "Add a new bug bounty target to the version-tracker database. Creates target, asset, and version_source rows in one step with deduplication."
category: bugbounty
---

# version-tracker-add-target

Add a new target and its version-checking sources to the database.

## Trigger

Load this skill when:
- User says "add a target" or "track this program"
- User provides a GitHub org URL or Play Store link and wants it monitored
- After scope import reveals a new program worth tracking

## Usage

Interactive: run the helper script.
```bash
python3 /var/lib/hermes/research/version-tracker/scripts/add_target.py
```

Or direct SQL for scripted use.

## What it does

1. Creates `target` row (if new)
2. For each attack vector type provided:
   - Checks `asset` for existing `(vector_type, canonical_identifier)` — reuses if found
   - Creates `asset` if new
   - Creates `target_asset` junction row
   - Creates `version_source` with the appropriate `source_type`, `check_method`, and `config` pattern
3. Reports what was created vs reused

## Deduplication

Before creating an `asset`, query:
```sql
SELECT asset_id FROM asset WHERE vector_type=? AND canonical_identifier=?
```
If found, reuse the existing `asset_id` and only create `target_asset`.

This is the structural fix the council required. Same repo tracked under multiple targets shares one `asset` row. No duplicate polling.

## Custom version sources

After adding a target, add custom checkers via SQL:
```sql
INSERT INTO version_source (asset_id, source_type, check_method, source_identifier, config)
VALUES (
    <asset_id>, 'custom', 'my_custom_checker', 'my-custom-source',
    '{"url": "https://api.example.com/version"}'
);
```
Custom checker script must exist at `checkers/custom/my_custom_checker.py`.
Template: `checkers/custom/_template.py` — copy and implement `check(config)`.

## Pitfalls

- GitHub canonical_identifier is `owner/repo` (no `https://github.com/` prefix). Normalize on input.
- Android package names are case-sensitive.
- Set `on_error_policy='trigger_discovery'` for RSS sources so re-discovery fires on FEED_GONE.
- For website targets (`source_type=css_selector` or `api`), run a pre-flight probe fetch to detect bot walls BEFORE committing the source. If blocked, load `bot-wall-escalation` to classify the wall and decide whether to proceed or use indirect signals (Play Store, App Store, RSS).
- Akamai-protected sites: version checks from this box will fail. Offer indirect alternatives on add.
