"""Tests for the github checker (latest_release + latest_tag) and the
add_github_release_sources + fix_tags_field_path scripts.

These tests pin:
  - The /tags endpoint returns a JSON array, so the field path must be
    "[0].name" (not "name") to extract the latest tag.
  - The add_github_release_sources script writes the correct field for
    both source types (releases + tags).
  - The fix_tags_field_path script upgrades the broken config.

Regression for the 2026-08-06 bug where 3 of 4 disabled github/tags
rows were emitting PARSE_ERROR ("Field 'name' not found in response")
because the config field was "name" instead of "[0].name".
"""

import json
import os
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


# ── Pure-python tests of the checker config semantics ─────────────


def _extract_field(field: str, data):
    """Mirror checkers/builtin/github.py::_extract_field for unit tests."""
    parts = field.replace("[", ".[").split(".")
    current = data
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if part.startswith("[") and part.endswith("]"):
            idx = int(part[1:-1])
            if not isinstance(current, list) or idx >= len(current):
                return None
            current = current[idx]
        else:
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
    return current


def test_tags_field_path_zero_dot_name_resolves_first_tag_name():
    tags_response = [{"name": "v5.0.0", "commit": {"sha": "abc"}}]
    assert _extract_field("[0].name", tags_response) == "v5.0.0"


def test_tags_field_path_bare_name_returns_none_on_array():
    """Bare 'name' on a JSON array returns None — the original bug."""
    tags_response = [{"name": "v5.0.0"}]
    assert _extract_field("name", tags_response) is None


def test_releases_field_path_tag_name_resolves_top_level():
    releases_response = {"tag_name": "v5.0.0", "name": "Release v5"}
    assert _extract_field("tag_name", releases_response) == "v5.0.0"


def test_handles_empty_tags_array():
    """An empty tags list returns None for [0].name."""
    assert _extract_field("[0].name", []) is None


# ── Test the add_github_release_sources config writer ─────────────


def test_add_github_release_sources_writes_correct_field_for_tags(tmp_path, monkeypatch):
    """The 2026-08-06 fix: tags field must be "[0].name", not "name"."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "add_github_release_sources",
        ROOT / "scripts" / "add_github_release_sources.py",
    )
    mod = importlib.util.module_from_spec(spec)

    # Set up an isolated DB
    db_path = tmp_path / "vt.sqlite3"
    monkeypatch.setenv("VERSION_TRACKER_DB", str(db_path))

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE target (
            target_id INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_name TEXT NOT NULL UNIQUE
        );
        CREATE TABLE asset (
            asset_id INTEGER PRIMARY KEY AUTOINCREMENT,
            vector_type TEXT NOT NULL,
            canonical_identifier TEXT NOT NULL,
            UNIQUE(vector_type, canonical_identifier)
        );
        CREATE TABLE target_asset (
            target_asset_id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_id INTEGER NOT NULL,
            asset_id INTEGER NOT NULL,
            is_current INTEGER NOT NULL DEFAULT 1,
            first_seen_at TEXT NOT NULL DEFAULT '2026-08-06T00:00:00Z',
            last_seen_at TEXT NOT NULL DEFAULT '2026-08-06T00:00:00Z',
            UNIQUE(target_id, asset_id)
        );
        CREATE TABLE version_source (
            version_source_id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL,
            source_type TEXT NOT NULL,
            source_url TEXT,
            source_identifier TEXT NOT NULL,
            check_method TEXT NOT NULL,
            config TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            check_interval INTEGER NOT NULL DEFAULT 1800,
            on_error_policy TEXT NOT NULL DEFAULT 'standard',
            next_check_at TEXT,
            status TEXT NOT NULL DEFAULT 'active'
        );
    """)
    conn.execute(
        "INSERT INTO target (canonical_name) VALUES (?)",
        ["test-target"],
    )
    conn.execute(
        "INSERT INTO asset (vector_type, canonical_identifier) VALUES (?, ?)",
        ["github_repository", "owner/repo"],
    )
    conn.execute(
        """INSERT INTO target_asset (target_id, asset_id) VALUES (1, 1)""",
    )
    conn.commit()

    spec.loader.exec_module(mod)
    # Apply with a single-candidate override
    mod.CANDIDATES = [("test-target", "owner", "repo")]
    monkeypatch.setattr(mod, "CANDIDATES", mod.CANDIDATES)
    monkeypatch.setattr("sys.argv", ["x", "--apply"])
    rc = mod.main()
    assert rc == 0

    rows = conn.execute(
        "SELECT source_type, config FROM version_source ORDER BY source_type"
    ).fetchall()
    by_type = {r["source_type"]: json.loads(r["config"]) for r in rows}
    assert "github" in by_type, f"missing github row: {by_type}"
    assert "github_release" in by_type, f"missing github_release row: {by_type}"

    # The bug being fixed:
    assert by_type["github"]["field"] == "[0].name", (
        f"github/tags field must be '[0].name', got {by_type['github']['field']!r}. "
        "Bare 'name' is the pre-fix bug that caused PARSE_ERROR."
    )

    # Sanity: releases field is unchanged
    assert by_type["github_release"]["field"] == "tag_name"

    conn.close()


