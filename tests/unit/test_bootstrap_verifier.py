import hashlib
import json
from pathlib import Path

import pytest

from bbr.bootstrap.downloader import pull_artifact
from bbr.bootstrap.errors import BootstrapError
from bbr.bootstrap.verifier import verify_manifest, verify_sha256, verify_signature


def test_verify_signature_missing_returns_31(tmp_path):
    with pytest.raises(BootstrapError, match="SIGNATURE_MISSING") as error:
        verify_signature(tmp_path / "a", tmp_path / "missing", "key")
    assert error.value.code == 31


def test_verify_sha256_match_returns_0(tmp_path):
    artifact = tmp_path / "artifact.tar.zst"
    artifact.write_bytes(b"good")
    digest = hashlib.sha256(b"good").hexdigest()
    sidecar = tmp_path / "artifact.tar.zst.sha256"
    sidecar.write_text(f"{digest}  artifact.tar.zst\n")
    verify_sha256(artifact, sidecar)


def test_verify_sha256_mismatch_returns_32(tmp_path):
    artifact = tmp_path / "artifact.tar.zst"
    artifact.write_bytes(b"bad")
    sidecar = tmp_path / "artifact.tar.zst.sha256"
    sidecar.write_text(f"{'0' * 64}  artifact.tar.zst\n")
    with pytest.raises(BootstrapError) as error:
        verify_sha256(artifact, sidecar)
    assert error.value.code == 32


def _manifest(path: Path, digest="0" * 64, platform="projects/p/global/images/i"):
    path.write_text(json.dumps({
        "manifest_version": 1, "artifact_version": "1",
        "artifact_sha256": digest, "supported_platform": platform,
    }))


def test_verify_manifest_valid(tmp_path):
    path = tmp_path / "manifest.json"
    _manifest(path)
    verify_manifest(path, "0" * 64, "projects/p/global/images/i")


def test_verify_manifest_schema_invalid_returns_33(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text("{}")
    with pytest.raises(BootstrapError) as error:
        verify_manifest(path, "0" * 64, "projects/p/global/images/i")
    assert error.value.code == 33


@pytest.mark.parametrize("digest,platform", [
    ("1" * 64, "projects/p/global/images/i"),
    ("0" * 64, "projects/p/global/images/other"),
])
def test_verify_manifest_consistency_returns_34(tmp_path, digest, platform):
    path = tmp_path / "manifest.json"
    _manifest(path, digest=digest)
    with pytest.raises(BootstrapError) as error:
        verify_manifest(path, "0" * 64, platform)
    assert error.value.code == 34


def test_download_artifact_404_returns_30(tmp_path, monkeypatch):
    monkeypatch.setenv("BBR_TEST_MODE", "2")
    monkeypatch.delenv("BBR_TEST_ARTIFACT", raising=False)
    with pytest.raises(BootstrapError) as error:
        pull_artifact("gs://bucket/missing", tmp_path)
    assert error.value.code == 30


def test_download_artifact_200_returns_0(tmp_path, monkeypatch):
    fixture = tmp_path / "fixture"
    fixture.write_bytes(b"artifact")
    monkeypatch.setenv("BBR_TEST_MODE", "2")
    monkeypatch.setenv("BBR_TEST_ARTIFACT", str(fixture))
    assert pull_artifact("gs://bucket/object", tmp_path / "out").read_bytes() == b"artifact"


def test_file_test_mode(tmp_path, monkeypatch):
    fixture = tmp_path / "fixture"
    fixture.write_bytes(b"local")
    monkeypatch.setenv("BBR_TEST_MODE", "1")
    assert pull_artifact(fixture.as_uri(), tmp_path / "out").read_bytes() == b"local"

