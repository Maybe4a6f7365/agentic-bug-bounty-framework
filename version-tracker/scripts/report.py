#!/usr/bin/env python3
"""
scripts/report.py — Post-check summary for the version-tracker.

Usage:
  python3 scripts/report.py                          # latest batch
  python3 scripts/report.py --target "Plaid"         # filter by target
  python3 scripts/report.py --batch-id 20260727-...  # specific batch
  python3 scripts/report.py --failures-only          # only failures
  python3 scripts/report.py --fingerprints-only      # only fingerprint-only entries
"""

import argparse
import os
import sqlite3
import sys

DB_PATH = os.environ.get(
    "VERSION_TRACKER_DB",
    os.path.expanduser("~/.hermes/version-tracker/version_tracker.db"),
)


def connect():
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA foreign_keys = ON")
    db.row_factory = sqlite3.Row
    return db


def get_latest_batch(db):
    row = db.execute(
        "SELECT batch_id, started_at FROM check_run ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
    return row["batch_id"] if row else None


def summary(db, batch_id, target_filter):
    """Print summary stats."""
    where = "WHERE cr.batch_id = ?"
    params = [batch_id]

    if target_filter:
        where += " AND t.canonical_name = ?"
        params.append(target_filter)

    row = db.execute(
        f"""SELECT
               COUNT(DISTINCT cr.version_source_id) AS total,
               SUM(CASE WHEN cr.status = 'success' THEN 1 ELSE 0 END) AS ok,
               SUM(CASE WHEN cr.status = 'failure' THEN 1 ELSE 0 END) AS failed,
               SUM(CASE WHEN cr.status = 'success' AND vo.version_value LIKE 'fp:%' THEN 1 ELSE 0 END) AS fingerprints
            FROM check_run cr
            JOIN version_source vs ON vs.version_source_id = cr.version_source_id
            JOIN asset a ON a.asset_id = vs.asset_id
            JOIN target_asset ta ON ta.asset_id = a.asset_id AND ta.is_current = 1
            JOIN target t ON t.target_id = ta.target_id
            LEFT JOIN version_observation vo ON vo.version_source_id = cr.version_source_id AND vo.is_current = 1
            {where}""",
        params,
    ).fetchone()

    total = row["total"] or 0
    ok_count = row["ok"] or 0
    failed = row["failed"] or 0
    fp_count = row["fingerprints"] or 0
    real_versions = ok_count - fp_count

    print()
    print("═══ VERSION-TRACKER REPORT ═══")
    print(f"  Batch:      {batch_id}")
    if target_filter:
        print(f"  Target:     {target_filter}")
    print(f"  Checked:    {total} sources")
    print(f"  Baselines:  {ok_count}  ({real_versions} versioned, {fp_count} fingerprint-only)")
    print(f"  Failures:   {failed}")
    print()
    return total, ok_count, failed, fp_count


def baselines(db, batch_id, target_filter, fingerprints_only=False):
    """Print baselines table."""
    where = "WHERE cr.batch_id = ? AND cr.status = 'success'"
    params = [batch_id]

    if target_filter:
        where += " AND t.canonical_name = ?"
        params.append(target_filter)

    if fingerprints_only:
        where += " AND vo.version_value LIKE 'fp:%'"
    else:
        where += " AND vo.version_value NOT LIKE 'fp:%'"

    rows = db.execute(
        f"""SELECT vs.source_type, vs.source_identifier, vo.version_value,
                   a.vector_type, t.canonical_name as target
            FROM check_run cr
            JOIN version_source vs ON vs.version_source_id = cr.version_source_id
            JOIN asset a ON a.asset_id = vs.asset_id
            LEFT JOIN version_observation vo ON vo.version_source_id = cr.version_source_id AND vo.is_current = 1
            JOIN target_asset ta ON ta.asset_id = a.asset_id AND ta.is_current = 1
            JOIN target t ON t.target_id = ta.target_id
            {where}
            ORDER BY vs.source_type, t.canonical_name, vs.source_identifier""",
        params,
    ).fetchall()

    if not rows:
        print("  (none)")
        return

    title = "FINGERPRINT-ONLY" if fingerprints_only else "BASELINES (versioned)"
    print(f"─── {title} ───")
    print(f"  {'source_type':<16s} {'target':<22s} {'identifier':<44s} version")
    print(f"  {'─'*16} {'─'*22} {'─'*44} {'─'*40}")

    for r in rows:
        v = (r["version_value"] or "")[:60]
        t = (r["target"] or "")[:22]
        sid = r["source_identifier"][:44]
        print(f"  {r['source_type']:<16s} {t:<22s} {sid:<44s} {v}")

    print(f"  ({len(rows)} entries)")
    print()


def failures(db, batch_id, target_filter):
    """Print failures table with suggested fixes."""
    where = "WHERE cr.batch_id = ? AND cr.status = 'failure'"
    params = [batch_id]

    if target_filter:
        where += " AND t.canonical_name = ?"
        params.append(target_filter)

    rows = db.execute(
        f"""SELECT vs.source_type, vs.source_identifier, cr.error_code, cr.error_message,
                   t.canonical_name as target
            FROM check_run cr
            JOIN version_source vs ON vs.version_source_id = cr.version_source_id
            JOIN asset a ON a.asset_id = vs.asset_id
            JOIN target_asset ta ON ta.asset_id = a.asset_id AND ta.is_current = 1
            JOIN target t ON t.target_id = ta.target_id
            {where}
            ORDER BY cr.error_code, vs.source_type, vs.source_identifier""",
        params,
    ).fetchall()

    if not rows:
        print("  (none)")
        return

    FIXES = {
        "AUTH_REQUIRED": "Needs cookie auth — export browser cookies, set config.auth.cookies_file",
        "STORAGE_MOVED": "Endpoint moved or doesn't exist. Check if repo has releases/tags. Tags source still works as fallback.",
        "FEED_GONE": "RSS/Atom feed removed. Disable source or switch to CSS selector.",
        "RATE_LIMITED": "Too many requests. Increase --per-domain-delay or add GITHUB_TOKEN.",
        "TIMEOUT": "Network timeout. Retry with higher timeout or check connectivity.",
        "EMPTY_RESPONSE": "Server returned empty body. Check URL or add authentication.",
        "PARSE_ERROR": "Config or response format issue. Check config JSON and endpoint.",
        "UNKNOWN": "Unclassified error. Check error_message for details.",
    }

    print("─── FAILURES ───")
    print(f"  {'source_type':<16s} {'target':<22s} {'error_code':<20s} {'identifier':<44s}")
    print(f"  {'─'*16} {'─'*22} {'─'*20} {'─'*44}")

    for r in rows:
        t = (r["target"] or "")[:22]
        sid = r["source_identifier"][:44]
        ec = (r["error_code"] or "?")[:20]
        print(f"  {r['source_type']:<16s} {t:<22s} {ec:<20s} {sid}")

    print(f"  ({len(rows)} failures)")
    print()

    # Suggested fixes
    seen_codes = set(r["error_code"] for r in rows if r["error_code"])
    if seen_codes:
        print("  Suggested fixes:")
        for code in sorted(seen_codes):
            if code in FIXES:
                print(f"    {code}: {FIXES[code]}")
        print()


def notable_gaps(db, batch_id, target_filter):
    """Flag notable patterns: releases-stale, tag-only repos, auth-wall clusters."""
    where = "WHERE cr.batch_id = ? AND cr.status = 'success'"
    params = [batch_id]
    if target_filter:
        where += " AND t.canonical_name = ?"
        params.append(target_filter)

    # Find repos where releases worked AND tags worked — compare versions
    rows = db.execute(
        f"""SELECT a.canonical_identifier as repo, t.canonical_name as target,
                   MAX(CASE WHEN vs.source_type = 'github_release' THEN vo.version_value END) AS release_ver,
                   MAX(CASE WHEN vs.source_type = 'github' THEN vo.version_value END) AS tag_ver
            FROM check_run cr
            JOIN version_source vs ON vs.version_source_id = cr.version_source_id
            JOIN asset a ON a.asset_id = vs.asset_id
            JOIN version_observation vo ON vo.version_source_id = cr.version_source_id AND vo.is_current = 1
            JOIN target_asset ta ON ta.asset_id = a.asset_id AND ta.is_current = 1
            JOIN target t ON t.target_id = ta.target_id
            {where}
              AND vs.source_type IN ('github_release', 'github')
              AND a.vector_type = 'github_repository'
            GROUP BY a.canonical_identifier, t.canonical_name
            HAVING release_ver IS NOT NULL AND tag_ver IS NOT NULL
            ORDER BY t.canonical_name, a.canonical_identifier""",
        params,
    ).fetchall()

    gaps = []
    for r in rows:
        rv = (r["release_ver"] or "").lstrip("vV")
        tv = (r["tag_ver"] or "").lstrip("vV")
        if rv != tv and rv and tv:
            gaps.append((r["target"], r["repo"], r["release_ver"], r["tag_ver"]))

    if gaps:
        print("─── NOTABLE GAPS ───")
        print("  (release version ≠ tag version — releases may be stale)")
        for target, repo, rv, tv in gaps:
            print(f"  {target:<22s} {repo:<45s} release={rv:<20s} tag={tv}")
        print()

    # Repos where releases failed but tags succeeded (STORAGE_MOVED pattern)
    failed_releases = db.execute(
        f"""SELECT a.canonical_identifier as repo, t.canonical_name as target
            FROM check_run cr
            JOIN version_source vs ON vs.version_source_id = cr.version_source_id
            JOIN asset a ON a.asset_id = vs.asset_id
            JOIN target_asset ta ON ta.asset_id = a.asset_id AND ta.is_current = 1
            JOIN target t ON t.target_id = ta.target_id
            WHERE cr.batch_id = ? AND cr.status = 'failure'
              AND vs.source_type = 'github_release'
              AND cr.error_code = 'STORAGE_MOVED'""",
        [batch_id],
    ).fetchall()

    if failed_releases:
        print("─── RELEASES BROKEN, TAGS WORKING ───")
        for r in failed_releases:
            print(f"  {r['target']:<22s} {r['repo']} — no GitHub Releases page, tags still checkable")
        print()


def main():
    parser = argparse.ArgumentParser(description="Version-tracker post-check report")
    parser.add_argument("--target", help="Filter by target canonical name")
    parser.add_argument("--batch-id", help="Specific batch ID (default: latest)")
    parser.add_argument("--failures-only", action="store_true", help="Only show failures")
    parser.add_argument("--fingerprints-only", action="store_true", help="Only show fingerprint-only entries")
    args = parser.parse_args()

    db = connect()

    batch_id = args.batch_id or get_latest_batch(db)
    if not batch_id:
        print("No check runs found. Run --first-check first.")
        sys.exit(1)

    summary(db, batch_id, args.target)

    if args.fingerprints_only:
        baselines(db, batch_id, args.target, fingerprints_only=True)
    elif args.failures_only:
        failures(db, batch_id, args.target)
    else:
        baselines(db, batch_id, args.target, fingerprints_only=False)
        baselines(db, batch_id, args.target, fingerprints_only=True)
        failures(db, batch_id, args.target)
        notable_gaps(db, batch_id, args.target)

    db.close()


if __name__ == "__main__":
    main()
