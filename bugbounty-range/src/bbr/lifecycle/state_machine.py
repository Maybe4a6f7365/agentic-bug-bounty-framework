"""BugBountyRange lifecycle state machine — Phase 3.

Single deterministic state machine that governs every lab
lifetime. Transitions are validated against an explicit table;
an invalid transition raises InvalidTransitionError. The
state machine is product-agnostic.

State graph (DIRECTIVE.md Section 9):

  Plan path:
    DEFINED -> VALIDATED -> PLANNED

  Execute path:
    PLANNED -> CREATED -> BOOTSTRAPPING -> ISOLATED -> READY

  Destroy path:
    READY -> STOPPED -> DESTROYED
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

VALID_STATES = (
    "DEFINED",
    "VALIDATED",
    "PLANNED",
    "CREATED",
    "BOOTSTRAPPING",
    "VERIFYING_ARTIFACT",
    "INSTALLING",
    "CONFIGURING",
    "STARTING",
    "ISOLATED",
    "READY",
    "HEALTHY",
    "VERIFIED",
    "FAILURE",
    "ROLLBACK",
    "DESTROY_PLANNED",
    "TESTING",
    "STOPPED",
    "DESTROYED",
)

# Phase 3 vertical slice enforces a conservative subset. The
# full graph (TESTING) is reserved for Phase 4+ but the strings
# remain valid in the schema for forward compatibility.
PHASE3_VALID_STATES = frozenset(
    {"DEFINED", "VALIDATED", "PLANNED", "CREATED", "BOOTSTRAPPING",
     "ISOLATED", "READY", "STOPPED", "DESTROYED"}
)
PHASE4_VALID_STATES = frozenset(VALID_STATES)

TRANSITIONS = frozenset(
    {
        ("DEFINED", "VALIDATED"),
        ("VALIDATED", "PLANNED"),
        ("PLANNED", "CREATED"),
        ("CREATED", "BOOTSTRAPPING"),
        ("BOOTSTRAPPING", "ISOLATED"),
        ("BOOTSTRAPPING", "VERIFYING_ARTIFACT"),
        ("VERIFYING_ARTIFACT", "INSTALLING"),
        ("INSTALLING", "CONFIGURING"),
        ("CONFIGURING", "STARTING"),
        ("STARTING", "READY"),
        ("ISOLATED", "READY"),
        ("READY", "HEALTHY"),
        ("HEALTHY", "VERIFIED"),
        ("HEALTHY", "STOPPED"),
        ("VERIFIED", "STOPPED"),
        ("BOOTSTRAPPING", "FAILURE"),
        ("VERIFYING_ARTIFACT", "FAILURE"),
        ("INSTALLING", "FAILURE"),
        ("CONFIGURING", "FAILURE"),
        ("STARTING", "FAILURE"),
        ("FAILURE", "ROLLBACK"),
        ("FAILURE", "STOPPED"),
        ("PLANNED", "DESTROY_PLANNED"),
        ("ROLLBACK", "DESTROY_PLANNED"),
        ("STOPPED", "DESTROY_PLANNED"),
        ("DESTROY_PLANNED", "DESTROYED"),
        ("READY", "TESTING"),  # reserved
        ("TESTING", "READY"),  # reserved
        ("READY", "STOPPED"),
        ("STOPPED", "DESTROYED"),
    }
)


class InvalidTransitionError(RuntimeError):
    """Raised when a transition is not part of the state graph."""


class UnknownStateError(ValueError):
    """Raised when a state name is not in the schema."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def validate_state(state: str) -> None:
    if state not in VALID_STATES:
        raise UnknownStateError(f"unknown state {state!r}")


def transition(current: str, target: str) -> str:
    """Return target if the transition is valid; otherwise raise."""
    validate_state(current)
    validate_state(target)
    if (current, target) not in TRANSITIONS:
        raise InvalidTransitionError(
            f"invalid transition {current!r} -> {target!r}; "
            f"allowed from {current!r}: "
            f"{sorted(t for c, t in TRANSITIONS if c == current)}"
        )
    return target


def make_state(
    lab_id: str,
    pack_id: str,
    state: str,
    plan_file: str = "",
    plan_sha256: str = "",
    lab_subnet_cidr: str = "",
    state_prefix: str = "",
    operator_principal: str = "",
    nodes: Optional[List[Dict[str, Any]]] = None,
    ttl_deadline: str = "",
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a fresh runtime-state dict. Validation runs against
    PHASE3_VALID_STATES so accidental TESTING transitions are
    rejected at the CLI level even if the schema permits them."""
    if state not in PHASE3_VALID_STATES:
        raise UnknownStateError(
            f"state {state!r} not in Phase 3 vertical-slice allow-list"
        )
    validate_state(state)
    d: Dict[str, Any] = {
        "lab_id": lab_id,
        "pack_id": pack_id,
        "state": state,
        "lab_subnet_cidr": lab_subnet_cidr,
        "state_prefix": state_prefix,
        "plan_file": plan_file,
        "plan_sha256": plan_sha256,
        "operator_principal": operator_principal,
        "ttl_deadline": ttl_deadline,
        "nodes": nodes or [],
        "transition_history": [
            {"to": state, "at": _now_iso(), "by": operator_principal or "operator"}
        ],
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    if extra:
        d.update(extra)
    return d


_FAILURE_EXIT_CODES = {
    "BOOTSTRAPPING": {30},
    "VERIFYING_ARTIFACT": {31, 32, 33, 34, 35},
    "INSTALLING": {36},
    "CONFIGURING": {37},
    "STARTING": {38, 39},
}


def record_transition(
    state: Dict[str, Any], target: str, by: str = "operator",
    exit_code: Optional[int] = None,
) -> Dict[str, Any]:
    """Validate and apply a transition. Returns a new dict with
    updated state, updated_at, and appended transition_history
    entry. The input dict is not mutated."""
    current = state["state"]
    if target == "FAILURE":
        allowed_codes = _FAILURE_EXIT_CODES.get(current, set())
        if exit_code not in allowed_codes:
            raise InvalidTransitionError(
                f"failure transition from {current!r} requires exit code "
                f"in {sorted(allowed_codes)}, got {exit_code!r}"
            )
    elif exit_code not in (None, 0):
        raise InvalidTransitionError("successful transition requires exit_code 0 or None")
    new_state = transition(current, target)
    out = deepcopy(state)
    out["state"] = new_state
    out["updated_at"] = _now_iso()
    history = out["transition_history"]
    assert isinstance(history, list)
    entry = {"to": new_state, "at": out["updated_at"], "by": by}
    if exit_code is not None:
        entry["exit_code"] = exit_code
    history.append(entry)
    return out