# ── Test the fix_tags_field_path script ───────────────────────────


def test_fix_tags_field_path_dry_run_reports_bug(tmp_path, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "fix_tags_field_path",
        ROOT / "scripts" / "fix_tags_field_path.py",
    )
    mod = importlib.util.module_from_spec(spec)

    db_path = tmp_path / "vt.sqlite3"
    monkeypatch.setenv("VERSION_TRACKER_DB", str(db_path))

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE version_source (
            version_source_id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL DEFAULT 1,
            source_type TEXT NOT NULL DEFAULT 'github',
            source_url TEXT NOT NULL DEFAULT 'https://example/tags',
            source_identifier TEXT NOT NULL DEFAULT 'x-tags',
            check_method TEXT NOT NULL DEFAULT 'tags',
            config TEXT
        );
    """)
    # Insert 2 broken rows + 1 already-correct row
    conn.execute(
        "INSERT INTO version_source (config) VALUES (?)",
        ['{"repo":"a/b","api_endpoint":"/tags","field":"name"}'],
    )
    conn.execute(
        "INSERT INTO version_source (config) VALUES (?)",
        ['{"repo":"c/d","api_endpoint":"/tags","field":"name"}'],
    )
    conn.execute(
        "INSERT INTO version_source (config) VALUES (?)",
        ['{"repo":"e/f","api_endpoint":"/tags","field":"[0].name"}'],
    )
    conn.commit()
    conn.close()

    spec.loader.exec_module(mod)
    monkeypatch.setattr("sys.argv", ["x"])  # dry-run
    rc = mod.main()
    assert rc == 0

    # Reopen and confirm no rows were changed in dry-run
    conn = sqlite3.connect(str(db_path))
    configs = [r[0] for r in conn.execute("SELECT config FROM version_source ORDER BY version_source_id")]
    assert '"field":"name"' in configs[0]
    assert '"field":"name"' in configs[1]
    assert '"field":"[0].name"' in configs[2]
    conn.close()


def test_fix_tags_field_path_apply_fixes_broken_rows(tmp_path, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "fix_tags_field_path",
        ROOT / "scripts" / "fix_tags_field_path.py",
    )
    mod = importlib.util.module_from_spec(spec)

    db_path = tmp_path / "vt.sqlite3"
    monkeypatch.setenv("VERSION_TRACKER_DB", str(db_path))

    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE version_source (
            version_source_id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL DEFAULT 1,
            source_type TEXT NOT NULL DEFAULT 'github',
            source_url TEXT NOT NULL DEFAULT 'https://example/tags',
            source_identifier TEXT NOT NULL DEFAULT 'x-tags',
            check_method TEXT NOT NULL DEFAULT 'tags',
            config TEXT
        );
    """)
    conn.execute(
        "INSERT INTO version_source (config) VALUES (?)",
        ['{"repo":"a/b","api_endpoint":"/tags","field":"name"}'],
    )
    conn.execute(
        "INSERT INTO version_source (config) VALUES (?)",
        ['{"repo":"e/f","api_endpoint":"/tags","field":"[0].name"}'],
    )
    conn.commit()
    conn.close()

    spec.loader.exec_module(mod)
    monkeypatch.setattr("sys.argv", ["x", "--apply"])
    rc = mod.main()
    assert rc == 0

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    configs = [r["config"] for r in conn.execute("SELECT config FROM version_source ORDER BY version_source_id")]
    assert '"[0].name"' in configs[0]
    assert configs[1] == '{"repo":"e/f","api_endpoint":"/tags","field":"[0].name"}'
    conn.close()