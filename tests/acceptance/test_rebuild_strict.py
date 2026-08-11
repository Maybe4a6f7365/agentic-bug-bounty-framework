import hashlib
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

RELEASE = Path(os.environ.get("BBR_RELEASE_DIR", "/home/admin/.bbr-build/wordpress-smoke-001-r2"))
SOURCE = Path(os.environ.get("BBR_BUNDLE_DIR", "/home/admin/.bbr-build/wordpress-smoke-001-r2-source"))


def test_bit_identical_rebuild():
    required = os.environ.get("BBR_REQUIRED_RELEASE_MODE") == "1"
    artifact = RELEASE / "artifact.tar.zst"
    if not artifact.is_file() or not SOURCE.is_dir():
        if required:
            pytest.fail("required rebuild inputs missing")
        pytest.skip("optional rebuild inputs not present")
    with tempfile.TemporaryDirectory() as temporary:
        temp = Path(temporary)
        raw_tar = temp / "artifact.tar"
        rebuilt = temp / "artifact.tar.zst"
        subprocess.run([
            "tar", "--sort=name", "--mtime=@0", "--owner=0", "--group=0",
            "--numeric-owner", "--create", "--file", str(raw_tar), "-C", str(SOURCE), ".",
        ], check=True)
        subprocess.run([
            "zstd", "-19", "--no-progress", "-f", str(raw_tar), "-o", str(rebuilt),
        ], check=True)
        assert hashlib.sha256(rebuilt.read_bytes()).hexdigest() == hashlib.sha256(artifact.read_bytes()).hexdigest()
