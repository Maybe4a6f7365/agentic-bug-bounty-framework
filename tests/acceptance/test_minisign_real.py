import os
import subprocess
from pathlib import Path

import pytest

ARTIFACT_DIR = Path(os.environ.get("BBR_RELEASE_DIR", "/home/admin/.bbr-build/wordpress-smoke-001-r2"))
PUB = Path("/home/admin/.bbr-keys/minisign.pub")


def test_production_minisign_signature():
    required = os.environ.get("BBR_REQUIRED_RELEASE_MODE") == "1"
    files = [ARTIFACT_DIR / "artifact.tar.zst", ARTIFACT_DIR / "artifact.tar.zst.minisig", PUB]
    if not all(p.is_file() for p in files):
        if required:
            pytest.fail("required release inputs missing")
        pytest.skip("optional release artifact/key not present")
    subprocess.run([
        "minisign", "-V", "-p", str(PUB), "-m", str(files[0]), "-x", str(files[1])
    ], check=True)
