"""
checkers/builtin/__init__.py — Re-export CheckerError and CheckResult for builtin checkers.

Builtin checkers import via `from . import CheckerError, CheckResult`.
The runner's importlib path adds the builtin/ directory to sys.modules,
so `from . import ...` resolves against this package.
"""

# These classes are defined in runner.py but re-exported here
# so each builtin checker module can `from . import CheckerError, CheckResult`.
# The runner injects them into the module namespace at load time.
import sys
_parent = sys.modules.get("checkers.runner")
if _parent:
    CheckerError = _parent.CheckerError
    CheckResult = _parent.CheckResult
else:
    # Fallback for direct execution / testing
    from dataclasses import dataclass
    from typing import Optional

    class CheckerError(Exception):
        def __init__(self, code: str, message: str):
            self.code = code
            self.message = message
            super().__init__(f"[{code}] {message}")

    @dataclass
    class CheckResult:
        changed: bool
        version_value: Optional[str] = None
        immutable_identifier: Optional[str] = None
        commit_hash: Optional[str] = None
        release_id: Optional[str] = None
        build_number: Optional[str] = None
        published_at: Optional[str] = None
        content_hash: Optional[str] = None
        raw_metadata: Optional[dict] = None
        change_type: Optional[str] = None
