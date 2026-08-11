"""
tests/test_schema.py — Schema structure and integrity tests.

Phase 1, zero dependencies beyond the schema file itself.
Pins the timestamp-format mismatch (bug #3) and the table-count
off-by-one in the header comment.
"""

import os
import re
import sqlite3
import sys
from pathlib import Path

import pytest

# ── Module-level imports ──────────────────────────────────────────

_checkers_dir = os.path.join(os.path.dirname(__file__), "..", "checkers")
if _checkers_dir not in sys.path:
    sys.path.insert(0, _checkers_dir)
from checkers import runner, http_cache  # noqa: E402


class TestSchemaApplication:
    """Schema loads cleanly and produces the expected structure."""

    def test_schema_applies_cleanly(self, db) -> None:
        """executescript(schema_sql()) must not raise."""
        # If we got here without an exception, the fixture succeeded.
        # Double-check we have tables.
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        assert len(tables) > 0

    def test_expected_tables_exist(self, db) -> None:
        """Assert the exact canonical table set."""
        expected = [
            "asset",
            "bug_bounty_platform",
            "bug_bounty_program",
            "check_run",
            "discovered_host",
            "error_classification",
            "finding",
            "http_cache",
            "program_policy",
            "research_note",
            "scope_change_event",
            "scope_observation",
            "scope_record",
            "source",
            "target",
            "target_asset",
            "version_change_event",
            "version_observation",
            "version_source",
        ]
        tables = [
            row["name"]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        ]
        assert tables == expected

    def test_expected_indexes_exist(self, db) -> None:
        """All named CREATE INDEX statements are present."""
        expected = [
            "idx_asset_type",
            "idx_bug_bounty_program_status",
            "idx_check_run_batch",
            "idx_check_run_status",
            "idx_discovered_host_active",
            "idx_discovered_host_hostname",
            "idx_http_cache_last_hit",
            "idx_program_policy_program",
            "idx_program_target_current",
            "idx_scope_record_asset",
            "idx_scope_record_status",
            "idx_version_change_research",
            "idx_version_change_source",
            "idx_version_obs_current",
            "idx_version_obs_source",
            "idx_version_source_enabled",
            "idx_version_source_failures",
            "idx_version_source_last_checked",
            "idx_vs_due",
        ]
        indexes = [
            row["name"]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        ]
        assert indexes == expected

    def test_program_policy_ddl_matches_migration_003(self, db) -> None:
        """Fresh-schema policy DDL must stay identical to migration 003."""
        migration_path = (
            Path(__file__).parents[1] / "sql/migrations/003_program_policy.sql"
        )
        migrated = sqlite3.connect(":memory:")
        migrated.executescript(
            "CREATE TABLE bug_bounty_program (program_id INTEGER PRIMARY KEY);"
        )
        migrated.executescript(migration_path.read_text())

        def policy_ddl(connection):
            rows = connection.execute(
                """SELECT type, name, sql FROM sqlite_master
                   WHERE name IN ('program_policy', 'idx_program_policy_program')
                   ORDER BY type, name"""
            ).fetchall()
            return [
                (row[0], row[1], re.sub(r"\s+", " ", row[2]).strip())
                for row in rows
            ]

        try:
            assert policy_ddl(db) == policy_ddl(migrated)
        finally:
            migrated.close()

    def test_partial_index_on_current_observations(self, db) -> None:
        """idx_version_obs_current must include WHERE is_current = 1."""
        sql = db.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' "
            "AND name='idx_version_obs_current'"
        ).fetchone()["sql"]
        assert "is_current" in sql
        assert "WHERE" in sql.upper()

    def test_schema_is_not_idempotent(self, db, db_schema) -> None:
        """Running executescript twice must raise OperationalError.

        Pins that sql/schema.sql is create-only and must never be run
        against an existing database.
        """
        with pytest.raises(Exception):
            db.executescript(db_schema)

    def test_http_cache_ddl_matches_schema(self, db_schema) -> None:
        """The http_cache table DDL in sql/schema.sql must match the
        runtime DDL in checkers/http_cache.py.  These are two copies
        of the same DDL that can silently drift.

        The schema version uses plain CREATE TABLE; the runtime version
        uses CREATE TABLE IF NOT EXISTS and includes a CREATE INDEX.
        This test strips those differences and compares column sets.
        """
        # Parse column sets from the schema DDL
        schema_cols = set()
        in_http_cache = False
        for line in db_schema.split("\n"):
            line = line.strip()
            if "CREATE TABLE http_cache" in line:
                in_http_cache = True
                continue
            if in_http_cache and line.startswith(")"):
                break
            if in_http_cache and line and not line.startswith("--"):
                col = line.strip().split()[0].strip('"')
                if col:
                    schema_cols.add(col)

        # Parse column sets from the runtime DDL
        runtime_cols = set()
        for line in http_cache._CACHE_TABLE_DDL.split("\n"):
            line = line.strip()
            if (line.startswith("CREATE TABLE") or line.startswith("CREATE INDEX")
                    or line.startswith(")")):
                continue
            if line and not line.startswith("--"):
                col = line.strip().split()[0].strip('"')
                if col:
                    runtime_cols.add(col)

        assert schema_cols == runtime_cols, (
            "http_cache column mismatch between sql/schema.sql and "
            "checkers/http_cache.py._CACHE_TABLE_DDL"
        )


