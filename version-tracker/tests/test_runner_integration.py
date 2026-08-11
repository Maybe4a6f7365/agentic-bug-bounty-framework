"""tests/test_runner_integration.py — Integration tests for runner._run_check_on_db.

Phase 9/12: Pytest-native — uses conftest fixtures (db, fake_http) instead of
dbutil.fresh_memory_db().

Tests:
  - _run_check_on_db: successful check, no-change, CheckerError,
    first_check_mode, consecutive_failures reset
  - run_single_check wrapper
  - ThreadPoolExecutor basic verification
"""

import json
import os
import sys
from unittest import mock

import pytest

# Mirror tests/__init__.py: ensure checkers/ is importable for http_cache resolution
_checkers_dir = os.path.join(os.path.dirname(__file__), "..", "checkers")
if _checkers_dir not in sys.path:
    sys.path.insert(0, _checkers_dir)

from checkers import runner
from checkers.runner import _run_check_on_db, run_single_check


# ── Canned test data ────────────────────────────────────────────────

API_SIMPLE_VERSION = b'{"version": "v1.2.3"}'

API_CONFIG = {
    "api_url": "https://example.com/version",
    "path": "$.version",
}


def _seed_asset(db_conn, canonical_identifier="example.com", vector_type="api"):
    """Seed an asset row and return its asset_id."""
    cur = db_conn.execute(
        """INSERT INTO asset (vector_type, canonical_identifier, display_name)
           VALUES (?, ?, ?)""",
        [vector_type, canonical_identifier, canonical_identifier],
    )
    db_conn.commit()
    return cur.lastrowid


def _seed_version_source(db_conn, asset_id, source_type="api",
                          check_method="json_path", config=None,
                          consecutive_failures=0, enabled=1):
    """Seed a version_source row and return its version_source_id."""
    if config is None:
        config = API_CONFIG
    cur = db_conn.execute(
        """INSERT INTO version_source
           (asset_id, source_type, source_identifier, check_method, config,
            enabled, check_interval, consecutive_failures)
           VALUES (?, ?, ?, ?, ?, ?, 86400, ?)""",
        [asset_id, source_type, f"{source_type}:{check_method}", check_method,
         json.dumps(config), enabled, consecutive_failures],
    )
    db_conn.commit()
    return cur.lastrowid


def _row(db_conn, vs_id):
    """Re-fetch the version_source row by id."""
    return db_conn.execute(
        "SELECT * FROM version_source WHERE version_source_id=?", [vs_id]
    ).fetchone()


# ═════════════════════════════════════════════════════════════════════
#  TestRunCheckOnDb — converted to pytest-native
# ═════════════════════════════════════════════════════════════════════

@pytest.fixture
def runner_db(db, fake_http, monkeypatch):
    """Fixture: DB + fake_http patched as runner.http_cache."""
    monkeypatch.setattr(runner, "http_cache", fake_http, raising=False)
    return db


# ── Successful check ───────────────────────────────────────

def test_successful_check_writes_observation_and_check_run(runner_db, fake_http):
    """A check that returns a new version writes observation + check_run
    and updates version_source."""
    fake_http.set("https://example.com/version", API_SIMPLE_VERSION)
    asset_id = _seed_asset(runner_db)
    vs_id = _seed_version_source(runner_db, asset_id)

    result = _run_check_on_db(runner_db, _row(runner_db, vs_id), first_check_mode=False)

    # Result contract
    assert result["status"] == "success"
    assert result["changed"]
    assert result["first_check"]    # No prior observation → first check
    assert "observation_id" in result

    # Observation written
    obs = runner_db.execute(
        "SELECT * FROM version_observation WHERE version_observation_id=?",
        [result["observation_id"]],
    ).fetchone()
    assert obs["version_value"] == "v1.2.3"
    assert obs["is_current"] == 1
    assert obs["version_source_id"] == vs_id

    # Check_run written
    cr = runner_db.execute(
        "SELECT * FROM check_run WHERE check_run_id=?",
        [result["check_run_id"]],
    ).fetchone()
    assert cr["status"] == "success"
    assert cr["changed"] == 1
    assert cr["version_source_id"] == vs_id

    # Version_source updated
    vs = _row(runner_db, vs_id)
    assert vs["consecutive_failures"] == 0
    assert vs["last_checked_at"] is not None
    assert vs["last_success_at"] is not None
    assert vs["last_error"] is None

    # Change_event written (not first_check_mode, not first check)
    events = runner_db.execute(
        "SELECT * FROM version_change_event WHERE version_source_id=?", [vs_id]
    ).fetchall()
    assert len(events) == 1
    assert events[0]["change_type"] == "api_version_changed"
    assert events[0]["research_status"] == "new"


