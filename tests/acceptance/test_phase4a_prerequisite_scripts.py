import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PACK_DIR = ROOT / "platform/your-lab-name/packs/wordpress-smoke"
BAKE = ROOT / "platform/your-lab-name/tools/bake_bootstrap_image.sh"
UPLOAD = ROOT / "platform/your-lab-name/tools/upload_wordpress_release.sh"
INPUT_SPEC = PACK_DIR / "bootstrap-image-inputs.json"
REAL_INPUTS = Path("/home/admin/.bbr-build/bootstrap-image-inputs-20260727-v2")
FILES = [
    "artifact.tar.zst",
    "artifact.tar.zst.sha256",
    "artifact.tar.zst.minisig",
    "manifest.json",
    "package-inputs.json",
]
TARGET = "gs://bbr-bootstrap-your-lab-name-your-researcher-handle/artifacts/wordpress/6.8.2-r2"


def test_bake_script_is_bootstrap_only_and_deterministic():
    text = BAKE.read_text()
    spec = json.loads(INPUT_SPEC.read_text())
    assert spec["source_image_self_link"] == (
        "projects/debian-cloud/global/images/debian-12-bookworm-v20260721"
    )
    assert spec["boot_disk"] == {"type": "pd-standard", "size_gb": 20}
    assert spec["minisign"]["sha256"] == (
        "9a599b48ba6eb7b1e80f12f36b94ceca7c00b7a5173c95c3efc88d9822957e73"
    )
    assert len(spec["packages"]) == 7
    assert not {
        "nginx", "nginx-light", "php8.2-fpm", "mariadb-server", "wordpress", "wp-cli"
    } & {item["package"] for item in spec["packages"]}
    for required in (
        '--network="$network"',
        'network="bbr-shared-vpc"',
        '--subnet="$subnet"',
        'subnet="bbr-bastion-subnet"',
        '--tags="$network_tag"',
        'network_tag="ssh-iap"',
        "--no-address",
        "--no-service-account",
        "--no-scopes",
        "enable-oslogin=TRUE",
        "block-project-ssh-keys=TRUE",
        'gcloud compute disks create "$temp_disk"',
        'source_image_project="debian-cloud"',
        'source_image_name="debian-12-bookworm-v20260721"',
        'source_image_self_link="projects/${source_image_project}/global/images/${source_image_name}"',
        '--image="$source_image_name"',
        '--image-project="$source_image_project"',
        "--type=pd-standard",
        "--size=20GB",
        'machine_type="e2-micro"',
        '--machine-type="$machine_type"',
        "--architecture=X86_64",
        "--guest-os-features=UEFI_COMPATIBLE",
        '--disk="name=${temp_disk},boot=yes,auto-delete=no,device-name=${temp_disk}"',
        "dpkg --unpack ./*.deb",
        "dpkg --configure -a",
        "sha256sum -c bootstrap-inputs.sha256",
        "UEFI_COMPATIBLE",
        "trap cleanup EXIT",
        "refusing to overwrite or delete existing target image",
    ):
        assert required in text
    assert "image-family" not in text.lower()
    assert "--image-family" not in text
    assert "wordpress-smoke-001-r2-source/packages" not in text
    assert "package-inputs.json" not in text
    assert "160 pinned" not in text
    assert "--boot-disk-name" not in text
    assert "--boot-disk-device-name" not in text
    disk_create = text.index('gcloud compute disks create "$temp_disk"')
    disk_created = text.index('disk_created="yes"', disk_create)
    instance_create = text.index('gcloud compute instances create "$temp_vm"')
    vm_created = text.index('vm_created="yes"', instance_create)
    assert disk_create < disk_created < instance_create < vm_created
    instance_command = text[instance_create:vm_created]
    assert '--image="$source_image_name"' not in instance_command
    assert instance_command.count("--disk=") == 1
    assert (
        'gcloud compute images create "$target_image" \\\n'
        '  --project="$project" \\\n'
        '  --source-disk="$temp_disk" \\\n'
        '  --source-disk-zone="$zone" \\\n'
        '  --architecture=X86_64 \\\n'
        '  --guest-os-features=UEFI_COMPATIBLE'
    ) in text
    for forbidden in ("apt update", "apt install", "wget ", "github.com", "deb.debian.org"):
        assert forbidden not in text.lower()


