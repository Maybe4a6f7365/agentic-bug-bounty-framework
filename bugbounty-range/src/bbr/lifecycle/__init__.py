"""Lifecycle state machine.

Phase 0 skeleton. Defines the 11 states and the allowed
transitions per DIRECTIVE.md Section 9. The state machine
must be generic. the reference target-specific transitions or
product-specific shortcuts are forbidden.

Usage:

    from bbr.lifecycle import StateMachine, LabState, LifecycleError

    sm = StateMachine()
    sm.assert_transition(LabState.DEFINED, LabState.VALIDATED)  # OK
    sm.assert_transition(LabState.READY, LabState.DESTROYED)    # raises
"""

from __future__ import annotations

from enum import Enum


class LabState(str, Enum):
    DEFINED = "DEFINED"
    VALIDATED = "VALIDATED"
    PLANNED = "PLANNED"
    CREATED = "CREATED"
    BOOTSTRAPPING = "BOOTSTRAPPING"
    ISOLATED = "ISOLATED"
    READY = "READY"
    TESTING = "TESTING"
    STOPPED = "STOPPED"
    DESTROYED = "DESTROYED"


# Forward transitions from DIRECTIVE.md Section 9.
FORWARD_TRANSITIONS: dict[LabState, set[LabState]] = {
    LabState.DEFINED: {LabState.VALIDATED},
    LabState.VALIDATED: {LabState.PLANNED},
    LabState.PLANNED: {LabState.CREATED},
    LabState.CREATED: {LabState.BOOTSTRAPPING, LabState.DESTROYED},
    LabState.BOOTSTRAPPING: {LabState.ISOLATED},
    LabState.ISOLATED: {LabState.READY},
    LabState.READY: {LabState.TESTING, LabState.STOPPED},
    LabState.TESTING: {LabState.READY, LabState.STOPPED},
    # Side transitions
    LabState.STOPPED: {LabState.READY, LabState.DESTROYED},
}


class LifecycleError(Exception):
    """Raised when a state transition is not permitted."""


class StateMachine:
    """Generic state machine. No product-specific branches."""

    def assert_transition(self, src: LabState, dst: LabState) -> None:
        allowed = FORWARD_TRANSITIONS.get(src, set())
        if dst not in allowed:
            raise LifecycleError(
                f"transition {src.value} -> {dst.value} is not permitted"
            )


__all__ = ["LabState", "StateMachine", "LifecycleError"]