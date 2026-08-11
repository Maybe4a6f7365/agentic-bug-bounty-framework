import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "platform/your-lab-name/packs/wordpress-smoke/manifest.json"
BUILD_ROOT = Path("/home/admin/.bbr-build")
KEY_ROOT = Path("/home/admin/.bbr-keys")
PROJECT = "your-lab-name-your-researcher-handle"
BUCKET = "gs://bbr-bootstrap-your-lab-name-your-researcher-handle"
IMAGE = "bbr-debian-12-with-minisign-20260727"


def _payload():
    return json.loads(PACK.read_text())["topology"]["nodes"][0]["driver_payload"]


def test_manifest_real_values():
    text = PACK.read_text()
    payload = _payload()
    assert "PLACEHOLDER" not in text
    assert "0000000000000000000000000000000000000000000000000000000000000000" not in text
    assert payload["artifact_sha256"] == payload["bootstrap_artifact_sha256"]
    assert len(payload["artifact_sha256"]) == 64
    assert payload["artifact_signature"]
    assert payload["wordpress_version"] == "6.8.2"
    assert payload["git_commit"] == "d20b05bf03e28e111ac6e973490e6070567f1397"
    assert payload["source_commit"] == payload["git_commit"]


def test_minisign_signature():
    artifact = BUILD_ROOT / "releases/wordpress/6.8.2-r1/artifact.tar.zst"
    signature = Path(f"{artifact}.minisig")
    public_key = KEY_ROOT / "minisign.pub"
    if not all(path.is_file() for path in (artifact, signature, public_key)):
        pytest.skip("local Phase-4A release or production public key is absent")
    subprocess.run(
        ["minisign", "-V", "-p", str(public_key), "-m", str(artifact), "-x", str(signature)],
        check=True,
    )


def test_artifact_build_reproducibility():
    artifact_dir = BUILD_ROOT / "releases/wordpress/6.8.2-r1"
    source_dir = BUILD_ROOT / "wordpress-smoke-001"
    input_manifest = BUILD_ROOT / "wordpress-smoke-001-input-manifest.json"
    if not all(path.exists() for path in (artifact_dir, source_dir, input_manifest)):
        pytest.skip("offline build cache is absent")
    subprocess.run(
        [
            str(ROOT / "platform/your-lab-name/tools/verify_bootstrap_tarball.sh"),
            "--artifact-dir", str(artifact_dir),
            "--minisign-pub", str(KEY_ROOT / "minisign.pub"),
            "--source-dir", str(source_dir),
            "--input-manifest", str(input_manifest),
        ],
        check=True,
    )


def _gcloud_json(*args):
    if not shutil.which("gcloud"):
        pytest.skip("gcloud is unavailable")
    result = subprocess.run(
        ["gcloud", *args, "--format=json"],
        capture_output=True, text=True,
        env={**os.environ, "CLOUDSDK_CORE_PROJECT": PROJECT},
    )
    if result.returncode:
        pytest.skip(f"GCP access unavailable: {result.stderr.strip()}")
    return json.loads(result.stdout)


def test_gcs_bucket_config():
    bucket = _gcloud_json("storage", "buckets", "describe", BUCKET)
    assert bucket["location"] == "EUROPE-WEST3"
    assert bucket["uniform_bucket_level_access"]
    assert bucket["public_access_prevention"] == "enforced"
    assert bucket["versioning_enabled"]


def test_custom_image_exists():
    image = _gcloud_json(
        "compute", "images", "describe", IMAGE, f"--project={PROJECT}"
    )
    assert image["status"] == "READY"