# ── No-change (304 / unchanged) ────────────────────────────

def test_no_change_does_not_write_new_observation(runner_db, fake_http):
    """When checker returns None (HTTP 304), check_run is success/changed=0,
    no new observation is written."""
    # First, seed an existing observation to establish baseline
    fake_http.set("https://example.com/version", API_SIMPLE_VERSION)
    asset_id = _seed_asset(runner_db)
    vs_id = _seed_version_source(runner_db, asset_id)

    # Run first check to create baseline observation
    _run_check_on_db(runner_db, _row(runner_db, vs_id), first_check_mode=False)

    obs_count_before = runner_db.execute(
        "SELECT COUNT(*) AS n FROM version_observation WHERE version_source_id=?",
        [vs_id],
    ).fetchone()["n"]
    assert obs_count_before == 1

    # Now simulate 304 — content unchanged
    fake_http.set_304("https://example.com/version")
    result = _run_check_on_db(runner_db, _row(runner_db, vs_id), first_check_mode=False)

    assert result["status"] == "success"
    assert not result["changed"]

    # No new observation
    obs_count_after = runner_db.execute(
        "SELECT COUNT(*) AS n FROM version_observation WHERE version_source_id=?",
        [vs_id],
    ).fetchone()["n"]
    assert obs_count_after == obs_count_before

    # Check_run changed=0
    cr = runner_db.execute(
        "SELECT * FROM check_run WHERE check_run_id=?",
        [result["check_run_id"]],
    ).fetchone()
    assert cr["status"] == "success"
    assert cr["changed"] == 0

    # consecutive_failures stays at 0 (no-change is not a failure)
    vs = _row(runner_db, vs_id)
    assert vs["consecutive_failures"] == 0


# ── CheckerError ───────────────────────────────────────────

def test_checker_error_records_failure_in_check_run(runner_db, fake_http):
    """When the checker raises CheckerError, check_run gets
    status='failure' + error_code, and consecutive_failures increments."""
    fake_http.set_404("https://example.com/version")
    asset_id = _seed_asset(runner_db)
    vs_id = _seed_version_source(runner_db, asset_id)

    result = _run_check_on_db(runner_db, _row(runner_db, vs_id), first_check_mode=False)

    assert result["status"] == "failure"
    assert "error_code" in result
    assert result["consecutive_failures"] > 0

    # Check_run
    cr = runner_db.execute(
        "SELECT * FROM check_run WHERE check_run_id=?",
        [result["check_run_id"]],
    ).fetchone()
    assert cr["status"] == "failure"
    assert cr["error_code"] is not None
    assert cr["error_message"] is not None

    # Version_source updated
    vs = _row(runner_db, vs_id)
    assert vs["consecutive_failures"] == 1
    assert vs["last_error"] is not None
    assert vs["last_error_at"] is not None


# ── First-check mode ───────────────────────────────────────