class TestTimestampFormat:
    """Bug #3: two timestamp formats coexist in the same columns."""

    def test_timestamp_default_format(self, db) -> None:
        """schema.sql's ``datetime('now')`` produces space-separated format,
        while runner._now() produces ISO-8601 with T and Z separators.

        The _source_is_due bug (#3) is rooted here: SQLite defaults use
        ``YYYY-MM-DD HH:MM:SS`` but the source-due check parses with
        fromisoformat, comparing naive datetimes against aware UTC
        (TypeError → swallowed → always "due").
        """
        # Schema default: datetime('now') produces space-separated
        db.execute(
            "INSERT INTO target (canonical_name) VALUES (?)",
            ("format-test",),
        )
        row = db.execute(
            "SELECT created_at FROM target WHERE canonical_name='format-test'"
        ).fetchone()

        ts = row["created_at"]
        # SQLite datetime('now') format: YYYY-MM-DD HH:MM:SS (no T, no Z)
        assert " " in ts, f"Expected space-separated timestamp, got: {ts!r}"
        assert "T" not in ts
        assert "Z" not in ts

    def test_runner_now_produces_iso_format(self) -> None:
        """runner._now() produces ``YYYY-MM-DDTHH:MM:SSZ``.

        The discrepancy with SQLite's datetime('now') is the root cause
        of the _source_is_due bug: the comparison between a naive datetime
        (from fromisoformat on the SQLite format) and an aware datetime
        (from datetime.now(timezone.utc)) raises TypeError, caught by the
        blanket except → returns True ("due").
        """
        now = runner._now()
        assert "T" in now, f"Expected ISO-8601 timestamp, got: {now!r}"
        assert "Z" in now


class TestErrorClassificationSeed:
    """Validate the 12 seeded error_classification rows."""

    def test_error_classification_seed_rows(self, db) -> None:
        """Exactly 14 rows seeded in schema.sql."""
        expected = {
            "STORAGE_MOVED", "PAGE_STRUCTURE", "FEED_GONE", "APP_UNLISTED",
            "AUTH_REQUIRED", "RATE_LIMITED", "TIMEOUT", "DNS_FAILURE",
            "TLS_ERROR", "PARSE_ERROR", "EMPTY_RESPONSE", "UNKNOWN",
            "BOT_WALL", "CAPTCHA_GATE",
        }
        codes = {
            row["error_code"]
            for row in db.execute(
                "SELECT error_code FROM error_classification"
            ).fetchall()
        }
        assert codes == expected

    def test_error_classification_transient_flags(self, db) -> None:
        """Transient (1): RATE_LIMITED, TIMEOUT, DNS_FAILURE, UNKNOWN.
        Structural (0): the other 8."""
        transient_codes = {"RATE_LIMITED", "TIMEOUT", "DNS_FAILURE", "UNKNOWN"}
        for row in db.execute(
            "SELECT error_code, is_transient FROM error_classification"
        ).fetchall():
            if row["error_code"] in transient_codes:
                assert row["is_transient"] == 1, (
                    f"{row['error_code']} should be transient"
                )
            else:
                assert row["is_transient"] == 0, (
                    f"{row['error_code']} should be structural"
                )

    def test_error_classification_max_retries(self, db) -> None:
        """Pin the expected max_retries values for every code."""
        expected = {
            "STORAGE_MOVED": 1, "PAGE_STRUCTURE": 2, "FEED_GONE": 1,
            "APP_UNLISTED": 1, "AUTH_REQUIRED": 1, "RATE_LIMITED": 3,
            "TIMEOUT": 3, "DNS_FAILURE": 3, "TLS_ERROR": 2,
            "PARSE_ERROR": 3, "EMPTY_RESPONSE": 2, "UNKNOWN": 5,
            "BOT_WALL": 2, "CAPTCHA_GATE": 1,
        }
        for row in db.execute(
            "SELECT error_code, max_retries FROM error_classification"
        ).fetchall():
            assert row["max_retries"] == expected[row["error_code"]], (
                f"max_retries mismatch for {row['error_code']}"
            )
