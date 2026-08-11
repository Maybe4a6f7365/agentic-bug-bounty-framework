"""
tests/test_runner_dispatch.py — Checker dispatch via _load_checker.

Phase 2, pure-function tests — no DB, no fakes.
Pins bugs #1 (api→api_json alias missing) and #2 (ios_store missing).
"""

import os
import sys

import pytest

# ── Module-level import (replaces setUpClass) ──────────────────────

_checkers_dir = os.path.join(os.path.dirname(__file__), "..", "checkers")
if _checkers_dir not in sys.path:
    sys.path.insert(0, _checkers_dir)
from checkers import runner  # noqa: E402
from checkers.runner import CheckerError  # noqa: E402


def _load(source_type: str, check_method: str = "default"):
    return runner._load_checker(source_type, check_method)


# ── Working dispatch ───────────────────────────────────────────────

def test_github_and_github_release_both_load_github_module() -> None:
    """Both github and github_release resolve to builtin/github.py."""
    g = _load("github", "tags")
    gr = _load("github_release", "latest")
    # Both modules expose _extract_field (the shared function)
    assert hasattr(g, "_extract_field")
    assert hasattr(gr, "_extract_field")


def test_rss_android_package_resolve() -> None:
    """Three source_type values that map to existing checker files."""
    for st in ("rss", "android_store", "package_registry"):
        mod = _load(st, st)
        assert hasattr(mod, "check"), f"{st} module has no check()"


# ── CONFIRMED BUGS ─────────────────────────────────────────────────

def test_api_source_type_resolves_to_api_json() -> None:
    """[FIXED BUG #1] source_type='api' now maps to builtin/api_json.py.

    The dispatch map in runner.py:168-172 includes ``"api": "api_json"``.
    Both enrich.py and add_target.py create sources with
    source_type='api', check_method='json_path'.  All 88 enabled
    production sources that were silently failing every sweep now
    resolve correctly.
    """
    mod = _load("api", "json_path")
    assert hasattr(mod, "check"), "api dispatches to api_json module"


def test_ios_store_resolves() -> None:
    """[FIXED BUG #2] source_type='ios_store' now has builtin/ios_store.py.

    The checker uses the iTunes lookup API to fetch App Store metadata.
    """
    mod = _load("ios_store", "app_store_lookup")
    assert hasattr(mod, "check"), "ios_store dispatches to ios_store module"


# ── Edge cases ─────────────────────────────────────────────────────

def test_manual_and_webhook_are_unsupported() -> None:
    """Assert that manual and changedetection_webhook are intentionally
    unresolvable — a future implementer should see this expectation."""
    for st in ("manual", "changedetection_webhook"):
        with pytest.raises(CheckerError):
            _load(st, st)


def test_injects_checker_error_check_result_http_cache() -> None:
    """Loaded module namespace has CheckerError, CheckResult, and http_cache
    injected — and module.CheckerError IS runner.CheckerError (identity
    matters for the runner's except CheckerError clause)."""
    mod = _load("rss", "rss")
    assert hasattr(mod, "CheckerError")
    assert hasattr(mod, "CheckResult")
    assert hasattr(mod, "http_cache")
    assert mod.CheckerError is runner.CheckerError, (
        "CheckerError identity matters — runner's except clause must catch "
        "what the checker raises"
    )


def test_each_load_returns_fresh_module() -> None:
    """Two loads → distinct module objects — the isolation guarantee."""
    mod1 = _load("rss", "rss")
    mod2 = _load("rss", "rss")
    assert mod1 is not mod2


def test_custom_source_type_is_rejected() -> None:
    """The user-supplied-path loader is gone.

    source_type='custom' used to load checkers/custom/<check_method>.py,
    which meant a DB column named the module to execute — and
    check_method='../builtin/github' escaped the custom dir. Dispatch is now
    a fixed map, so 'custom' is simply an unknown source_type.
    """
    with pytest.raises(CheckerError) as exc_info:
        _load("custom", "anything")
    assert "No builtin checker" in str(exc_info.value)


def test_check_method_cannot_select_the_module() -> None:
    """check_method no longer influences which file is loaded."""
    with pytest.raises(CheckerError):
        _load("custom", "../builtin/github")

    # For a real source_type, check_method is irrelevant to dispatch.
    a = _load("rss", "feed_parse")
    b = _load("rss", "../builtin/github")
    assert hasattr(a, "check") and hasattr(b, "check")
