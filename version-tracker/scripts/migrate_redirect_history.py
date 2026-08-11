#!/usr/bin/env python3
"""scripts/migrate_redirect_history.py — operator-gated migration script.

Walks every enabled version_source row in the live DB and probes its
configured source_url with `http_cache.fetch(follow_redirects=False)`. On
3xx with a Location header, calls `redirect_recorder.record_redirect` to
keep the original row (status=redirected) and insert a new row at the
Location target. On 200 OK, no-op. On 404/410, no-op (the existing
auto-disable path handles that).

Operator-gated: --apply required for any DB writes. Default mode is
--dry-run which prints the planned migrations.

Usage:
    VERSION_TRACKER_DB=/opt/data/.hermes/version-tracker/version_tracker.db \\
        python3 scripts/migrate_redirect_history.py --dry-run

    # Re-run with --apply after reviewing dry-run output:
    VERSION_TRACKER_DB=/opt/data/.hermes/version-tracker/version_tracker.db \\
        python3 scripts/migrate_redirect_history.py --apply

This script makes HTTPS calls to the configured URLs. It does NOT poll
recurrently; one-shot discovery only.
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from checkers import http_cache  # noqa: E402
from checkers import redirect_recorder  # noqa: E402


def _connect_db(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def probe_url(url: str, timeout: int = 15):
    """Probe a single URL. Returns:
      ('ok', body_summary)  — 200 or 304, no redirect
      ('redirect', location_str)  — 3xx with Location
      ('gone', code_int)   — 404 / 410 (auto-disable territory)
      ('error', message)   — anything else
    """
    try:
        raw = http_cache.fetch(
            url,
            headers={
                "User-Agent": "version-tracker-migrate-redirect-history/1.0",
                "Accept": "*/*",
            },
            timeout=timeout,
            follow_redirects=False,
        )
        if raw is None:
            return ("ok", "304 Not Modified")
        return ("ok", "200 OK")
    except http_cache.RedirectBlockedError as e:
        # type: ignore[return-value] -- probe_url returns (str, str)
        return ("redirect", str(e.location))
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            return ("gone", int(e.code))
        return ("error", f"HTTP {e.code}")
    except Exception as e:
        return ("error", str(e)[:120])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="Apply the migration (default: dry-run)")
    ap.add_argument("--dry-run", action="store_true",
                    help="(default) Print the planned migrations, do not write")
    ap.add_argument("--limit", type=int, default=None,
                    help="Limit the number of sources to probe")
    args = ap.parse_args()

    db_path = os.environ.get(
        "VERSION_TRACKER_DB",
        os.path.expanduser("~/.hermes/version-tracker/version_tracker.db"),
    )
    if not Path(db_path).exists():
        print(f"DB not found: {db_path}", file=sys.stderr)
        return 1

    conn = _connect_db(db_path)
    try:
        rows = conn.execute(
            """SELECT vs.version_source_id, vs.source_url, vs.asset_id,
                      vs.source_type, vs.check_method, vs.status,
                      a.canonical_identifier
               FROM version_source vs
               JOIN asset a ON a.asset_id = vs.asset_id
               WHERE vs.enabled = 1 AND vs.source_url IS NOT NULL
                 AND vs.status = 'active'
               ORDER BY vs.version_source_id""",
        ).fetchall()
        if args.limit:
            rows = rows[: args.limit]

        print(f"Probing {len(rows)} enabled source_url(s) ...")
        redirects_found = 0
        ok_count = 0
        errors = 0
        applied = 0

        for row in rows:
            url = row["source_url"]
            probe_result = probe_url(url)
            result = probe_result[0]
            info: str = probe_result[1] if isinstance(probe_result[1], str) else str(probe_result[1])
            label = f"vs={row['version_source_id']:3} {row['canonical_identifier']:30} {row['source_url']}"
            if result == "redirect":
                redirects_found += 1
                print(f"  [REDIRECT]  {label}")
                print(f"              -> {info}")
                if args.apply:
                    new_id = redirect_recorder.record_redirect(
                        conn,
                        old_source_id=row["version_source_id"],
                        http_status=302,
                        location=info,
                        check_run_id=None,
                    )
                    conn.commit()
                    applied += 1
                    print(f"              (recorded: new vs={new_id})")
            elif result == "ok":
                ok_count += 1
                print(f"  [OK]        {label}")
            elif result == "gone":
                ok_count += 1  # leave the existing auto-disable path to handle
                print(f"  [GONE]      {label} (HTTP {info})")
            else:
                errors += 1
                print(f"  [ERR]       {label} ({info})")

        print()
        print(f"Summary: {ok_count} ok, {redirects_found} redirect(s), {errors} error(s)")
        if args.apply:
            print(f"  applied: {applied} redirect(s) recorded.")
        else:
            print("  DRY-RUN. Re-run with --apply to write to the DB.")

    finally:
        conn.close()
    return 0


# urllib.error.HTTPError is referenced inside probe_url but the import is
# deferred to keep the top-level namespace clean.
import urllib.error  # noqa: E402


if __name__ == "__main__":
    sys.exit(main())