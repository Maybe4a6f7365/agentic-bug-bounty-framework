"""Minisign, SHA-256, and bootstrap-manifest verification."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from .errors import BootstrapError


def verify_signature(artifact_path: Path, signature_path: Path, public_key: str) -> None:
    if not signature_path.is_file():
        raise BootstrapError(31, "SIGNATURE_MISSING", "SIGNATURE")
    result = subprocess.run(
        ["minisign", "-V", "-P", public_key, "-m", str(artifact_path),
         "-x", str(signature_path)],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise BootstrapError(
            31, f"SIGNATURE_INVALID: minisign_exit={result.returncode}", "SIGNATURE"
        )


def verify_sha256(artifact_path: Path, sha256_path: Path) -> None:
    if not sha256_path.is_file():
        raise BootstrapError(32, "SHA256_MISSING", "SHA256")
    result = subprocess.run(
        ["sha256sum", "-c", str(sha256_path.resolve())],
        cwd=str(artifact_path.parent), capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise BootstrapError(32, "SHA256_MISMATCH", "SHA256")


def verify_manifest(
    manifest_path: Path, computed_sha256: str, expected_platform: str
) -> None:
    try:
        data = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise BootstrapError(33, "MANIFEST_INVALID", "MANIFEST") from exc
    required = {
        "manifest_version": int,
        "artifact_version": str,
        "artifact_sha256": str,
        "supported_platform": str,
    }
    if any(not isinstance(data.get(key), kind) for key, kind in required.items()):
        raise BootstrapError(33, "MANIFEST_SCHEMA_INVALID", "MANIFEST")
    digest = data["artifact_sha256"]
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise BootstrapError(33, "MANIFEST_SCHEMA_INVALID", "MANIFEST")
    if digest != computed_sha256:
        raise BootstrapError(34, "MANIFEST_HASH_MISMATCH", "MANIFEST")
    if data["supported_platform"] != expected_platform:
        raise BootstrapError(34, "UNSUPPORTED_PLATFORM", "MANIFEST")


def compute_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_with_trust_store(
    artifact_path: Path, signature_path: Path, trust_store: list[dict]
) -> str:
    for entry in trust_store:
        try:
            verify_signature(artifact_path, signature_path, entry["public_key"])
            return str(entry["key_id"])
        except (BootstrapError, KeyError):
            continue
    raise BootstrapError(31, "TRUST_STORE_NO_VALID_SIGNATURE", "SIGNATURE")