def test_first_check_mode_writes_observation_no_change_event(runner_db, fake_http):
    """first_check_mode=True on a brand-new source: observation is written
    as a baseline, but NO change_event is created."""
    fake_http.set("https://example.com/version", API_SIMPLE_VERSION)
    asset_id = _seed_asset(runner_db)
    vs_id = _seed_version_source(runner_db, asset_id)

    result = _run_check_on_db(runner_db, _row(runner_db, vs_id), first_check_mode=True)

    assert result["status"] == "success"
    assert result["first_check"]
    assert not result["changed"]  # changed=False in first-check mode

    # Observation IS written (baseline)
    assert "observation_id" in result
    obs = runner_db.execute(
        "SELECT * FROM version_observation WHERE version_observation_id=?",
        [result["observation_id"]],
    ).fetchone()
    assert obs is not None
    assert obs["is_current"] == 1
    assert obs["version_value"] == "v1.2.3"

    # NO change_event for baseline
    events = runner_db.execute(
        "SELECT * FROM version_change_event WHERE version_source_id=?", [vs_id]
    ).fetchall()
    assert len(events) == 0, "First-check mode must not write a change_event"

    # Check_run has changed=0 for baseline
    cr = runner_db.execute(
        "SELECT * FROM check_run WHERE check_run_id=?",
        [result["check_run_id"]],
    ).fetchone()
    assert cr["changed"] == 0


# ── Consecutive failures reset ─────────────────────────────

def test_consecutive_failures_reset_on_success(runner_db, fake_http):
    """After a successful check, consecutive_failures resets to 0
    and last_error is cleared."""
    fake_http.set("https://example.com/version", API_SIMPLE_VERSION)
    asset_id = _seed_asset(runner_db)
    vs_id = _seed_version_source(runner_db, asset_id, consecutive_failures=5)

    row = _row(runner_db, vs_id)
    assert row["consecutive_failures"] == 5, (
        "Precondition: seeded with 5 consecutive failures"
    )

    result = _run_check_on_db(runner_db, row, first_check_mode=False)

    assert result["status"] == "success"

    vs = _row(runner_db, vs_id)
    assert vs["consecutive_failures"] == 0, (
        "consecutive_failures must reset to 0 on success"
    )
    assert vs["last_error"] is None, "last_error must be cleared on success"
    assert vs["last_error_code"] is None, "last_error_code must be cleared on success"


# ── Edge: existing observation + first_check_mode ──────────

def test_first_check_mode_with_existing_observation_still_writes_change_event(
    runner_db, fake_http,
):
    """When a source already has an observation, first_check_mode still
    writes a change_event (it's no longer the first check)."""
    fake_http.set("https://example.com/version", API_SIMPLE_VERSION)
    asset_id = _seed_asset(runner_db)
    vs_id = _seed_version_source(runner_db, asset_id)

    # Baseline run to create an observation
    _run_check_on_db(runner_db, _row(runner_db, vs_id), first_check_mode=True)

    # Second run — different content, still first_check_mode
    fake_http.set("https://example.com/version", b'{"version": "v1.4.0"}')
    result = _run_check_on_db(runner_db, _row(runner_db, vs_id), first_check_mode=True)

    # Should now detect a real change
    assert result["changed"], (
        "Second check with existing observation should detect change"
    )
    assert not result["first_check"], (
        "Not a first check; observation already exists"
    )

    events = runner_db.execute(
        "SELECT * FROM version_change_event WHERE version_source_id=?", [vs_id]
    ).fetchall()
    assert len(events) == 1, "Change event should be written for non-first check"


# ═════════════════════════════════════════════════════════════════════
#  TestRunSingleCheck — converted to pytest-native
# ═════════════════════════════════════════════════════════════════════

