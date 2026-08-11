import json
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "terraform/modules/compute-node/templates/raw-vm-startup.sh.tftpl"
MANIFEST = ROOT / "packs/wordpress-smoke/manifest.json"


def _template() -> str:
    return TEMPLATE.read_text()


def _driver_payload() -> dict:
    manifest = json.loads(MANIFEST.read_text())
    return manifest["topology"]["nodes"][0]["driver_payload"]


def _artifact_paths() -> tuple[Path, Path] | None:
    candidates = []
    if artifact_dir := os.environ.get("BBR_R2_ARTIFACT_DIR"):
        candidates.append(Path(artifact_dir))
    candidates.extend((ROOT / "artifacts", Path("/tmp")))

    for directory in candidates:
        artifact = directory / "artifact.tar.zst"
        signature = directory / "artifact.tar.zst.minisig"
        if artifact.is_file() and signature.is_file():
            return artifact, signature
    return None


def _minisign_command(raw_key: str, artifact: Path, signature: Path) -> list[str]:
    return [
        "minisign",
        "-V",
        "-P",
        raw_key,
        "-m",
        str(artifact),
        "-x",
        str(signature),
    ]


def _verification_block() -> str:
    match = re.search(
        r'CURRENT_STAGE="minisign"\nminisign -V \\\n'
        r'.*?\necho "Minisign verification successful"',
        _template(),
        flags=re.DOTALL,
    )
    assert match is not None
    return match.group(0)


def test_template_uses_raw_public_key_option():
    template = _template()

    assert '-P "$MINISIGN_PUBLIC_KEY"' in template
    assert "-p /var/lib/bbr/keys/minisign.pub" not in template
    assert 'echo "$MINISIGN_PUBLIC_KEY" >' not in template
    assert "/var/lib/bbr/keys" not in template


def test_empty_public_key_guard_exits_31():
    match = re.search(
        r'if \[\[ -z "\$MINISIGN_PUBLIC_KEY" \]\]; then\n.*?\nfi',
        _template(),
        flags=re.DOTALL,
    )
    assert match is not None
    script = "\n".join(
        (
            'MINISIGN_PUBLIC_KEY=""',
            'CURRENT_STAGE="preflight"',
            "date() { printf '2026-07-27T00:00:00Z\\n'; }",
            match.group(0),
        )
    )

    result = subprocess.run(["bash", "-c", script], text=True, capture_output=True)

    assert result.returncode == 31
    assert result.stdout == "2026-07-27T00:00:00Z missing Minisign public key\n"


def test_wrong_raw_key_exits_31_and_writes_minisign_failure_marker(tmp_path):
    template = _template()
    function = re.search(
        r"write_failure_marker\(\) \{\n.*?\n\}",
        template,
        flags=re.DOTALL,
    )
    assert function is not None
    marker_root = tmp_path / "var/lib/bbr"
    marker_function = function.group(0).replace("/var/lib/bbr", str(marker_root))
    artifact_paths = _artifact_paths()

    if shutil.which("minisign") and artifact_paths:
        artifact, signature = artifact_paths
        raw_key = _driver_payload()["minisign_public_key"]
        wrong_key = f"{raw_key[:-1]}{'3' if raw_key[-1] != '3' else '2'}"
        setup = "\n".join(
            (
                f"MINISIGN_PUBLIC_KEY={shlex.quote(wrong_key)}",
                f"work_dir={shlex.quote(str(artifact.parent))}",
            )
        )
    else:
        setup = "\n".join(
            (
                "minisign() { return 1; }",
                'MINISIGN_PUBLIC_KEY="deterministic-wrong-key"',
                f"work_dir={shlex.quote(str(tmp_path))}",
                f"touch {shlex.quote(str(tmp_path / 'artifact.tar.zst'))}",
                f"touch {shlex.quote(str(tmp_path / 'artifact.tar.zst.minisig'))}",
            )
        )

    script = "\n".join(
        (
            "set -uo pipefail",
            'ARTIFACT_URI="gs://test/artifact.tar.zst"',
            'CURRENT_STAGE="preflight"',
            marker_function,
            "trap 'rc=$?; if [[ $rc -ne 0 ]]; then write_failure_marker \"$rc\"; fi' EXIT",
            setup,
            _verification_block(),
        )
    )
    result = subprocess.run(["bash", "-c", script], text=True, capture_output=True)

    assert result.returncode == 31
    marker = json.loads((marker_root / "failure").read_text())
    assert marker["stage"] == "minisign"
    assert marker["exit_code"] == 31


def test_real_r2_artifact_verifies_with_manifest_raw_key():
    if not shutil.which("minisign"):
        pytest.skip("minisign is not installed")
    artifact_paths = _artifact_paths()
    if artifact_paths is None:
        pytest.skip("r2 artifact and signature are not available locally")

    artifact, signature = artifact_paths
    raw_key = _driver_payload()["minisign_public_key"]
    result = subprocess.run(
        _minisign_command(raw_key, artifact, signature),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Signature and comment signature verified" in result.stdout


def test_real_raw_key_reaches_sha256_stage():
    if not shutil.which("minisign"):
        pytest.skip("minisign is not installed")
    artifact_paths = _artifact_paths()
    if artifact_paths is None:
        pytest.skip("r2 artifact and signature are not available locally")

    artifact, _signature = artifact_paths
    raw_key = _driver_payload()["minisign_public_key"]
    script = "\n".join(
        (
            f"MINISIGN_PUBLIC_KEY={shlex.quote(raw_key)}",
            f"work_dir={shlex.quote(str(artifact.parent))}",
            _verification_block(),
            'CURRENT_STAGE="sha256"',
            'printf "stage=%s\\n" "$CURRENT_STAGE"',
        )
    )
    result = subprocess.run(["bash", "-c", script], text=True, capture_output=True)

    assert result.returncode == 0, result.stderr
    assert "stage=sha256" in result.stdout
