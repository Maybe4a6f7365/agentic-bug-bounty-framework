"""BugBountyRange state locking — Phase 3.

Coarse file-lock based locking for local runtime-state files.
Used by `bbr plan` and `bbr create` to prevent two concurrent
operations against the same lab from corrupting the state file.

The implementation uses `fcntl.flock` (POSIX advisory lock) on
a per-lab lock file in `<state_dir>/.locks/<lab-id>.lock`.

Locks are always released when the context manager exits,
including on exceptions.
"""

from __future__ import annotations

import contextlib
import fcntl
import os
from pathlib import Path
from typing import Iterator

LOCK_DIR_NAME = ".locks"


class LockError(RuntimeError):
    """Raised when the lock cannot be acquired."""


def lock_path(state_dir: Path, lab_id: str) -> Path:
    return state_dir / LOCK_DIR_NAME / f"{lab_id}.lock"


@contextlib.contextmanager
def locked(state_dir: Path, lab_id: str, *, blocking: bool = True) -> Iterator[Path]:
    """Acquire an exclusive advisory lock on a per-lab lock file.

    The lock is released on context exit, including on exceptions.
    """
    lock = lock_path(state_dir, lab_id)
    lock.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
    acquired = False
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX if blocking else fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError as exc:
            os.close(fd)
            raise LockError(
                f"could not acquire lock for lab {lab_id!r}: {exc}"
            ) from exc
        yield lock
    finally:
        if acquired:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
        try:
            os.close(fd)
        except OSError:
            pass


def is_locked(state_dir: Path, lab_id: str) -> bool:
    """Return True if a non-blocking lock would fail (i.e. another
    process currently holds the lock)."""
    lock = lock_path(state_dir, lab_id)
    if not lock.exists():
        return False
    fd = os.open(lock, os.O_RDWR)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return True
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


def clear_stale_locks(state_dir: Path) -> int:
    """Remove stale lock files. A lock is stale if no process
    holds it. The caller must guarantee that no live operation
    is in progress; this is intended for crash recovery only.
    """
    locks_dir = state_dir / LOCK_DIR_NAME
    if not locks_dir.is_dir():
        return 0
    removed = 0
    for lock in sorted(locks_dir.glob("*.lock")):
        lab_id = lock.stem
        if not is_locked(state_dir, lab_id):
            try:
                lock.unlink()
                removed += 1
            except OSError:
                pass
    return removed