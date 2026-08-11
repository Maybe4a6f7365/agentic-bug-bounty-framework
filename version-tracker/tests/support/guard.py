"""
tests/support/guard.py — Production-DB safety guard.

"The single most important line in the suite" (TEST_PLAN.md §1.4).
Called at import time by ``tests/__init__.py`` before any project
module touches ``checkers/runner.py``, and validated at test time
by ``tests/test_infra.py``.
"""

import os

_PROD_DB_PATH = os.path.expanduser("~/.hermes/version-tracker/version_tracker.db")
_DOT_HERMES = os.path.expanduser("~/.hermes/")


def assert_not_production_db(path: str) -> None:
    """Raise RuntimeError if *path* is the production DB or under ``~/.hermes/``.

    The runner.py module opens ``sqlite3.connect(DB_PATH)`` at import time,
    creating the DB file and parent directories.  A test suite must never let
    that happen against the real production database.
    """
    resolved = os.path.realpath(os.path.expanduser(path))

    if resolved == os.path.realpath(_PROD_DB_PATH):
        raise RuntimeError(
            f"SAFETY GUARD: VERSION_TRACKER_DB points at the production database.\n"
            f"  Resolved: {resolved}\n"
            f"  Expected: a temp/test DB path outside ~/.hermes/\n"
            f"  This guard exists to prevent the test suite from opening\n"
            f"  the real version-tracker database."
        )

    if resolved.startswith(os.path.realpath(_DOT_HERMES)):
        raise RuntimeError(
            f"SAFETY GUARD: VERSION_TRACKER_DB lives under ~/.hermes/.\n"
            f"  Resolved: {resolved}\n"
            f"  Paths under ~/.hermes/ are reserved for production data.\n"
            f"  Use a temp directory (e.g. /tmp/vt-test-...) instead."
        )
