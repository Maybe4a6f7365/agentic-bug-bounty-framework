import json
import hashlib
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RELEASE = Path(os.environ.get("BBR_RELEASE_DIR", "/home/admin/.bbr-build/wordpress-smoke-001-r2"))


@pytest.mark.skipif(os.environ.get("BBR_REQUIRED_RELEASE_MODE") != "1", reason="required-mode only")
def test_required_release_inputs_and_metadata():
    required = [
        "artifact.tar.zst", "artifact.tar.zst.sha256",
        "artifact.tar.zst.minisig", "manifest.json", "package-inputs.json",
    ]
    for name in required:
        assert (RELEASE / name).is_file(), f"missing required release input: {name}"
    manifest = json.loads((RELEASE / "manifest.json").read_text())
    packages = json.loads((RELEASE / "package-inputs.json").read_text())
    assert manifest["artifact_version"] == "6.8.2-r2"
    entries = packages["packages"]
    assert len(entries) == 160
    names = [item["file"] for item in entries]
    assert len(names) == len(set(names)), "duplicate package filenames"
    package_dir = RELEASE.with_name(RELEASE.name + "-source") / "packages"
    actual = {path.name for path in package_dir.glob("*.deb")}
    assert actual == set(names), (
        f"missing={sorted(set(names) - actual)}, extra={sorted(actual - set(names))}"
    )
    for item in entries:
        digest = hashlib.sha256((package_dir / item["file"]).read_bytes()).hexdigest()
        assert digest == item["sha256"], item["file"]