@pytest.mark.skipif(not REAL_INPUTS.is_dir(), reason="bootstrap-only local inputs absent")
def test_bake_dry_run_has_full_plan_and_never_calls_gcloud(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    gcloud = fake_bin / "gcloud"
    gcloud.write_text("#!/usr/bin/env bash\nexit 97\n")
    gcloud.chmod(0o755)
    result = subprocess.run(
        [str(BAKE)],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "BBR_BAKE_RUN_ID": "acceptance-dry-run",
            "BBR_BOOTSTRAP_IMAGE_INPUT_DIR": str(REAL_INPUTS),
        },
    )
    assert result.returncode == 0, result.stderr
    for value in (
        "your-lab-name-your-researcher-handle",
        "europe-west3-a",
        "bbr-shared-vpc",
        "bbr-bastion-subnet",
        "ssh-iap",
        "external IP: NONE",
        "source image project: debian-cloud",
        "source image name: debian-12-bookworm-v20260721",
        "temporary boot disk size: 20GB",
        "bake VM machine type: e2-micro",
        "bbr-image-bake-acceptance-dry-run",
        "create temporary boot disk bbr-image-bake-acceptance-dry-run-boot "
        "from pinned source image "
        "projects/debian-cloud/global/images/debian-12-bookworm-v20260721",
        "attach existing disk bbr-image-bake-acceptance-dry-run-boot "
        "as the VM boot disk (boot=yes; auto-delete=no",
        "dpkg --unpack",
        "cleanup temporary VM and disk",
        "DRY-RUN: no mutating command executed",
    ):
        assert value in result.stdout


def _write_bake_gcloud(tmp_path: Path):
    fake_bin = tmp_path / "bake-bin"
    fake_bin.mkdir()
    gcloud = fake_bin / "gcloud"
    gcloud.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> "$GCLOUD_LOG"
command=$*
if [[ "$command" == compute\\ images\\ list* ]] ||
   [[ "$command" == compute\\ instances\\ list* ]] ||
   [[ "$command" == compute\\ disks\\ list* ]]; then
  exit 0
fi
if [[ "$command" == compute\\ disks\\ create* ]]; then
  [[ "${FAIL_AT:-}" != "disk-create" ]] || exit 41
  exit 0
fi
if [[ "$command" == compute\\ instances\\ create* ]]; then
  [[ "${FAIL_AT:-}" != "instance-create" ]] || exit 42
  exit 0
fi
if [[ "$command" == compute\\ scp* ]]; then
  [[ "${FAIL_AT:-}" != "after-instance" ]] || exit 43
  exit 0
fi
if [[ "$command" == compute\\ images\\ describe* ]]; then
  printf '%s\\n' '{"name":"bbr-debian-12-bootstrap-tools-20260727-v2","selfLink":"https://www.googleapis.com/compute/v1/projects/your-lab-name-your-researcher-handle/global/images/bbr-debian-12-bootstrap-tools-20260727-v2","status":"READY","guestOsFeatures":[{"type":"UEFI_COMPATIBLE"}]}'
  exit 0
