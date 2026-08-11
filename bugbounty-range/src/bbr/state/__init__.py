"""Runtime state persistence and locking.

Phase 0. Defines the on-disk layout and the lock protocol
described in ADR-0006, plus the active-lab limit
enforcement described in ADR-0003 and DIRECTIVE.md
Section 8.4.

Layout:
    state/<lab-id>.json        runtime state file (committed)
    state/<lab-id>.lock        short-lived lock file
    state/active-labs.json     count of active (non-DESTROYED)
                               labs; used by the lock layer to
                               enforce the hard cap

The state file is append-only. Each transition records from,
to, timestamp, operator identity, and rationale. The schema
is schemas/lifecycle-state.schema.json.

The lock is implemented as a file with O_CREAT | O_EXCL. The
lock is removed on every transition, including on error.

The active-lab limit is enforced at two layers:

1. The CLI lifecycle layer, before any Terraform call.
2. The state/locking layer, which refuses to record a
   transition that would push the count beyond the hard
   cap.

The hard cap is hard-coded to 2 for v1 (DIRECTIVE.md
Section 8.4).

This module contains no product-specific code.
"""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from bbr.network import DEFAULT_MAX_ACTIVE_LABS, HARD_MAX_ACTIVE_LABS


DEFAULT_STATE_DIR = Path("state")
ACTIVE_LABS_INDEX = "active-labs.json"


class StateError(Exception):
    """Raised for any state-file or lock-file error."""


class ActiveLabCapExceeded(StateError):
    """Raised when the active-lab hard cap would be exceeded."""


def state_path(lab_id: str, base: Path = DEFAULT_STATE_DIR) -> Path:
    return base / f"{lab_id}.json"


def lock_path(lab_id: str, base: Path = DEFAULT_STATE_DIR) -> Path:
    return base / f"{lab_id}.lock"


def index_path(base: Path = DEFAULT_STATE_DIR) -> Path:
    return base / ACTIVE_LABS_INDEX


def hard_max_active_labs() -> int:
    """Return the hard maximum active-lab count for v1.

    Per DIRECTIVE.md Section 8.4 the default is 1 and the
    hard configurable maximum is 2. The CLI may lower the
    effective limit below this; it may never raise it above
    this. Enforced in the lock layer as well.
    """
    return HARD_MAX_ACTIVE_LABS


def default_max_active_labs() -> int:
    """Return the default active-lab limit (1 per DIRECTIVE)."""
    return DEFAULT_MAX_ACTIVE_LABS


def list_active_labs(base: Path = DEFAULT_STATE_DIR) -> list[str]:
    """Return the list of lab ids that currently have a
    non-DESTROYED runtime state file.

    The index is recomputed from the on-disk state files so
    the value is authoritative.
    """
    base.mkdir(parents=True, exist_ok=True)
    active: list[str] = []
    for p in base.glob("*.json"):
        if p.name == ACTIVE_LABS_INDEX:
            continue
        try:
            with p.open() as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        if data.get("state") != "DESTROYED":
            active.append(data.get("lab_id", p.stem))
    return sorted(active)


@contextmanager
def acquire_lock(lab_id: str, base: Path = DEFAULT_STATE_DIR) -> Iterator[None]:
    base.mkdir(parents=True, exist_ok=True)
    lp = lock_path(lab_id, base)
    fd = os.open(str(lp), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.write(fd, f"{os.getpid()}\n".encode())
    os.close(fd)
    try:
        yield
    finally:
        try:
            lp.unlink()
        except FileNotFoundError:
            pass


@contextmanager
def acquire_index_lock(base: Path = DEFAULT_STATE_DIR) -> Iterator[None]:
    base.mkdir(parents=True, exist_ok=True)
    lp = base / "active-labs.lock"
    fd = os.open(str(lp), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.write(fd, f"{os.getpid()}\n".encode())
    os.close(fd)
    try:
        yield
    finally:
        try:
            lp.unlink()
        except FileNotFoundError:
            pass


def assert_active_lab_cap(
    base: Path = DEFAULT_STATE_DIR,
    *,
    hard_max: int | None = None,
) -> None:
    """Enforce the active-lab hard cap. Called by the CLI
    before any state change that would add a new active
    lab. Called by the lock layer too.
    """
    cap = hard_max if hard_max is not None else HARD_MAX_ACTIVE_LABS
    active = list_active_labs(base)
    if len(active) >= cap:
        raise ActiveLabCapExceeded(
            f"active lab count {len(active)} reaches hard max {cap}"
        )


def read_state(lab_id: str, base: Path = DEFAULT_STATE_DIR) -> dict:
    p = state_path(lab_id, base)
    if not p.exists():
        raise StateError(f"lab {lab_id!r} has no state file at {p}")
    with p.open() as f:
        return json.load(f)


def append_transition(
    lab_id: str,
    *,
    from_state: str,
    to_state: str,
    operator: str,
    rationale: str,
    base: Path = DEFAULT_STATE_DIR,
) -> None:
    """Append a transition record. The state file is updated
    atomically with the lock held. Enforces the active-lab
    hard cap before recording transitions that would add a
    new active lab.
    """
    base.mkdir(parents=True, exist_ok=True)
    p = state_path(lab_id, base)
    # State changes that introduce a new active lab must not
    # exceed the hard cap. Transitions among existing labs
    # (for example READY -> TESTING) are not subject to the
    # cap check.
    new_active_introduced = from_state == "DEFINED"
    if new_active_introduced:
        with acquire_index_lock(base):
            assert_active_lab_cap(base)
    with acquire_lock(lab_id, base):
        if p.exists():
            with p.open() as f:
                state = json.load(f)
        else:
            state = {
                "lab_id": lab_id,
                "created_at": _now_iso(),
                "transitions": [],
            }
        state.setdefault("state", to_state)
        state["state"] = to_state
        state["updated_at"] = _now_iso()
        state.setdefault("transitions", []).append({
            "from": from_state,
            "to": to_state,
            "at": _now_iso(),
            "operator": operator,
            "rationale": rationale,
        })
        tmp = p.with_suffix(".tmp")
        with tmp.open("w") as f:
            json.dump(state, f, indent=2, sort_keys=True)
        os.replace(tmp, p)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


__all__ = [
    "ACTIVE_LABS_INDEX",
    "DEFAULT_STATE_DIR",
    "ActiveLabCapExceeded",
    "StateError",
    "acquire_index_lock",
    "acquire_lock",
    "append_transition",
    "assert_active_lab_cap",
    "default_max_active_labs",
    "hard_max_active_labs",
    "index_path",
    "list_active_labs",
    "lock_path",
    "read_state",
    "state_path",
]