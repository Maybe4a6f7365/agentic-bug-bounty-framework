"""Typed bootstrap failures and their stable Phase 4 exit codes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class BootstrapError(RuntimeError):
    code: int
    message: str
    phase: str = "BOOTSTRAP"
    artifact_uri: Optional[str] = None
    public_key_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not 30 <= self.code <= 39:
            raise ValueError("bootstrap error code must be in range 30-39")
        RuntimeError.__init__(self, self.message)