fi
exit 0
"""
    )
    gcloud.chmod(0o755)
    return fake_bin


def _run_bake_execute(tmp_path: Path, fail_at=None):
    fake_bin = _write_bake_gcloud(tmp_path)
    log = tmp_path / "bake-gcloud.log"
    result = subprocess.run(
        [str(BAKE)],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "BBR_BAKE_RUN_ID": "mock-lifecycle",
            "BBR_BOOTSTRAP_IMAGE_INPUT_DIR": str(REAL_INPUTS),
            "BBR_IMAGE_BAKE_EXECUTE": "yes",
            "GCLOUD_LOG": str(log),
            "FAIL_AT": fail_at or "",
        },
    )
    return result, log.read_text().splitlines()


@pytest.mark.skipif(not REAL_INPUTS.is_dir(), reason="bootstrap-only local inputs absent")
@pytest.mark.parametrize(
    ("fail_at", "expected_deletes"),
    [
        ("disk-create", []),
        ("instance-create", ["compute disks delete"]),
        ("after-instance", ["compute instances delete", "compute disks delete"]),
        (None, ["compute instances delete", "compute disks delete"]),
    ],
    ids=["disk-create-fails", "instance-create-fails", "post-instance-fails", "success"],
)
def test_bake_cleanup_tracks_only_created_resources(tmp_path, fail_at, expected_deletes):
    result, calls = _run_bake_execute(tmp_path, fail_at)
    if fail_at:
        assert result.returncode != 0
    else:
        assert result.returncode == 0, result.stderr

    joined = "\n".join(calls)
    deletes = [line for line in calls if " delete " in f" {line} "]
    assert len(deletes) == len(expected_deletes)
    for expected, actual in zip(expected_deletes, deletes):
        assert expected in actual
    if fail_at != "disk-create":
        assert (
            "compute disks create bbr-image-bake-mock-lifecycle-boot "
            "--project=your-lab-name-your-researcher-handle --zone=europe-west3-a "
            "--image=debian-12-bookworm-v20260721 "
            "--image-project=debian-cloud --type=pd-standard --size=20GB"
        ) in joined
    if fail_at not in ("disk-create", "instance-create"):
        instance_call = next(
            line for line in calls if line.startswith("compute instances create ")
        )
        assert (
            "--disk=name=bbr-image-bake-mock-lifecycle-boot,boot=yes,"
            "auto-delete=no,device-name=bbr-image-bake-mock-lifecycle-boot"
        ) in instance_call
        assert " --image=" not in f" {instance_call}"
        assert " --machine-type=e2-micro " in f" {instance_call} "
    if fail_at is None:
        assert (
            "compute images create bbr-debian-12-bootstrap-tools-20260727-v2 "
            "--project=your-lab-name-your-researcher-handle "
            "--source-disk=bbr-image-bake-mock-lifecycle-boot "
            "--source-disk-zone=europe-west3-a "
            "--architecture=X86_64 --guest-os-features=UEFI_COMPATIBLE"
        ) in joined


def _write_release(directory: Path):
    directory.mkdir()
    artifact = b"immutable r2 test artifact"
    (directory / "artifact.tar.zst").write_bytes(artifact)
    digest = hashlib.sha256(artifact).hexdigest()
    (directory / "artifact.tar.zst.sha256").write_text(
        f"{digest}  artifact.tar.zst\n"
    )
    (directory / "artifact.tar.zst.minisig").write_text("test signature\n")
    pack = json.loads((PACK_DIR / "manifest.json").read_text())
    payload = pack["topology"]["nodes"][0]["driver_payload"]
    manifest = {
        "artifact_version": "6.8.2-r2",
        "bootstrap_version": payload["bootstrap_version"],
        "wordpress_version": payload["wordpress_version"],
        "artifact_sha256": payload["artifact_sha256"],
        "artifact_signature": payload["artifact_signature"],
        "supported_platform": payload["supported_platform"],
        "git_commit": payload["git_commit"],
        "build_id": payload["build_id"],
    }
    (directory / "manifest.json").write_text(json.dumps(manifest))
    (directory / "package-inputs.json").write_text('{"packages":[]}\n')


def _write_fake_tools(tmp_path: Path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    minisign = fake_bin / "minisign"
    minisign.write_text("#!/usr/bin/env bash\nexit 0\n")
    minisign.chmod(0o755)
    gcloud = fake_bin / "gcloud"
    gcloud.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> "$GCLOUD_LOG"
shift
case "$1" in
  objects)
    [[ "$2" == "describe" ]]
    object="${3##*/}"
    [[ -f "$FAKE_REMOTE/$object" ]]
    ;;
  cp)
    shift
    if [[ "${1:-}" == "--if-generation-match=0" ]]; then
      shift
      source_path=$1
      destination=$2
      object="${destination##*/}"
      [[ ! -e "$FAKE_REMOTE/$object" ]]
      cp "$source_path" "$FAKE_REMOTE/$object"
    else
      source_path=$1
      destination=$2
      if [[ "$source_path" == gs://* ]]; then
        object="${source_path##*/}"
        cp "$FAKE_REMOTE/$object" "$destination"
      else
        exit 88
      fi
    fi
    ;;
  ls)
    for path in "$FAKE_REMOTE"/*; do
      [[ -f "$path" ]] || continue
      printf '%s/%s\\n' "$TARGET" "${path##*/}"
    done
    ;;
  *)
    exit 89
    ;;
esac
"""
    )
    gcloud.chmod(0o755)
    return fake_bin


