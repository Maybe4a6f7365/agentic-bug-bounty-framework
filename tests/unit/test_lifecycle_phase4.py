import argparse
import json

from bbr import cli
from bbr.lifecycle.state_machine import make_state, record_transition


def _planned(path):
    state = make_state("wordpress-smoke-001", "wordpress-smoke", "DEFINED")
    state = record_transition(state, "VALIDATED")
    state = record_transition(state, "PLANNED")
    path.write_text(json.dumps(state))


def test_full_lifecycle_create_to_verified(tmp_path, monkeypatch):
    path = tmp_path / "wordpress-smoke-001.json"; _planned(path)
    monkeypatch.setenv("BBR_HEALTH_CONSECUTIVE_PASSES", "3")
    assert cli._verify_wordpress_phase4(path, json.loads(path.read_text()), True) == 0
    assert json.loads(path.read_text())["state"] == "VERIFIED"


def test_failure_path_triggers_rollback(tmp_path, monkeypatch):
    path = tmp_path / "wordpress-smoke-001.json"; _planned(path)
    monkeypatch.setenv("BBR_BOOTSTRAP_FAIL_CODE", "36")
    assert cli._verify_wordpress_phase4(path, json.loads(path.read_text())) == 36
    monkeypatch.setattr(cli, "_state_dir", lambda: tmp_path)
    cli.cmd_destroy(argparse.Namespace(
        lab_id="wordpress-smoke-001", from_failure=True))
    assert json.loads(path.read_text())["state"] != "DESTROYED"


def test_health_3_consecutive_passes_to_healthy(tmp_path, monkeypatch):
    path = tmp_path / "wordpress-smoke-001.json"; _planned(path)
    monkeypatch.setenv("BBR_HEALTH_CONSECUTIVE_PASSES", "3")
    cli._verify_wordpress_phase4(path, json.loads(path.read_text()))
    assert json.loads(path.read_text())["state"] == "HEALTHY"


def test_health_unhealthy_does_not_advance_to_healthy(tmp_path, monkeypatch):
    path = tmp_path / "wordpress-smoke-001.json"; _planned(path)
    monkeypatch.setenv("BBR_HEALTH_CONSECUTIVE_PASSES", "2")
    assert cli._verify_wordpress_phase4(path, json.loads(path.read_text())) == 39
    assert json.loads(path.read_text())["state"] == "READY"


def test_state_machine_idempotent(tmp_path, monkeypatch):
    path = tmp_path / "wordpress-smoke-001.json"; _planned(path)
    monkeypatch.setenv("BBR_HEALTH_CONSECUTIVE_PASSES", "3")
    cli._verify_wordpress_phase4(path, json.loads(path.read_text()))
    assert cli._verify_wordpress_phase4(path, json.loads(path.read_text())) == 0
