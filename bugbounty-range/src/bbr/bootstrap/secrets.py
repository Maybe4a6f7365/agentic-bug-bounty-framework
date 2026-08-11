"""Runtime-only secret helpers."""

from __future__ import annotations

import contextlib
import os
import pwd
import grp
import subprocess
from pathlib import Path
from typing import Iterator


def generate_db_password() -> str:
    result = subprocess.run(
        ["openssl", "rand", "-base64", "32"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def shuffle_wp_salts(wp_cli_path: str) -> dict:
    result = subprocess.run(
        [wp_cli_path, "--allow-root", "config", "shuffle-salts"],
        capture_output=True, text=True, check=True,
    )
    return {"status": "shuffled", "returncode": result.returncode}


def write_secret_file(
    path: Path, content: str, mode: int = 0o600, owner: str = "root:root"
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(path, flags, mode)
    try:
        os.write(fd, content.encode())
        os.fsync(fd)
        os.fchmod(fd, mode)
        user, group = owner.split(":", 1)
        uid = pwd.getpwnam(user).pw_uid
        gid = grp.getgrnam(group).gr_gid
        current = os.fstat(fd)
        if (current.st_uid, current.st_gid) != (uid, gid):
            os.fchown(fd, uid, gid)
    finally:
        os.close(fd)


@contextlib.contextmanager
def secret_safe_context() -> Iterator[None]:
    """Disable shell xtrace environment hints and restore them exactly."""
    old_ps4 = os.environ.pop("PS4", None)
    old_shellopts = os.environ.get("SHELLOPTS")
    try:
        yield
    finally:
        if old_ps4 is not None:
            os.environ["PS4"] = old_ps4
        if old_shellopts is not None:
            os.environ["SHELLOPTS"] = old_shellopts
