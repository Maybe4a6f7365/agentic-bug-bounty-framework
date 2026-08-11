#!/usr/bin/env python3
"""Fail-closed reconciliation for two known synthetic orphan assets."""

import argparse
import json
import sqlite3
import sys
from pathlib import Path


PHASE1 = ("website", "phase1-test.example")
PHASE6 = ("website", "phase6-js-bundle")


class ReconciliationError(RuntimeError):
    """The database does not match the exact expected reconciliation state."""


def _checks_ok(connection: sqlite3.Connection) -> bool:
    return (
        connection.execute("PRAGMA foreign_key_check").fetchall() == []
        and [row[0] for row in connection.execute("PRAGMA integrity_check")] == ["ok"]
    )


def reconcile(db_path: Path) -> dict:
    if not db_path.is_file():
        raise ReconciliationError(f"database does not exist: {db_path}")

    uri = f"{db_path.resolve().as_uri()}?mode=rw"
    connection = sqlite3.connect(uri, uri=True, isolation_level=None)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.execute("PRAGMA foreign_keys = ON")
        if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise ReconciliationError("could not enable foreign key enforcement")
        if not _checks_ok(connection):
            raise ReconciliationError("database failed pre-reconciliation integrity checks")

        connection.execute("BEGIN IMMEDIATE")
        phase1_rows = connection.execute(
            "SELECT asset_id, status FROM asset WHERE vector_type=? AND canonical_identifier=?",
            PHASE1,
        ).fetchall()
        phase6_rows = connection.execute(
            "SELECT asset_id, status, discovery_method FROM asset "
            "WHERE vector_type=? AND canonical_identifier=?",
            PHASE6,
        ).fetchall()
        if len(phase1_rows) != 1 or len(phase6_rows) != 1:
            raise ReconciliationError("required synthetic orphan asset is missing or duplicated")
        phase1 = phase1_rows[0]
        phase6 = phase6_rows[0]

        source_counts = connection.execute(
            """SELECT COUNT(*), SUM(CASE WHEN enabled=1 THEN 1 ELSE 0 END)
               FROM version_source WHERE asset_id=?""",
            (phase1["asset_id"],),
        ).fetchone()
        phase1_stale = phase1["status"] == "active" and tuple(source_counts) == (13, 13)
        phase1_correct = phase1["status"] == "deprecated" and tuple(source_counts) == (13, 0)
        if not (phase1_stale or phase1_correct):
            raise ReconciliationError("unexpected phase1 source state")

        current_links = connection.execute(
            """SELECT COUNT(*) FROM target_asset
               WHERE is_current=1 AND asset_id IN (?, ?)""",
            (phase1["asset_id"], phase6["asset_id"]),
        ).fetchone()[0]
        phase6_sources = connection.execute(
            "SELECT COUNT(*) FROM version_source WHERE asset_id=?",
            (phase6["asset_id"],),
        ).fetchone()[0]
        phase6_known_status = phase6["status"] in ("active", "deprecated")
        if (
            current_links != 0
            or phase6_sources != 0
            or phase6["discovery_method"] != "manual_synthetic"
            or not phase6_known_status
        ):
            raise ReconciliationError("unexpected synthetic orphan state")

        source_total_before = connection.execute(
            "SELECT COUNT(*) FROM version_source"
        ).fetchone()[0]
        link_total_before = connection.execute(
            "SELECT COUNT(*) FROM target_asset"
        ).fetchone()[0]
        expected_disabled = 13 if phase1_stale else 0
        expected_deprecated = int(phase1["status"] == "active") + int(
            phase6["status"] == "active"
        )
        changes_before = connection.total_changes

        disabled = connection.execute(
            "UPDATE version_source SET enabled=0 WHERE asset_id=? AND enabled=1",
            (phase1["asset_id"],),
        ).rowcount
        deprecated = 0
        for asset_id in (phase1["asset_id"], phase6["asset_id"]):
            deprecated += connection.execute(
                "UPDATE asset SET status='deprecated', updated_at=datetime('now') "
                "WHERE asset_id=? AND status='active'",
                (asset_id,),
            ).rowcount

        expected_changes = expected_disabled + expected_deprecated
        if connection.total_changes - changes_before != expected_changes:
            raise ReconciliationError("unexpected database changes during reconciliation")

        post_state = connection.execute(
            """SELECT
                 (SELECT COUNT(*) FROM version_source WHERE asset_id=?),
                 (SELECT COUNT(*) FROM version_source WHERE asset_id=? AND enabled=0),
                 (SELECT COUNT(*) FROM version_source WHERE asset_id=?),
                 (SELECT COUNT(*) FROM version_source),
                 (SELECT COUNT(*) FROM target_asset),
                 (SELECT COUNT(*) FROM target_asset
                    WHERE is_current=1 AND asset_id IN (?, ?)),
                 (SELECT COUNT(*) FROM asset
                    WHERE asset_id IN (?, ?) AND status='deprecated')""",
            (
                phase1["asset_id"], phase1["asset_id"], phase6["asset_id"],
                phase1["asset_id"], phase6["asset_id"],
                phase1["asset_id"], phase6["asset_id"],
            ),
        ).fetchone()
        expected_post_state = (
            13, 13, 0, source_total_before, link_total_before, 0, 2
        )
        if (
            tuple(post_state) != expected_post_state
            or disabled != expected_disabled
            or deprecated != expected_deprecated
        ):
            raise ReconciliationError("reconciliation postconditions failed")
        if not _checks_ok(connection):
            raise ReconciliationError("database failed post-reconciliation integrity checks")
        connection.commit()
        return {
            "ok": True,
            "phase1_sources_disabled": disabled,
            "assets_deprecated": deprecated,
        }
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = reconcile(args.db)
    except (ReconciliationError, sqlite3.Error) as exc:
        print(f"reconciliation refused: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
