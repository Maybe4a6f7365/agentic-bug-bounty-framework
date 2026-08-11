import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bbr import cli  # noqa: E402
from bbr.network import allocator  # noqa: E402
from bbr.plan_contract import WORDPRESS_ADDRESSES  # noqa: E402


HEAD = "a" * 40
PLAN_BYTES = b"reviewed destroy plan"
PLAN_SHA = hashlib.sha256(PLAN_BYTES).hexdigest()
EIGHT_ADDRESSES = tuple(
    address
    for address in WORDPRESS_ADDRESSES
    if address != "module.lab_node.google_compute_instance.node"
)


def _plan(addresses=EIGHT_ADDRESSES, actions=None):
    return {
        "resource_changes": [
            {
                "address": address,
                "change": {"actions": actions or ["delete"]},
            }
            for address in addresses
        ]
    }


def _state(state="PLANNED"):
    return {
        "lab_id": "wordpress-smoke-001",
        "pack_id": "wordpress-smoke",
        "state": state,
        "lab_subnet_cidr": "10.200.2.0/24",
        "transition_history": [
            {"to": "DEFINED", "at": "2026-07-27T00:00:00Z", "by": "operator"},
            {"to": "VALIDATED", "at": "2026-07-27T00:00:01Z", "by": "operator"},
            {"to": "PLANNED", "at": "2026-07-27T00:00:02Z", "by": "operator"},
        ],
    }


def _args(plan_path, **overrides):
    values = {
        "lab_id": "wordpress-smoke-001",
        "from_failure": False,
        "finalize": True,
        "plan_file": str(plan_path),
        "expected_sha256": PLAN_SHA,
        "expected_commit": HEAD,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def _setup_finalize(monkeypatch, tmp_path, state="PLANNED", plan_json=None):
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    state_file = state_dir / "wordpress-smoke-001.json"
    state_file.write_text(json.dumps(_state(state)))
    plan_path = tmp_path / "destroy.tfplan"
    plan_path.write_bytes(PLAN_BYTES)
    monkeypatch.setenv("BBR_STATE_DIR", str(state_dir))
    monkeypatch.setattr(cli, "_git_clean", lambda _root: True)
    monkeypatch.setattr(cli, "_git_head", lambda _root: HEAD)
    monkeypatch.setattr(cli, "_git_origin_main", lambda _root: HEAD)
    monkeypatch.setattr(
        cli, "_terraform_show_json", lambda _root, _path: plan_json or _plan()
    )
    monkeypatch.setattr(
        cli,
        "_run_subprocess",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args, returncode=0, stdout="", stderr=""
        ),
    )
    return state_file, plan_path


def test_destroy_plan_from_planned_records_binding(monkeypatch, tmp_path):
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    state_file = state_dir / "wordpress-smoke-001.json"
    state_file.write_text(json.dumps(_state()))
    plan_path = Path("/tmp/bbr-wordpress-smoke-001-destroy.tfplan")
    monkeypatch.setenv("BBR_STATE_DIR", str(state_dir))
    monkeypatch.setattr(cli, "_git_clean", lambda _root: True)
    monkeypatch.setattr(cli, "_git_head", lambda _root: HEAD)
    monkeypatch.setattr(cli, "_git_origin_main", lambda _root: HEAD)
    monkeypatch.setattr(cli, "_terraform_init", lambda *args: None)
    monkeypatch.setattr(
        cli,
        "load_manifest",
        lambda _pack: {
            "topology": {
                "nodes": [{
                    "driver_payload": {
                        "artifact_uri": "gs://bucket/artifact",
                        "artifact_sha256": "b" * 64,
                        "minisign_public_key": "key",
                        "supported_platform": "image",
                    },
                    "base_image": {"self_link": "image"},
                }]
            }
        },
    )
    monkeypatch.setattr(cli, "_plan_state_serial", lambda _path: 1)
    monkeypatch.setattr(cli, "_current_lab_state_serial", lambda: 2)
    monkeypatch.setattr(cli, "_terraform_show_json", lambda *_args: _plan())

    def run(command, **kwargs):
        if command[:2] == ["terraform", "plan"]:
            plan_path.write_bytes(PLAN_BYTES)
            return subprocess.CompletedProcess(command, 0, "", "")
        return subprocess.CompletedProcess(command, 0, "\n".join(EIGHT_ADDRESSES), "")

    monkeypatch.setattr(cli, "_run_subprocess", run)
    try:
        assert cli.cmd_destroy(_args(plan_path, finalize=False)) == 0
    finally:
        plan_path.unlink(missing_ok=True)
    result = json.loads(state_file.read_text())
    assert result["state"] == "DESTROY_PLANNED"
    assert result["destroy_plan_file"] == str(plan_path)
    assert result["destroy_plan_sha256"] == PLAN_SHA
    assert result["destroy_source_commit"] == HEAD
    assert result["destroy_delete_addresses"] == sorted(EIGHT_ADDRESSES)