def test_run_single_check_passes_module_db_to_run_check_on_db():
    """run_single_check calls _run_check_on_db with the module-level
    `runner.db` connection and passes through first_check_mode."""
    with mock.patch.object(runner, "_run_check_on_db") as mock_run:
        mock_run.return_value = {"status": "success", "changed": False}

        # Build a minimal sqlite3.Row-like object
        fake_row = mock.MagicMock()
        fake_row.__getitem__.side_effect = lambda k: {
            "version_source_id": 1,
            "source_type": "api",
            "check_method": "json_path",
            "asset_id": 1,
            "config": "{}",
            "consecutive_failures": 0,
        }[k]

        run_single_check(fake_row, first_check_mode=True)

        mock_run.assert_called_once()
        # args[0] → db_conn
        assert mock_run.call_args[0][0] is runner.db, (
            "run_single_check must pass module-level db connection"
        )
        # args[0][1] → vs_row
        assert mock_run.call_args[0][1] is fake_row
        # args[0][2] → first_check_mode
        assert mock_run.call_args[0][2]


def test_run_single_check_default_no_first_check():
    """Default first_check_mode is False."""
    with mock.patch.object(runner, "_run_check_on_db") as mock_run:
        mock_run.return_value = {"status": "success", "changed": False}
        fake_row = mock.MagicMock()
        fake_row.__getitem__.side_effect = lambda k: {
            "version_source_id": 1,
            "source_type": "api",
            "check_method": "json_path",
            "asset_id": 1,
            "config": "{}",
            "consecutive_failures": 0,
        }[k]

        run_single_check(fake_row)

        assert not mock_run.call_args[0][2], (
            "first_check_mode defaults to False"
        )


# ═════════════════════════════════════════════════════════════════════
#  TestThreadPoolExecutor — converted to pytest-native
# ═════════════════════════════════════════════════════════════════════

