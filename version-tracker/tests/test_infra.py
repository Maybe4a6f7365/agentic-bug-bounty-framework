"""
tests/test_infra.py — Validate the production-DB guard works.

The guard in ``tests/support/guard.py::assert_not_production_db()`` is
"the single most important line in the suite" (TEST_PLAN.md §1.4).  If it
fails silently, the test suite opens the real production database,
creating it if it doesn't exist, disabling sources and writing check_run
history.  These three tests validate the guard catches the two failure modes
and accepts a legitimate temp path.

Phase 0, <50 ms, zero deps.
"""

import os
import tempfile

import pytest

from tests.support.guard import assert_not_production_db


def test_rejects_real_production_path() -> None:
    """The exact production DB path must be rejected."""
    prod_path = os.path.expanduser("~/.hermes/version-tracker/version_tracker.db")
    with pytest.raises(RuntimeError) as exc_info:
        assert_not_production_db(prod_path)
    assert "production database" in str(exc_info.value)


def test_rejects_path_under_dot_hermes() -> None:
    """Any path under ~/.hermes/ must be rejected — catches copy-paste
    mistakes that point at the wrong view of the target inventory."""
    # Pick a path that is under ~/.hermes/ but is NOT the exact prod DB
    # path — this exercises the prefix check, not the equality check.
    bogus = os.path.expanduser("~/.hermes/some-other-db/vt-copy.db")
    with pytest.raises(RuntimeError) as exc_info:
        assert_not_production_db(bogus)
    assert "under ~/.hermes/" in str(exc_info.value)


def test_accepts_temp_path() -> None:
    """A path in /tmp should pass the guard without raising."""
    tmpdir = tempfile.mkdtemp()
    try:
        test_db = os.path.join(tmpdir, "test.db")
        # Must not raise
        assert_not_production_db(test_db)
    finally:
        os.rmdir(tmpdir)
