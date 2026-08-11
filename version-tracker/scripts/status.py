#!/usr/bin/env python3
"""
scripts/status.py — One-screen dashboard for the version-tracker pipeline.

Shows: programs, assets, version sources, linkage health, recent changes,
       checker health, and last runner batch.

Usage:
  python3 scripts/status.py              # Full dashboard
  python3 scripts/status.py --short      # Compact summary
  python3 scripts/status.py --changes    # Only recent version changes
  python3 scripts/status.py --health     # Only checker health
"""

import os
import sqlite3
import sys
from datetime import datetime, timezone

DB_PATH = os.environ.get(
    "VERSION_TRACKER_DB",
    os.path.expanduser("~/.hermes/version-tracker/version_tracker.db"),
)

SEP = "─" * 60
THIN = "─" * 40


def _connect() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA journal_mode = WAL")
    db.row_factory = sqlite3.Row
    return db


def _fmt_pct(n: int, total: int) -> str:
    if total == 0:
        return "—"
    return f"{n * 100 // total}%"


def _fmt_since(ts: str | None) -> str:
    if not ts:
        return "never"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - dt
        hours = int(delta.total_seconds() / 3600)
        if hours < 1:
            return f"{int(delta.total_seconds()/60)}m ago"
        if hours < 24:
            return f"{hours}h ago"
        return f"{hours // 24}d ago"
    except (ValueError, TypeError):
        return "?"


def section(title: str):
    print(f"\n  {title}")
    print(f"  {THIN}")


def programs(db: sqlite3.Connection):
    section("PROGRAMS")
    total = db.execute("SELECT COUNT(*) FROM bug_bounty_program").fetchone()[0]
    active = db.execute(
        "SELECT COUNT(*) FROM bug_bounty_program WHERE program_status='open'"
    ).fetchone()[0]
    with_scope = db.execute(
        "SELECT COUNT(DISTINCT program_id) FROM scope_record WHERE scope_status='in_scope'"
    ).fetchone()[0]
    enriched = db.execute(
        """SELECT COUNT(DISTINCT sr.program_id)
           FROM scope_record sr
           WHERE sr.scope_status='in_scope' AND sr.asset_id IS NOT NULL"""
    ).fetchone()[0]
    unlinked = db.execute(
        """SELECT COUNT(*) FROM scope_record
           WHERE scope_status='in_scope' AND asset_id IS NULL"""
    ).fetchone()[0]

    print(f"  Total programs:   {total}")
    print(f"  Active (open):    {active}")
    print(f"  With scope:       {with_scope}")
    print(f"  Scope enriched:   {enriched} / {with_scope} programs ({_fmt_pct(enriched, max(with_scope,1))})")
    print(f"  Scope unlinked:   {unlinked} records")


def assets(db: sqlite3.Connection):
    section("ASSETS")
    rows = db.execute(
        """SELECT vector_type, COUNT(*) as cnt
           FROM asset
           GROUP BY vector_type
           ORDER BY cnt DESC"""
    ).fetchall()
    total = sum(r["cnt"] for r in rows)
    print(f"  Total: {total}")
    for r in rows:
        bar = "█" * min(r["cnt"], 40)
        print(f"  {r['vector_type']:22s} {r['cnt']:5d}  {bar}")


def version_sources(db: sqlite3.Connection):
    section("VERSION SOURCES")
    by_type = db.execute(
        """SELECT source_type, COUNT(*) as cnt,
                  SUM(CASE WHEN enabled=1 THEN 1 ELSE 0 END) as enabled,
                  MAX(last_checked_at) as last_check
           FROM version_source
           GROUP BY source_type
           ORDER BY cnt DESC"""
    ).fetchall()
    total = sum(r["cnt"] for r in by_type)
    print(f"  Total: {total} ({sum(r['enabled'] for r in by_type)} enabled)")
    for r in by_type:
        marker = "✓" if r["enabled"] == r["cnt"] else f"{r['enabled']}/{r['cnt']}"
        print(f"  {r['source_type']:22s} {r['cnt']:5d}  enabled={marker:8s}  last={_fmt_since(r['last_check'])}")


def linkage(db: sqlite3.Connection):
    section("LINKAGE HEALTH")
    total_scope = db.execute(
        "SELECT COUNT(*) FROM scope_record WHERE scope_status='in_scope'"
    ).fetchone()[0]
    linked = db.execute(
        "SELECT COUNT(*) FROM scope_record WHERE scope_status='in_scope' AND asset_id IS NOT NULL"
    ).fetchone()[0]
    total_assets = db.execute("SELECT COUNT(*) FROM asset").fetchone()[0]
    total_sources = db.execute("SELECT COUNT(*) FROM version_source").fetchone()[0]
    assets_with_sources = db.execute(
        "SELECT COUNT(DISTINCT asset_id) FROM version_source"
    ).fetchone()[0]

    print(f"  Scope → Asset:    {linked}/{total_scope} linked ({_fmt_pct(linked, max(total_scope,1))})")
    print(f"  Assets w/ sources:{assets_with_sources}/{total_assets} ({_fmt_pct(assets_with_sources, max(total_assets,1))})")
    print(f"  Assets:           {total_assets}")
    print(f"  Version sources:  {total_sources}")


