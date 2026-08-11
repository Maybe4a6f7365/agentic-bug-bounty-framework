"""scripts/fix_tags_field_path.py — operator-gated one-shot fixer.

Updates the `config` JSON column for `github/latest_tag` version_source rows
where the field is "name" (incorrect for the /tags endpoint, which returns
a JSON array). The fix is to set it to "[0].name", which is what
`_extract_field()` in checkers/builtin/github.py expects.

The fix mirrors the corrected `add_github_release_sources.py` so future
runs of that script also write the right field.

Idempotent: rows already with "[0].name" are skipped.

Dry-run by default. Pass --apply to write.
"""

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="Write to the DB (default: dry-run)")
    args = ap.parse_args()

    db_path = os.environ.get("VERSION_TRACKER_DB")
    if not db_path:
        print("VERSION_TRACKER_DB env var is required", file=sys.stderr)
        return 1

    if not args.apply:
        print("DRY-RUN: pass --apply to write changes.\n")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT version_source_id, source_type, source_url, config
            FROM version_source
            WHERE source_type = 'github'
              AND check_method = 'tags'
              AND config LIKE '%/tags%'
        """).fetchall()

        if not rows:
            print("No github/tags rows found; nothing to fix.")
            return 0

        fixed = 0
        skipped = 0
        for r in rows:
            vsid = r["version_source_id"]
            url = r["source_url"]
            cfg_str = r["config"]

            try:
                cfg = json.loads(cfg_str)
            except json.JSONDecodeError:
                print(f"  vs={vsid}  SKIP (config not JSON): {cfg_str[:60]}")
                skipped += 1
                continue

            field = cfg.get("field", "")
            if field == "[0].name":
                print(f"  vs={vsid}  ALREADY OK ({url})")
                skipped += 1
                continue
            if field != "name":
                print(f"  vs={vsid}  UNEXPECTED field={field!r}; leaving as-is")
                skipped += 1
                continue

            cfg["field"] = "[0].name"
            new_cfg_str = json.dumps(cfg, separators=(",", ":"))

            print(f"  vs={vsid}  {field!r} → '[0].name'  ({url})")
            if args.apply:
                conn.execute(
                    "UPDATE version_source SET config=? WHERE version_source_id=?",
                    [new_cfg_str, vsid],
                )
            fixed += 1

        if args.apply:
            conn.commit()
            print(f"\nCommitted. {fixed} rows fixed, {skipped} unchanged.")
        else:
            print(f"\nWould fix {fixed} rows. {skipped} unchanged.")
            print("Re-run with --apply to write.")

    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())