def test_destroy_plan_from_healthy_records_stop_and_destroy_plan(
    monkeypatch, tmp_path
):
    state = _state("HEALTHY")
    result = cli._record_destroy_planned(state, by="system")

    assert result["state"] == "DESTROY_PLANNED"
    assert [entry["to"] for entry in result["transition_history"]][-2:] == [
        "STOPPED",
        "DESTROY_PLANNED",
    ]


def test_finalize_recovery_from_planned_records_full_history(monkeypatch, tmp_path):
    state_file, plan_path = _setup_finalize(monkeypatch, tmp_path)
    assert cli.cmd_destroy(_args(plan_path)) == 0
    result = json.loads(state_file.read_text())
    assert result["state"] == "DESTROYED"
    assert [entry["to"] for entry in result["transition_history"]][-2:] == [
        "DESTROY_PLANNED",
        "DESTROYED",
    ]
    assert result["destroy_plan_sha256"] == PLAN_SHA
    assert result["destroy_source_commit"] == HEAD
    assert result["destroy_delete_addresses"] == sorted(EIGHT_ADDRESSES)
    assert result["destroy_finalized_at"].endswith("Z")


@pytest.mark.parametrize(
    ("failure", "expected_rc"),
    [
        ("nonempty_state", 9),
        ("sha", 6),
        ("commit", 4),
        ("dirty", 2),
        ("create", 7),
        ("update", 7),
        ("outside", 8),
    ],
)
def test_finalize_gate_failures_leave_runtime_state_unchanged(
    monkeypatch, tmp_path, failure, expected_rc
):
    plan_json = _plan()
    if failure == "create":
        plan_json = _plan(actions=["create"])
    elif failure == "update":
        plan_json = _plan(actions=["update"])
    elif failure == "outside":
        plan_json = _plan(addresses=("google_compute_instance.phantom",))
    state_file, plan_path = _setup_finalize(
        monkeypatch, tmp_path, plan_json=plan_json
    )
    before = state_file.read_bytes()
    args = _args(plan_path)
    if failure == "nonempty_state":
        monkeypatch.setattr(
            cli,
            "_run_subprocess",
            lambda *args, **kwargs: subprocess.CompletedProcess(
                args=args, returncode=0, stdout=EIGHT_ADDRESSES[0] + "\n", stderr=""
            ),
        )
    elif failure == "sha":
        args.expected_sha256 = "0" * 64
    elif failure == "commit":
        args.expected_commit = "b" * 40
    elif failure == "dirty":
        monkeypatch.setattr(cli, "_git_clean", lambda _root: False)
    assert cli.cmd_destroy(args) == expected_rc
    assert state_file.read_bytes() == before


def test_finalize_destroyed_is_idempotent_without_write(monkeypatch, tmp_path):
    state_file, plan_path = _setup_finalize(monkeypatch, tmp_path, state="DESTROYED")
    data = json.loads(state_file.read_text())
    data.update({
        "destroy_plan_file": str(plan_path),
        "destroy_plan_sha256": PLAN_SHA,
        "destroy_source_commit": HEAD,
        "destroy_delete_addresses": sorted(EIGHT_ADDRESSES),
    })
    state_file.write_text(json.dumps(data))
    before = state_file.read_bytes()
    assert cli.cmd_destroy(_args(plan_path)) == 0
    assert state_file.read_bytes() == before


def test_allocator_ignores_finalized_lab(monkeypatch, tmp_path):
    (tmp_path / "wordpress-smoke-001.json").write_text(
        json.dumps(_state("DESTROYED"))
    )
    monkeypatch.setattr(allocator, "list_gcp_subnet_cidrs", lambda *_args: [])
    allocation = allocator.allocate_cidr(tmp_path, "project")
    assert allocation.active_lab_count == 0
    assert allocation.cidr == "10.200.1.0/24"