def recent_changes(db: sqlite3.Connection):
    section("RECENT CHANGES (research_status='new')")
    rows = db.execute(
        """SELECT vec.version_change_id, vec.change_type, vec.detected_at,
                  a.canonical_identifier, a.vector_type,
                  t.canonical_name as target,
                  vs.source_type, vs.check_method
           FROM version_change_event vec
           JOIN asset a ON a.asset_id = vec.asset_id
           LEFT JOIN target_asset ta ON ta.asset_id = a.asset_id AND ta.is_current = 1
           LEFT JOIN target t ON t.target_id = ta.target_id
           JOIN version_source vs ON vs.version_source_id = vec.version_source_id
           WHERE vec.research_status = 'new'
           ORDER BY vec.detected_at DESC
           LIMIT 10"""
    ).fetchall()

    if not rows:
        print("  (none)")
        return

    for r in rows:
        tgt = r["target"] or "?"
        print(f"  [{r['detected_at'][:16]}] {r['change_type']:28s} "
              f"{r['canonical_identifier'][:40]:40s} ({tgt})")


def checker_health(db: sqlite3.Connection):
    section("CHECKER HEALTH")
    failing = db.execute(
        """SELECT vs.version_source_id, vs.source_type, vs.check_method,
                  vs.consecutive_failures, vs.last_error_code, vs.source_url,
                  a.canonical_identifier
           FROM version_source vs
           JOIN asset a ON a.asset_id = vs.asset_id
           WHERE vs.consecutive_failures > 0 AND vs.enabled = 1
           ORDER BY vs.consecutive_failures DESC
           LIMIT 10"""
    ).fetchall()

    disabled = db.execute(
        """SELECT COUNT(*) FROM version_source WHERE enabled = 0"""
    ).fetchone()[0]

    if failing:
        print(f"  Sources with errors: {len(failing)} (showing up to 10)")
        for r in failing:
            print(f"  [{r['consecutive_failures']}x fail] {r['canonical_identifier'][:45]:45s} "
                  f"{r['source_type']}:{r['check_method']}  ({r['last_error_code']})")
    else:
        print("  No active sources with errors.")

    if disabled:
        print(f"  Disabled sources:   {disabled}")


def last_runner(db: sqlite3.Connection):
    section("LAST RUNNER BATCH")
    row = db.execute(
        """SELECT batch_id, started_at, finished_at,
                  COUNT(*) as total,
                  SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) as success,
                  SUM(CASE WHEN changed=1 THEN 1 ELSE 0 END) as changed,
                  MAX(finished_at) as last_finish
           FROM check_run
           GROUP BY batch_id
           ORDER BY started_at DESC
           LIMIT 1"""
    ).fetchone()

    if not row:
        print("  No check runs yet.")
        return

    print(f"  Batch:     {row['batch_id']}")
    print(f"  Started:   {row['started_at'][:19]}")
    print(f"  Finished:  {row['last_finish'][:19] if row['last_finish'] else 'incomplete'}")
    print(f"  Sources:   {row['total']} total, {row['success']} success, {row['changed']} changed")


def db_info(db: sqlite3.Connection):
    size_mb = os.path.getsize(DB_PATH) / (1024 * 1024)
    tables = db.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
    ).fetchone()[0]
    print(f"\n  DB: {DB_PATH} ({size_mb:.1f} MB, {tables} tables)")


def short(db: sqlite3.Connection):
    """Compact summary — one glance."""
    total_scope = db.execute(
        "SELECT COUNT(*) FROM scope_record WHERE scope_status='in_scope'"
    ).fetchone()[0]
    linked = db.execute(
        "SELECT COUNT(*) FROM scope_record WHERE scope_status='in_scope' AND asset_id IS NOT NULL"
    ).fetchone()[0]
    total_assets = db.execute("SELECT COUNT(*) FROM asset").fetchone()[0]
    total_sources = db.execute("SELECT COUNT(*) FROM version_source").fetchone()[0]
    enabled_sources = db.execute(
        "SELECT COUNT(*) FROM version_source WHERE enabled=1"
    ).fetchone()[0]
    new_changes = db.execute(
        "SELECT COUNT(*) FROM version_change_event WHERE research_status='new'"
    ).fetchone()[0]

    programs = db.execute("SELECT COUNT(*) FROM bug_bounty_program").fetchone()[0]
    enriched_progs = db.execute(
        """SELECT COUNT(DISTINCT sr.program_id)
           FROM scope_record sr
           WHERE sr.scope_status='in_scope' AND sr.asset_id IS NOT NULL"""
    ).fetchone()[0]

    print(f"  Programs: {programs} ({enriched_progs} enriched)\t"
          f"Scope→Asset: {linked}/{total_scope} ({_fmt_pct(linked, max(total_scope,1))})")
    print(f"  Assets: {total_assets}\tSources: {total_sources} ({enabled_sources} enabled)\t"
          f"Changes (new): {new_changes}")


def main():
    short_mode = False
    changes_only = False
    health_only = False

    for arg in sys.argv[1:]:
        if arg in ("--short", "-s"):
            short_mode = True
        elif arg == "--changes":
            changes_only = True
        elif arg == "--health":
            health_only = True
        elif arg in ("--help", "-h"):
            print(__doc__)
            sys.exit(0)

    db = _connect()
    try:
        if changes_only:
            db_info(db)
            recent_changes(db)
        elif health_only:
            db_info(db)
            checker_health(db)
        elif short_mode:
            db_info(db)
            short(db)
        else:
            db_info(db)
            short(db)
            programs(db)
            assets(db)
            version_sources(db)
            linkage(db)
            recent_changes(db)
            checker_health(db)
            last_runner(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
