"""Unit tests for the lifecycle state machine."""
import pytest

from bbr.lifecycle.state_machine import (
    InvalidTransitionError,
    PHASE3_VALID_STATES,
    UnknownStateError,
    make_state,
    record_transition,
    transition,
    validate_state,
)


def test_valid_transition_defined_to_validated():
    assert transition("DEFINED", "VALIDATED") == "VALIDATED"


def test_invalid_transition_raises():
    with pytest.raises(InvalidTransitionError):
        transition("DEFINED", "CREATED")


def test_unknown_state_raises():
    with pytest.raises(UnknownStateError):
        validate_state("NONEXISTENT")
    with pytest.raises(UnknownStateError):
        transition("DEFINED", "NONEXISTENT")


def test_record_transition_appends_history():
    s = make_state("lab-1", "smoke-vm", "VALIDATED", operator_principal="user:t")
    s2 = record_transition(s, "PLANNED")
    assert s2["state"] == "PLANNED"
    assert s["state"] == "VALIDATED"  # original not mutated
    assert len(s2["transition_history"]) == 2
    assert s2["transition_history"][-1]["to"] == "PLANNED"


def test_testing_state_not_in_phase3_allow_list():
    assert "TESTING" not in PHASE3_VALID_STATES
    with pytest.raises(UnknownStateError):
        make_state("lab-1", "smoke-vm", "TESTING")


def test_destroy_path():
    s = make_state("lab-1", "smoke-vm", "READY")
    s = record_transition(s, "STOPPED")
    s = record_transition(s, "DESTROYED")
    assert s["state"] == "DESTROYED"
