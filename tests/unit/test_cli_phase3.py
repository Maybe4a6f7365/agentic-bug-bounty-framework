"""Unit tests for the Phase 3 CLI surface (hardened)."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PYTHONPATH = str(REPO / "platform/your-lab-name/src")


def _run(*args, env_extra=None, cwd=None):
    env = dict(os.environ)
    env["PYTHONPATH"] = PYTHONPATH
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-m", "bbr.cli", *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd or str(REPO),
    )


def test_validate_smoke_vm_pass():
    result = _run("validate", "platform/your-lab-name/packs/smoke-vm")
    assert result.returncode == 0, result.stdout + result.stderr


def test_validate_unknown_pack_rejected():
    result = _run("validate", "platform/your-lab-name/packs/does-not-exist")
    assert result.returncode != 0


def test_validate_bad_image_rejected(tmp_path):
    bad = tmp_path / "bad-pack"
    bad.mkdir()
    (bad / "manifest.json").write_text(json.dumps({
        "pack_id": "bad-pack",
        "version": "0.0.1",
        "topology": {"nodes": [{
            "node_id": "n1",
            "driver": "raw_vm",
            "machine_type": "e2-micro",
            "disk_type": "pd-standard",
            "disk_size_gb": 10,
            "base_image": {"family": "debian-12"}
        }]},
        "comparison_groups": [{"group_id": "g", "node_refs": ["n1"]}],
        "scenarios": [],
        "ttl": {"max_lifetime": "1h"},
        "cost_limits": {"per_lab_eur_estimate": 0.5, "per_cycle_eur_limit": 1.0},
        "teardown_requirements": []
    }))
    result = _run("validate", str(bad))
    assert result.returncode != 0


def test_list_reads_local_state(tmp_path):
    (tmp_path / "smoke-vm-001.json").write_text(json.dumps({
        "lab_id": "smoke-vm-001",
        "pack_id": "smoke-vm",
        "state": "READY",
    }))
    result = _run("list", env_extra={"BBR_STATE_DIR": str(tmp_path)})
    assert result.returncode == 0
    assert "smoke-vm-001" in result.stdout


def test_create_requires_all_flags():
    """Without ALL flags (--plan-file, --expected-sha256,
    --expected-commit), bbr create must abort."""
    result = _run("create", "smoke-vm-001")
    assert result.returncode != 0
    out = (result.stdout + result.stderr).lower()
    assert "plan-file" in out
    assert "expected-sha256" in out
    assert "expected-commit" in out


def test_create_rejects_mismatched_sha(tmp_path):
    plan = tmp_path / "x.tfplan"
    plan.write_bytes(b"not a real plan")
    result = _run(
        "create", "smoke-vm-001",
        "--plan-file", str(plan),
        "--expected-sha256", "0" * 64,
        "--expected-commit", "deadbeef" * 5,
    )
    assert result.returncode != 0


def test_destroy_not_executed_in_plan_step():
    """bbr destroy must never actually destroy. Either:
      - it aborts with a gate failure (e.g. no local state), or
      - it produces a stored destroy plan AND prints the human
        gate 'APPROVE PHASE 3 DESTROY EXECUTE' language.
    Either way the destructive action is gated."""
    result = _run("destroy", "smoke-vm-001")
    if result.returncode == 0:
        out = (result.stdout + result.stderr).lower()
        assert "approv" in out
        assert "destroy execute" in out
    else:
        # The destroy was aborted by a gate. The error must be a
        # gate-related message, NOT a destructive command.
        assert result.returncode != 0
        out = (result.stdout + result.stderr).lower()
        assert "fail" in out or "no local state" in out or "working tree" in out


def test_cost_limit_is_one_euro():
    """The PHASE3_SMOKE_CYCLE_LIMIT_EUR constant must be 1.0, not 2.0."""
    from bbr.cli import PHASE3_SMOKE_CYCLE_LIMIT_EUR
    assert PHASE3_SMOKE_CYCLE_LIMIT_EUR == 1.00


def test_cost_limit_default_in_pack_validation():
    """pack_validation default guard must be 1.0 EUR, not 2.0."""
    from bbr.pack_validation import validate_cost_limits
    # limit = 1.5 should be REJECTED under default 1.0
    with pytest.raises(Exception):
        validate_cost_limits({"cost_limits": {"per_cycle_eur_limit": 1.5}})


def test_locking_module_is_tracked():
    """src/bbr/state/locking.py must be tracked in git (not ignored)."""
    r = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "--error-unmatch",
         "platform/your-lab-name/src/bbr/state/locking.py"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, (
        f"locking.py must be tracked; got: {r.stderr}\n"
        f"check-ignore: "
        + subprocess.run(
            ["git", "-C", str(REPO), "check-ignore", "-v",
             "platform/your-lab-name/src/bbr/state/locking.py"],
            capture_output=True, text=True,
        ).stdout
    )


def test_repo_root_state_is_ignored():
    """A repository-root level state/ directory must be ignored."""
    r = subprocess.run(
        ["git", "-C", str(REPO), "check-ignore", "-v", "state/probe.json"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, "state/ at repo root must be ignored"
    assert "state/" in r.stdout


def test_src_bbr_state_is_not_ignored():
    r = subprocess.run(
        ["git", "-C", str(REPO), "check-ignore", "-v",
         "platform/your-lab-name/src/bbr/state/locking.py"],
        capture_output=True, text=True,
    )
    assert r.returncode != 0, (
        f"src/bbr/state/ must not be ignored: {r.stdout}"
    )


@pytest.mark.parametrize("cmd", ["bootstrap", "isolate", "start", "stop",
                                  "snapshot", "restore", "run", "diff"])
def test_not_implemented_commands(cmd):
    result = _run(cmd, "smoke-vm-001")
    assert result.returncode != 0
    out = (result.stdout + result.stderr).lower()
    assert "not implemented" in out

def test_transition_history_contains_defined_validated_planned():
    """The runtime state must record the full plan path."""
    from bbr.lifecycle.state_machine import make_state, record_transition
    s = make_state(
        lab_id="lab-1",
        pack_id="smoke-vm",
        state="DEFINED",
        operator_principal="user:test",
        ttl_deadline="2026-07-27T00:00:00Z",
    )
    s = record_transition(s, "VALIDATED")
    s = record_transition(s, "PLANNED")
    history = s["transition_history"]
    assert len(history) == 3
    assert history[0]["to"] == "DEFINED"
    assert history[1]["to"] == "VALIDATED"
    assert history[2]["to"] == "PLANNED"


# ------------------------------------------------------------------
# Credential preflight
# ------------------------------------------------------------------

def test_credential_preflight_aborts_create_without_token(tmp_path, monkeypatch):
    """bbr create must refuse to invoke terraform apply when
    GOOGLE_OAUTH_ACCESS_TOKEN is not set.

    The test simulates the scenario by unsetting the variable
    and providing a valid plan-file and state-file. The CLI
    must abort with exit code 18 and a clear credential-preflight
    error message BEFORE terraform apply runs (so the State
    stays unmutated).
    """
    import argparse
    import json
    from bbr import cli

    # Ensure no token is set
    monkeypatch.delenv("GOOGLE_OAUTH_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("BBR_PHASE3_EXECUTE_CONFIRM", "yes")
    # A dummy plan-file (real SHA computed for the state)
    plan = tmp_path / "p.tfplan"
    plan.write_bytes(b"x")
    import hashlib
    plan_sha = hashlib.sha256(plan.read_bytes()).hexdigest()
    head = cli._git_head(cli.REPO_ROOT)
    monkeypatch.setenv("BBR_STATE_DIR", str(tmp_path))
    (tmp_path / "smoke-vm-001.json").write_text(json.dumps({
        "lab_id": "smoke-vm-001",
        "pack_id": "smoke-vm",
        "state": "PLANNED",
        "source_commit": head,
        "plan_file": str(plan),
        "plan_sha256": plan_sha,
        "backend_prefix": "labs/smoke-vm-001",
        "transition_history": [],
    }))
    args = argparse.Namespace(
        lab_id="smoke-vm-001",
        plan_file=str(plan),
        expected_sha256=plan_sha,
        expected_commit=head,
    )
    rc = cli.cmd_create(args)
    # The dedicated exit code for credential preflight is 18.
    assert rc == 18, (
        f"expected exit 18 (credential preflight), got {rc}; "
        f"missing GOOGLE_OAUTH_ACCESS_TOKEN must abort before "
        f"any subprocess or state mutation"
    )
    # State must NOT have been advanced
    state = json.loads((tmp_path / "smoke-vm-001.json").read_text())
    assert state["state"] == "PLANNED"


# ------------------------------------------------------------------
# Stale-plan detection
# ------------------------------------------------------------------

def test_stale_plan_detected_before_apply(tmp_path, monkeypatch):
    """If the plan serial does not match the current lab state
    serial, bbr create must abort before invoking terraform
    apply. The test simulates this by patching
    _plan_state_serial and _current_lab_state_serial to
    return differing values.

    The CLI must exit with code 19 (the dedicated stale-plan
    exit code) before any subprocess is spawned for the
    actual apply. The credential preflight must run BEFORE
    the serial check so that a missing token still produces
    the credential error (a missing token is the more
    important user-facing problem).
    """
    import argparse
    import json
    from bbr import cli

    # Patch the serial helpers to differ — the apply MUST
    # be rejected because the plan serial (1) does not match
    # the current state serial (99).
    monkeypatch.setattr(cli, "_plan_state_serial", lambda p: 1)
    monkeypatch.setattr(cli, "_current_lab_state_serial", lambda: 99)
    # A valid token so we get past the credential preflight.
    monkeypatch.setenv("GOOGLE_OAUTH_ACCESS_TOKEN", "dummy-token")
    monkeypatch.setenv("BBR_PHASE3_EXECUTE_CONFIRM", "yes")

    # Use the REAL Phase 3 create plan so terraform show -json
    # succeeds. The stale-detection is triggered by the patched
    # serial helpers, not by an invalid plan file.
    real_plan = Path("/tmp/bbr-phase3-smoke-create-v3.tfplan")
    if not real_plan.is_file():
        pytest.skip("real Phase 3 plan not available at /tmp/bbr-phase3-smoke-create-v3.tfplan")
    plan = tmp_path / "p.tfplan"
    plan.write_bytes(real_plan.read_bytes())
    import hashlib
    plan_sha = hashlib.sha256(plan.read_bytes()).hexdigest()
    head = cli._git_head(cli.REPO_ROOT)
    monkeypatch.setenv("BBR_STATE_DIR", str(tmp_path))
    (tmp_path / "smoke-vm-001.json").write_text(json.dumps({
        "lab_id": "smoke-vm-001",
        "pack_id": "smoke-vm",
        "state": "PLANNED",
        "source_commit": head,
        "plan_file": str(plan),
        "plan_sha256": plan_sha,
        "backend_prefix": "labs/smoke-vm-001",
        "transition_history": [],
    }))

    # Build a minimal args namespace matching cmd_create's contract.
    args = argparse.Namespace(
        lab_id="smoke-vm-001",
        plan_file=str(plan),
        expected_sha256=plan_sha,
        expected_commit=head,
    )

    # We expect exit 19 (stale-plan exit code) — not via SystemExit
    # but via return value, because cmd_create returns ints on
    # failure.
    rc = cli.cmd_create(args)
    assert rc == 19, (
        f"expected exit 19 for stale plan, got {rc}; "
        f"the apply must be rejected before any subprocess runs"
    )


# ------------------------------------------------------------------
# Destroy-plan-freshness
# ------------------------------------------------------------------

def test_destroy_refuses_to_overwrite_fresh_existing_plan(tmp_path, monkeypatch):
    """If a destroy plan file already exists whose State serial
    matches the current State, bbr destroy must refuse to
    silently overwrite it. The operator must rename it to
    .OBSOLETE first or advance the State.
    """
    import argparse
    import json
    from bbr import cli

    monkeypatch.delenv("GOOGLE_OAUTH_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("GOOGLE_OAUTH_ACCESS_TOKEN", "dummy-token")
    # Pre-existing plan file at the canonical path
    existing = tmp_path / "bbr-smoke-vm-001-destroy.tfplan"
    existing.write_bytes(b"existing-plan-bytes")
    # State file
    monkeypatch.setenv("BBR_STATE_DIR", str(tmp_path))
    (tmp_path / "smoke-vm-001.json").write_text(json.dumps({
        "lab_id": "smoke-vm-001",
        "pack_id": "smoke-vm",
        "state": "READY",
        "backend_prefix": "labs/smoke-vm-001",
        "transition_history": [],
    }))
    # Patch the serial helpers to return the SAME value —
    # the plan is fresh against the current State, so the
    # destroy command must refuse to overwrite it.
    monkeypatch.setattr(cli, "_plan_state_serial", lambda p: 7)
    monkeypatch.setattr(cli, "_current_lab_state_serial", lambda: 7)
    # Bypass the early gate checks (working tree / commit /
    # terraform init) so the overwrite-protection activates.
    monkeypatch.setattr(cli, "_git_clean", lambda *a, **k: True)
    monkeypatch.setattr(cli, "_git_head", lambda *a, **k: "x" * 40)
    monkeypatch.setattr(cli, "_git_origin_main", lambda *a, **k: "x" * 40)
    monkeypatch.setattr(cli, "_terraform_init", lambda *a, **k: None)

    args = argparse.Namespace(lab_id="smoke-vm-001")
    rc = cli.cmd_destroy(args)
    assert rc == 10, (
        f"expected exit 10 (destroy plan already exists), got {rc}; "
        f"the plan file must NOT be silently overwritten"
    )
    # Plan file content unchanged — no new plan written.
    assert existing.read_bytes() == b"existing-plan-bytes"


# ------------------------------------------------------------------
# verify firewall filter fix
# ------------------------------------------------------------------

def test_verify_uses_firewall_rules_not_firewalls(monkeypatch):
    """The CLI must call `gcloud compute firewall-rules list`
    (not `gcloud compute firewalls list`) and parse JSON in
    Python instead of using a targetTags filter.

    We verify this by source-code inspection of cli.py. The
    obsolete alias 'firewalls' (singular, as a subcommand
    token) used to appear in the list call:
        ["gcloud", "compute", "firewalls", "list", ...]
    and the filter expression 'targetTags:X' used to appear
    in that same call. Both must be absent from any
    executable line in cmd_verify.
    """
    import re
    from bbr import cli
    src = Path(cli.__file__).read_text()
    verify_start = src.find("def cmd_verify")
    assert verify_start > 0
    verify_end = src.find("\n\n\ndef ", verify_start + 1)
    verify_body = src[verify_start:verify_end]
    # Strip the docstring (between triple quotes at function start)
    docstring_end = verify_body.find('"""', 3)
    if docstring_end > 0:
        verify_body = verify_body[docstring_end + 3:]
    # Strip Python line-comments — they may legitimately
    # mention the obsolete tokens in prose without making
    # the code wrong.
    no_comments = "\n".join(
        re.sub(r"\s*#.*$", "", line) for line in verify_body.splitlines()
    )
    # The obsolete list alias 'firewalls' (without '-rules')
    # must NOT appear anywhere in executable verify code.
    assert '"firewalls", "list"' not in no_comments, (
        "verify still uses obsolete 'firewalls list' alias"
    )
    # The invalid gcloud filter expression must not be present.
    assert "targetTags:" not in no_comments, (
        "verify still uses invalid 'targetTags:' gcloud filter"
    )
    # Positive assertions: the canonical subcommand and JSON
    # output path must be present.
    assert "firewall-rules" in no_comments
    assert '"--format=json"' in no_comments
    # The Python-side filter must inspect targetTags:
    assert "targetTags" in no_comments
