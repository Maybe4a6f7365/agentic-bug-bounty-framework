import argparse
import hashlib
import json

from bbr import cli
from bbr.plan_contract import plan_contract


def _state(tmp_path, plan):
    manifest = json.loads(
        (cli.DEFAULT_PACKS_DIR / "wordpress-smoke/manifest.json").read_text()
    )
    payload = manifest["topology"]["nodes"][0]["driver_payload"]
    sha = hashlib.sha256(plan.read_bytes()).hexdigest()
    state = {
        "state": "PLANNED",
        "lab_id": "wordpress-smoke-001",
        "pack_id": "wordpress-smoke",
        "pack_version": manifest["version"],
        "backend_prefix": "labs/wordpress-smoke-001",
        "plan_file": str(plan),
        "plan_sha256": sha,
        "driver_payload": payload,
        "transition_history": [],
    }
    (tmp_path / "wordpress-smoke-001.json").write_text(json.dumps(state))
    return sha


def _args(plan, sha):
    return argparse.Namespace(
        lab_id="wordpress-smoke-001", plan_file=str(plan),
        expected_sha256=sha, expected_commit="a" * 40,
    )


def _prepare(monkeypatch, tmp_path, resource_type="google_compute_firewall"):
    plan = tmp_path / "create.tfplan"
    plan.write_bytes(b"reviewed plan")
    sha = _state(tmp_path, plan)
    contract = plan_contract("wordpress-smoke")
    changes = [
        {
            "address": address,
            "type": (
                "google_storage_bucket_iam_member"
                if "bucket_binding" in address else resource_type
            ),
            "change": {"actions": ["create"]},
        }
        for address in contract.expected_create_addresses
    ]
    monkeypatch.setattr(cli, "_state_dir", lambda: tmp_path)
    monkeypatch.setattr(cli, "_git_head", lambda _: "a" * 40)
    monkeypatch.setattr(cli, "_git_origin_main", lambda _: "a" * 40)
    monkeypatch.setattr(cli, "_git_clean", lambda _: True)
    monkeypatch.setattr(cli, "_plan_state_serial", lambda _: None)
    monkeypatch.setattr(cli, "_current_lab_state_serial", lambda: None)
    monkeypatch.setattr(cli, "_terraform_show_json", lambda *_: {"resource_changes": changes})
    monkeypatch.setenv("GOOGLE_OAUTH_ACCESS_TOKEN", "redacted-test-token")
    monkeypatch.delenv("BBR_PHASE4_EXECUTE_CONFIRM", raising=False)
    return plan, sha


def test_wordpress_create_gate_passes_without_apply(monkeypatch, tmp_path, capsys):
    plan, sha = _prepare(monkeypatch, tmp_path)
    calls = []
    monkeypatch.setattr(cli, "_run_subprocess", lambda *args, **kwargs: calls.append(args))
    assert cli.cmd_create(_args(plan, sha)) == 0
    output = capsys.readouterr().out
    assert "BBR_PHASE4_EXECUTE_CONFIRM=yes" in output
    assert "APPROVE PHASE 4 EXECUTE" in output
    assert calls == []


def test_wordpress_create_rejects_unexpected_type(monkeypatch, tmp_path):
    plan, sha = _prepare(monkeypatch, tmp_path, "google_compute_router")
    assert cli.cmd_create(_args(plan, sha)) == 16


def test_missing_plan_serial_is_not_replaced_by_resource_count(monkeypatch, tmp_path):
    plan = tmp_path / "create.tfplan"
    plan.write_bytes(b"plan")
    monkeypatch.setattr(
        cli, "_terraform_show_json",
        lambda *_: {"resource_changes": [{"change": {"actions": ["create"]}}]},
    )
    assert cli._plan_state_serial(plan) is None
