"""
tests/__init__.py — Import-time safety guard and hermetic environment.

Executed before any test module in the tests/ directory is imported.
Responsibilities (TEST_PLAN.md §1.4), in order:

1. Create a per-session temp directory for test databases.
2. Set ``VERSION_TRACKER_DB`` to a temp path — BEFORE any project import —
   so that ``checkers/runner.py`` never opens the production database.
3. Run the hard guard: assert the DB path is not the real production path
   and does not live under ``~/.hermes/``.
4. Strip ``GITHUB_TOKEN`` and ``CHECK_BATCH_ID`` from the environment so
   unit tests are hermetic regardless of the operator's shell state.
5. Add ``checkers/`` to ``sys.path``, mirroring ``runner.py:37``, so
   ``import http_cache`` resolves correctly.
"""

import os
import sys
import tempfile

_GUARD_RAN = False


def _setup() -> None:
    global _GUARD_RAN
    if _GUARD_RAN:
        return

    # 1. Per-session temp directory
    _tmpdir = tempfile.mkdtemp(prefix="vt-test-")

    # 2. Set DB path BEFORE any project import touches runner.py:41
    os.environ["VERSION_TRACKER_DB"] = os.path.join(_tmpdir, "test.db")

    # 3. Hard guard — the single most important line in the suite
    from tests.support.guard import assert_not_production_db

    assert_not_production_db(os.environ["VERSION_TRACKER_DB"])

    # 4. Hermetic environment
    os.environ.pop("GITHUB_TOKEN", None)
    os.environ.pop("CHECK_BATCH_ID", None)

    # 5. Mirror runner.py:37 so checkers can `import http_cache`
    _checkers_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "checkers",
    )
    if _checkers_dir not in sys.path:
        sys.path.insert(0, _checkers_dir)

    _GUARD_RAN = True


_setup()
