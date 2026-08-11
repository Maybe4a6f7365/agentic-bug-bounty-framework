"""Unit tests for the file-based state locking."""
import os
from pathlib import Path

import pytest

from bbr.state.locking import LockError, clear_stale_locks, is_locked, locked


def test_lock_acquired_and_released(tmp_path: Path):
    with locked(tmp_path, "lab-1"):
        # While held, another non-blocking attempt should report is_locked=True
        assert is_locked(tmp_path, "lab-1")
    # After exit, lock should be free
    assert not is_locked(tmp_path, "lab-1")


def test_lock_removed_after_exception(tmp_path: Path):
    try:
        with locked(tmp_path, "lab-1"):
            raise RuntimeError("simulated failure")
    except RuntimeError:
        pass
    # The lock file may remain but must not be held by a live process
    assert not is_locked(tmp_path, "lab-1")


def test_lock_acquire_failure_raises(tmp_path: Path):
    with locked(tmp_path, "lab-1"):
        # Another non-blocking attempt must raise LockError
        from bbr.state.locking import locked as _locked
        with pytest.raises(LockError):
            with _locked(tmp_path, "lab-1", blocking=False):
                pass


def test_clear_stale_locks_removes_unheld(tmp_path: Path):
    # Acquire + release a lock so the lock file exists
    with locked(tmp_path, "lab-1"):
        pass
    assert (tmp_path / ".locks" / "lab-1.lock").exists()
    removed = clear_stale_locks(tmp_path)
    assert removed == 1
    assert not (tmp_path / ".locks" / "lab-1.lock").exists()
