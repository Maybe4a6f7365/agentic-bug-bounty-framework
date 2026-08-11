"""Atomic, merge-only Phase 4 runtime-state extensions."""

from __future__ import annotations

import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any


def _update(state_file: Path, changes: dict[str, Any]) -> None:
    state = json.loads(state_file.read_text()) if state_file.exists() else {}
    history = deepcopy(state.get("transition_history"))
    state.update(changes)
    if history is not None:
        state["transition_history"] = history
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", dir=state_file.parent, prefix=state_file.name + ".", delete=False
    ) as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, state_file)
    directory_fd = os.open(state_file.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def write_artifact_fields(
    state_file: Path, artifact_version: str, artifact_uri: str,
    artifact_sha256: str, artifact_signature: str, minisign_public_key: Any,
) -> None:
    _update(state_file, {
        "artifact_version": artifact_version,
        "artifact_uri": artifact_uri,
        "artifact_sha256": artifact_sha256,
        "artifact_signature": artifact_signature,
        "minisign_public_key": minisign_public_key,
    })


def write_timestamps(state_file: Path, **timestamps: str | None) -> None:
    allowed = {"bootstrap_started_at", "bootstrap_finished_at",
               "install_started_at", "install_finished_at"}
    _update(state_file, {k: v for k, v in timestamps.items()
                         if k in allowed and v is not None})


def write_substate(state_file: Path, substate_name: str, data: dict) -> None:
    allowed = {"bootstrap_state", "install_state", "configuring_state",
               "health_state", "failure_state", "rollback_state"}
    if substate_name not in allowed:
        raise ValueError(f"unsupported substate {substate_name!r}")
    state = json.loads(state_file.read_text()) if state_file.exists() else {}
    current = state.get(substate_name)
    if isinstance(current, list):
        value = current + [deepcopy(data)]
    elif current is None:
        value = [deepcopy(data)]
    else:
        value = [current, deepcopy(data)]
    _update(state_file, {substate_name: value})


def update_health_status(
    state_file: Path, status: str, consecutive_passes: int
) -> None:
    _update(state_file, {
        "health_status": status,
        "health_state": {
            "status": status,
            "consecutive_passes": consecutive_passes,
        },
    })