def test_import_exists():
    """concurrent.futures.ThreadPoolExecutor is importable in this Python."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    assert callable(ThreadPoolExecutor)
    assert callable(as_completed)


def test_basic_thread_pool_executes_in_parallel():
    """A basic ThreadPoolExecutor can submit and collect tasks."""
    from concurrent.futures import ThreadPoolExecutor

    def double(n):
        return n * 2

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(double, i) for i in range(4)]
        results = [f.result() for f in futures]

    assert results == [0, 2, 4, 6]


def test_thread_pool_with_db_connections():
    """Verify threads can open their own SQLite connections (simulates
    the parallel runner pattern where each thread gets its own connection)."""
    from concurrent.futures import ThreadPoolExecutor
    import sqlite3

    db_path = os.environ.get("VERSION_TRACKER_DB", ":memory:")

    def thread_work(i):
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        # Just verify the connection works
        conn.execute("SELECT 1 AS one").fetchone()
        conn.close()
        return i

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(thread_work, i) for i in range(2)]
        results = [f.result() for f in futures]

    assert results == [0, 1]


# ═════════════════════════════════════════════════════════════════════
#  Bug A regression test: check_method column propagation.
# ═════════════════════════════════════════════════════════════════════

class TestCheckMethodPropagation:
    """Regression test for Bug A (Phase-1 fix).

    The `version_source.check_method` column says which checker branch
    to run. The api_json.check() dispatcher reads
    ``config.get("check_method") == "header_diff"`` to choose between
    the JSONPath and header_diff branches. Without
    ``config["check_method"] = check_method`` in `_run_check_on_db`, the
    JSONPath branch fires even when the DB row says `header_diff` —
    and `headers` (a list) is then fed to `identity.merge_custom` (which
    expects a dict) → AttributeError.

    This test seeds a row whose `config` JSON does NOT contain a
    `check_method` key but whose `check_method` column is `header_diff`,
    runs the full `_run_check_on_db` pipeline, and asserts that:

    1. The check completes with status='success' (NOT a failure /
       AttributeError).
    2. The version_observation's version_value JSON contains the
       captured headers (proves the header_diff branch fired).

    If the fix is reverted (the `config["check_method"] = check_method`
    line removed), the JSONPath branch will fire, and the dispatcher
    will raise AttributeError when it tries to merge the list-shaped
    `headers` config — this test will FAIL.
    """

    def test_header_diff_dispatch_via_check_method_column(
        self, runner_db, monkeypatch,
    ) -> None:
        """End-to-end runner test: check_method column routes to
        _check_header_diff even when config JSON lacks the key."""
        import urllib.request as _ur
        import checkers.builtin.api_json as _api_json_mod

        # Stub urllib.request.urlopen so the header_diff branch can read
        # a response without making a real HTTP call.
        from tests.support.fakes import _CaseInsensitiveHeaders

        STUB_HEADERS = {
            "Content-Security-Policy": "default-src 'self'",
            "X-Frame-Options": "DENY",
            "Strict-Transport-Security": "max-age=31536000",
        }

        def _stub_urlopen(req, timeout=30, *args, **kwargs):
            class _StubResp:
                status = 200
                headers = _CaseInsensitiveHeaders(
                    {k.lower(): v for k, v in STUB_HEADERS.items()}
                )

                def read(self, *_a, **_kw):
                    return b""

                def __enter__(self):
                    return self

                def __exit__(self, *_a):
                    return False

            return _StubResp()

        monkeypatch.setattr(_ur, "urlopen", _stub_urlopen)
        monkeypatch.setattr(_api_json_mod.urllib.request, "urlopen", _stub_urlopen)

        # Seed an asset + version_source whose config JSON omits
        # check_method but whose column is 'header_diff'.
        cur = runner_db.execute(
            """INSERT INTO asset (vector_type, canonical_identifier, display_name)
               VALUES (?, ?, ?)""",
            ["website", "header-diff-test.example", "header-diff test"],
        )
        asset_id = cur.lastrowid

        cfg_json = json.dumps({
            "api_url": "https://example.com/",
            # Deliberately NO "check_method" key here — the runner
            # must inject it from the column.
            "headers": list(STUB_HEADERS.keys()),
        })
        cur = runner_db.execute(
            """INSERT INTO version_source
               (asset_id, source_type, source_identifier, check_method, config,
                enabled, check_interval, consecutive_failures)
               VALUES (?, ?, ?, ?, ?, 1, 86400, 0)""",
            [asset_id, "api", "api:header_diff", "header_diff", cfg_json],
        )
        vs_id = cur.lastrowid
        runner_db.commit()

        # Run the full pipeline. Use first_check_mode=True so the runner
        # does NOT insert a version_change_event (the schema's CHECK
        # constraint doesn't yet include 'security_header_changed' — a
        # Phase 1 schema gap unrelated to this test). The observation
        # IS still written, which is what we assert below.
        row = runner_db.execute(
            "SELECT * FROM version_source WHERE version_source_id=?", [vs_id]
        ).fetchone()
        result = _run_check_on_db(runner_db, row, first_check_mode=True)

        # Assertion 1: status is success (no AttributeError).
        assert result["status"] == "success", (
            f"Bug A regression: runner failed to propagate check_method — "
            f"got status={result.get('status')!r}, error={result.get('error_code')!r}"
        )

        # Assertion 2: an observation was written.
        assert "observation_id" in result, (
            "Bug A regression: no observation written — header_diff branch did "
            "not fire (the JSONPath branch would have raised AttributeError)"
        )
        obs = runner_db.execute(
            "SELECT * FROM version_observation WHERE version_observation_id=?",
            [result["observation_id"]],
        ).fetchone()
        assert obs is not None

        # Assertion 3: the version_value JSON contains the captured headers —
        # the signature of the header_diff branch.
        parsed_value = json.loads(obs["version_value"])
        assert parsed_value == STUB_HEADERS, (
            f"Bug A regression: header_diff branch did NOT fire — "
            f"version_value shape is wrong: {parsed_value!r}"
        )

        # Assertion 4: the raw_metadata records the security-header
        # capture (another header_diff-only field).
        raw_meta = json.loads(obs["raw_metadata"]) if obs["raw_metadata"] else {}
        assert raw_meta.get("headers") == STUB_HEADERS, (
            f"Bug A regression: raw_metadata['headers'] missing or wrong: "
            f"{raw_meta!r}"
        )
