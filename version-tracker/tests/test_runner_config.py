"""
tests/test_runner_config.py — Config parsing via _parse_config.

Phase 2, pure-function tests — no DB, no fakes.
Pins bug #7: a malformed config JSON row aborts the entire batch.
"""

import os
import sys

import pytest

# ── Module-level import (replaces setUpClass) ──────────────────────

_checkers_dir = os.path.join(os.path.dirname(__file__), "..", "checkers")
if _checkers_dir not in sys.path:
    sys.path.insert(0, _checkers_dir)
from checkers import runner  # noqa: E402


def _parse(raw):
    return runner._parse_config(raw)


# ── Happy path ─────────────────────────────────────────────────────

def test_none_returns_empty_dict() -> None:
    assert _parse(None) == {}


def test_empty_string_returns_empty_dict() -> None:
    assert _parse("") == {}


def test_empty_json_object() -> None:
    assert _parse("{}") == {}


def test_valid_json_string_parsed() -> None:
    assert _parse('{"page_url": "https://x.com", "selector": "h1"}') == {
        "page_url": "https://x.com",
        "selector": "h1",
    }


def test_dict_passthrough_is_identity() -> None:
    """_parse_config(d) returns d itself — not a copy.

    This matters because _run_check_on_db injects _last_immutable_id
    and _last_obs_id into the caller's dict, mutating it in place.
    The parallel-mode row-reuse question depends on this contract.
    """
    d = {"k": "v"}
    assert _parse(d) is d


# ── GAP: JSON array as config ──────────────────────────────────────

def test_json_array_returns_list_not_dict() -> None:
    """[GAP] JSON array parsed as a list, not a dict.

    Schema does not constrain config to an object.  Downstream
    ``config.get(...)`` then raises AttributeError.
    """
    result = _parse("[1, 2]")
    assert isinstance(result, list)
    # Confirm it's not a dict
    with pytest.raises(AttributeError):
        result.get("key")


# ── Bug #7: malformed config aborts batch ──────────────────────────

def test_invalid_json_raises_json_decode_error() -> None:
    """Malformed JSON raises json.JSONDecodeError.

    In production, _parse_config is called at runner.py:207 OUTSIDE
    the try/except in _run_check_on_db.  A single malformed config
    row kills the entire nightly sweep.
    """
    with pytest.raises(Exception):
        _parse("{not json")