def _run_upload(tmp_path: Path, present, divergent=None, execute=True):
    release = tmp_path / "release"
    remote = tmp_path / "remote"
    remote.mkdir()
    _write_release(release)
    for name in present:
        shutil.copy2(release / name, remote / name)
    if divergent:
        (remote / divergent).write_bytes(b"divergent remote content")
    fake_bin = _write_fake_tools(tmp_path)
    log = tmp_path / "gcloud.log"
    result = subprocess.run(
        [str(UPLOAD)],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "BBR_RELEASE_DIR": str(release),
            "BBR_MINISIGN_PUBLIC_KEY": str(tmp_path / "public.key"),
            "BBR_RELEASE_UPLOAD_EXECUTE": "yes" if execute else "no",
            "FAKE_REMOTE": str(remote),
            "GCLOUD_LOG": str(log),
            "TARGET": TARGET,
        },
    )
    return result, release, remote, log


@pytest.mark.parametrize(
    "present",
    [
        [],
        FILES,
        FILES[:2],
    ],
    ids=["empty-prefix", "fully-present-identical", "partially-present-identical"],
)
def test_upload_is_resumable_and_final_set_is_identical(tmp_path, present):
    result, release, remote, log = _run_upload(tmp_path, present)
    assert result.returncode == 0, result.stderr
    assert sorted(path.name for path in remote.iterdir()) == sorted(FILES)
    for name in FILES:
        assert (remote / name).read_bytes() == (release / name).read_bytes()
    calls = log.read_text()
    call_lines = calls.splitlines()
    for name in present:
        assert not any(
            line == f"storage cp --if-generation-match=0 {release / name} {TARGET}/{name}"
            for line in call_lines
        )
    for name in set(FILES) - set(present):
        assert f"--if-generation-match=0 {release / name} {TARGET}/{name}" in calls
    assert " delete " not in f" {calls} "
    assert "6.8.2-r1" not in calls


def test_upload_aborts_on_first_divergent_existing_object(tmp_path):
    result, _, _, log = _run_upload(
        tmp_path, ["artifact.tar.zst"], divergent="artifact.tar.zst"
    )
    assert result.returncode != 0
    assert "existing remote object diverges: artifact.tar.zst" in result.stderr
    assert "--if-generation-match=0" not in log.read_text()


def test_upload_dry_run_performs_no_remote_operation(tmp_path):
    result, _, _, log = _run_upload(tmp_path, [], execute=False)
    assert result.returncode == 0, result.stderr
    assert "DRY-RUN: no remote read or mutating command executed" in result.stdout
    assert not log.exists()


def test_upload_script_has_full_post_verification_and_no_delete():
    text = UPLOAD.read_text()
    assert 'gcloud storage objects describe "$remote"' in text
    assert "--if-generation-match=0" in text
    assert 'downloaded_sha="$(sha256sum' in text
    assert "remote prefix does not contain exactly five objects" in text
    assert "gcloud storage rm" not in text
    assert "gcloud storage objects delete" not in text
