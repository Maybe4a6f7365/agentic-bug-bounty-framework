"""
tests/conftest.py — Pytest fixtures for the version-tracker test suite.

Phase 2 of the pytest migration: provides fixture equivalents of
tests/support/dbutil.py and tests/support/fakes.py so that individual
test files can migrate incrementally.

Existing unittest-based tests are unaffected — they continue to use the
support modules directly.  Converted tests use these fixtures instead.

Fixtures
--------
db_schema   session-scoped   Schema SQL text (cached)
db          function-scoped  File-based SQLite DB with schema applied (tmp_path)
seeded_db   function-scoped  DB with seed data loaded from sql/seeds/
fake_http   function-scoped  FakeHTTPCache instance (from tests.support.fakes)
fake_gps    function-scoped  FakeGPSModule instance (for android_store tests)
"""

import os
import sqlite3
from functools import lru_cache

import pytest

# ── Schema fixture (session-scoped, cached) ─────────────────────────

_SCHEMA_PATH = os.path.join(
    os.path.dirname(__file__), "..", "sql", "schema.sql",
)


@lru_cache(maxsize=1)
def _load_schema() -> str:
    with open(_SCHEMA_PATH) as f:
        return f.read()


@pytest.fixture(scope="session")
def db_schema() -> str:
    """Session-scoped: the full ``sql/schema.sql`` text, cached."""
    return _load_schema()


# ── DB fixtures (function-scoped, file-based via tmp_path) ──────────

def _apply_schema(conn: sqlite3.Connection) -> None:
    """Apply the production schema to an open connection."""
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    conn.executescript(_load_schema())


@pytest.fixture
def db(tmp_path, db_schema):
    """Function-scoped: a file-based SQLite DB with the full schema applied.

    Returns an ``sqlite3.Connection`` with ``PRAGMA foreign_keys = ON``
    and ``row_factory = sqlite3.Row``.  Backed by a temp file under
    ``tmp_path`` so WAL mode works correctly.

    Use ``seeded_db`` when you need pre-populated data.
    """
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    _apply_schema(conn)
    return conn


@pytest.fixture
def seeded_db(db):
    """Function-scoped: like ``db`` but with seed data from ``sql/seeds/``.

    Loads seed files in dependency order so foreign keys are satisfied.
    Returns the same connection with data pre-loaded.
    """
    seeds_dir = os.path.join(
        os.path.dirname(__file__), "..", "sql", "seeds",
    )
    if not os.path.isdir(seeds_dir):
        return db

    seed_files = sorted(
        f for f in os.listdir(seeds_dir) if f.endswith(".sql")
    )
    with db:
        for seed_file in seed_files:
            with open(os.path.join(seeds_dir, seed_file)) as f:
                db.executescript(f.read())
    return db


# ── Fake HTTP fixture (function-scoped) ─────────────────────────────

@pytest.fixture
def fake_http():
    """Function-scoped: a fresh ``FakeHTTPCache`` instance.

    Use ``fake_http.set(url, body)`` to set canned responses before
    calling a checker.  ``fake_http.requests`` records every call.
    """
    from tests.support.fakes import FakeHTTPCache
    return FakeHTTPCache()


# ── Fake GPS fixture (function-scoped, for android_store tests) ─────

@pytest.fixture
def fake_gps():
    """Function-scoped: a fresh ``FakeGPSModule`` for android_store tests.

    Use ``fake_gps.app.set(app_id, result)`` to set canned Play Store
    responses.  Inject via ``sys.modules["google_play_scraper"]``.
    """
    from tests.support.fakes import FakeGPSModule
    return FakeGPSModule()
