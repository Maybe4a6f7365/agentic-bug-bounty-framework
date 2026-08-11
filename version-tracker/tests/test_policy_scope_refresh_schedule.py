import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).parents[1]
DAILY = ROOT / "cron/version-tracker-daily.sh"


def _run_daily(tmp_path, **overrides):
    env = os.environ.copy()
    for variable in (
        "VERSION_TRACKER_POLICY_REPO_ROOT",
        "VERSION_TRACKER_DB",
        "VERSION_TRACKER_DERIVED_ARTIFACT_ADAPTER",
        "VERSION_TRACKER_TARGET_ASSET_OUTPUT",
        "VERSION_TRACKER_INVENTORY_JSON",
        "VERSION_TRACKER_INVENTORY_MARKDOWN",
    ):
        env.pop(variable, None)
    env.update({
        "VERSION_TRACKER_LOCK_FILE": str(tmp_path / "daily.lock"),
        "VERSION_TRACKER_SECRETS_FILE": str(tmp_path / "missing-secrets"),
        **overrides,
    })
    return subprocess.run(
        ["bash", str(DAILY)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _linked_review_worktree(tmp_path):
    primary = tmp_path / "primary"
    review = tmp_path / "review"
    subprocess.run(["git", "init", str(primary)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(primary), "config", "user.name", "Test"], check=True
    )
    subprocess.run(
        ["git", "-C", str(primary), "config", "user.email", "test@example.invalid"],
        check=True,
    )
    (primary / "targets").mkdir()
    (primary / "targets" / ".gitkeep").write_text("")
    subprocess.run(["git", "-C", str(primary), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(primary), "commit", "-m", "fixture"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(primary), "worktree", "add", str(review), "-b", "review"],
        check=True,
        capture_output=True,
    )
    return review


def _stubbed_daily_environment(tmp_path):
    review = _linked_review_worktree(tmp_path)
    fake_repo = tmp_path / "version-tracker"
    fake_bin = tmp_path / "bin"
    fake_repo.mkdir()
    fake_bin.mkdir()
    trace = tmp_path / "trace"
    python = fake_bin / "python3"
    python.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$*\" >> \"$TRACE_FILE\"\n"
        "case \"$*\" in\n"
        "  *'checkers/runner.py --dry-run'*) printf '%s\\n' 'No sources due for check.' ;;\n"
        "  *'SELECT COUNT(*)'*) printf '%s\\n' '1' ;;\n"
        "esac\n"
    )
    python.chmod(0o755)
    adapter = tmp_path / "derived-adapter"
    adapter.write_text(
        "#!/usr/bin/env bash\n"
        "{ printf 'adapter'; printf ' <%s>' \"$@\"; printf '\\n'; } >> \"$TRACE_FILE\"\n"
        "exit \"${ADAPTER_EXIT:-0}\"\n"
    )
    adapter.chmod(0o755)
    outputs = {
        "VERSION_TRACKER_TARGET_ASSET_OUTPUT": str(tmp_path / "target assets.md"),
        "VERSION_TRACKER_INVENTORY_JSON": str(tmp_path / "inventory view.json"),
        "VERSION_TRACKER_INVENTORY_MARKDOWN": str(tmp_path / "inventory view.md"),
    }
    env = {
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "TRACE_FILE": str(trace),
        "VERSION_TRACKER_POLICY_REPO_ROOT": str(review),
        "VERSION_TRACKER_REPO_DIR": str(fake_repo),
        "VERSION_TRACKER_VENV_PYTHON": str(python),
        "VERSION_TRACKER_DB": str(tmp_path / "version-tracker.db"),
        "VERSION_TRACKER_DERIVED_ARTIFACT_ADAPTER": str(adapter),
        **outputs,
    }
    return trace, adapter, outputs, env


def test_daily_maintenance_requires_explicit_policy_review_worktree_before_writes(tmp_path):
    result = _run_daily(tmp_path)

    assert result.returncode != 0
    assert "VERSION_TRACKER_POLICY_REPO_ROOT is required" in result.stderr
    assert not (tmp_path / "daily.lock").exists()


def test_daily_maintenance_rejects_primary_checkout_before_writes(tmp_path):
    primary = tmp_path / "primary"
    subprocess.run(["git", "init", str(primary)], check=True, capture_output=True)
    (primary / "targets").mkdir()

    result = _run_daily(
        tmp_path,
        VERSION_TRACKER_POLICY_REPO_ROOT=str(primary),
    )

    assert result.returncode != 0
    assert "isolated linked Git worktree" in result.stderr
    assert not (tmp_path / "daily.lock").exists()


def test_git_environment_cannot_spoof_isolated_worktree_validation(tmp_path):
    primary = tmp_path / "primary"
    subprocess.run(["git", "init", str(primary)], check=True, capture_output=True)
    (primary / "targets").mkdir()
    linked_git_dir = subprocess.run(
        ["git", "rev-parse", "--absolute-git-dir"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    result = _run_daily(
        tmp_path,
        VERSION_TRACKER_POLICY_REPO_ROOT=str(primary),
        GIT_DIR=linked_git_dir,
        GIT_WORK_TREE=str(primary),
    )

    assert result.returncode != 0
    assert "isolated linked Git worktree" in result.stderr
    assert not (tmp_path / "daily.lock").exists()


def test_daily_maintenance_accepts_explicit_linked_review_worktree(tmp_path):
    primary = tmp_path / "primary"
    review = tmp_path / "review"
    subprocess.run(["git", "init", str(primary)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(primary), "config", "user.name", "Test"], check=True
    )
    subprocess.run(
        ["git", "-C", str(primary), "config", "user.email", "test@example.invalid"],
        check=True,
    )
    (primary / "targets").mkdir()
    (primary / "targets" / ".gitkeep").write_text("")
    subprocess.run(["git", "-C", str(primary), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(primary), "commit", "-m", "fixture"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(primary), "worktree", "add", str(review), "-b", "review"],
        check=True,
        capture_output=True,
    )

    adapter = tmp_path / "adapter"
    adapter.write_text("#!/bin/sh\nexit 0\n")
    adapter.chmod(0o755)
    result = _run_daily(
        tmp_path,
        VERSION_TRACKER_POLICY_REPO_ROOT=str(review),
        VERSION_TRACKER_REPO_DIR=str(tmp_path / "missing-version-tracker"),
        VERSION_TRACKER_DB=str(tmp_path / "version-tracker.db"),
        VERSION_TRACKER_DERIVED_ARTIFACT_ADAPTER=str(adapter),
        VERSION_TRACKER_TARGET_ASSET_OUTPUT=str(tmp_path / "target-assets.md"),
        VERSION_TRACKER_INVENTORY_JSON=str(tmp_path / "inventory.json"),
        VERSION_TRACKER_INVENTORY_MARKDOWN=str(tmp_path / "inventory.md"),
    )

    assert result.returncode != 0
    assert "venv interpreter missing" in result.stderr
    assert (tmp_path / "daily.lock").exists()


def test_secrets_cannot_replace_validated_policy_worktree(tmp_path):
    primary = tmp_path / "primary"
    review = tmp_path / "review"
    subprocess.run(["git", "init", str(primary)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(primary), "config", "user.name", "Test"], check=True
    )
    subprocess.run(
        ["git", "-C", str(primary), "config", "user.email", "test@example.invalid"],
        check=True,
    )
    (primary / "targets").mkdir()
    (primary / "targets" / ".gitkeep").write_text("")
    subprocess.run(["git", "-C", str(primary), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(primary), "commit", "-m", "fixture"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(primary), "worktree", "add", str(review), "-b", "review"],
        check=True,
        capture_output=True,
    )
    secrets = tmp_path / "secrets"
    secrets.write_text(f"POLICY_REPO_ROOT={tmp_path / 'unvalidated'}\n")
    adapter = tmp_path / "adapter"
    adapter.write_text("#!/bin/sh\nexit 0\n")
    adapter.chmod(0o755)

    result = _run_daily(
        tmp_path,
        VERSION_TRACKER_POLICY_REPO_ROOT=str(review),
        VERSION_TRACKER_SECRETS_FILE=str(secrets),
        VERSION_TRACKER_DB=str(tmp_path / "version-tracker.db"),
        VERSION_TRACKER_DERIVED_ARTIFACT_ADAPTER=str(adapter),
        VERSION_TRACKER_TARGET_ASSET_OUTPUT=str(tmp_path / "target-assets.md"),
        VERSION_TRACKER_INVENTORY_JSON=str(tmp_path / "inventory.json"),
        VERSION_TRACKER_INVENTORY_MARKDOWN=str(tmp_path / "inventory.md"),
    )

    assert result.returncode != 0
    assert "POLICY_REPO_ROOT: readonly variable" in result.stderr


def test_daily_maintenance_refreshes_repo_after_policy_enrichment():
    text = (ROOT / "cron/version-tracker-daily.sh").read_text()

    policy = text.index("scripts/enrich_policy.py --all")
    refresh = text.index("scripts/refresh_policy_scope.py")
    retention = text.index("retention (prune old data")

    assert policy < refresh < retention
    assert '--repo-root "$POLICY_REPO_ROOT"' in text
    assert text.rindex("validate_policy_worktree") < refresh
    assert "git commit" not in text
    assert "git push" not in text


def test_30_minute_poller_does_not_refresh_policy_scope():
    text = (ROOT / "cron/version-tracker-30m.sh").read_text()

    assert "refresh_policy_scope.py" not in text


def test_daily_maintenance_runs_mandatory_derived_refresh_in_exact_order(tmp_path):
    trace, _, outputs, env = _stubbed_daily_environment(tmp_path)

    result = _run_daily(tmp_path, **env)

    assert result.returncode == 0, result.stderr
    calls = trace.read_text().splitlines()
    import_index = next(i for i, call in enumerate(calls) if "import_h1.py --enrich" in call)
    enrich_index = next(i for i, call in enumerate(calls) if "scripts/enrich_policy.py --all" in call)
    refresh_index = next(i for i, call in enumerate(calls) if "scripts/refresh_policy_scope.py" in call)
    adapter_index = next(i for i, call in enumerate(calls) if call.startswith("adapter "))
    retention_index = next(i for i, call in enumerate(calls) if "DELETE FROM version_observation" in call)
    assert import_index < enrich_index < refresh_index < adapter_index < retention_index
    assert calls[adapter_index] == (
        f"adapter <--db> <{env['VERSION_TRACKER_DB']}> "
        f"<--target-asset-output> <{outputs['VERSION_TRACKER_TARGET_ASSET_OUTPUT']}> "
        f"<--inventory-json> <{outputs['VERSION_TRACKER_INVENTORY_JSON']}> "
        f"<--inventory-markdown> <{outputs['VERSION_TRACKER_INVENTORY_MARKDOWN']}>"
    )


def test_daily_maintenance_fails_closed_when_derived_adapter_is_missing(tmp_path):
    trace, adapter, _, env = _stubbed_daily_environment(tmp_path)
    adapter.unlink()

    result = _run_daily(tmp_path, **env)

    assert result.returncode != 0
    assert "VERSION_TRACKER_DERIVED_ARTIFACT_ADAPTER" in result.stderr
    assert not trace.exists()


def test_secrets_cannot_redirect_bound_derived_artifact_paths(tmp_path):
    trace, adapter, outputs, env = _stubbed_daily_environment(tmp_path)
    malicious = tmp_path / "malicious-adapter"
    malicious.write_text(
        "#!/bin/sh\nprintf '%s\\n' malicious-adapter >> \"$TRACE_FILE\"\n"
    )
    malicious.chmod(0o755)
    secrets = tmp_path / "secrets"
    secrets.write_text(
        f"VERSION_TRACKER_DERIVED_ARTIFACT_ADAPTER='{malicious}'\n"
        f"VERSION_TRACKER_TARGET_ASSET_OUTPUT='{tmp_path / 'redirected target.md'}'\n"
        f"VERSION_TRACKER_INVENTORY_JSON='{tmp_path / 'redirected.json'}'\n"
        f"VERSION_TRACKER_INVENTORY_MARKDOWN='{tmp_path / 'redirected.md'}'\n"
    )
    env["VERSION_TRACKER_SECRETS_FILE"] = str(secrets)

    result = _run_daily(tmp_path, **env)

    assert result.returncode == 0, result.stderr
    calls = trace.read_text().splitlines()
    assert not any(call == "malicious-adapter" for call in calls)
    adapter_call = next(call for call in calls if call.startswith("adapter "))
    assert str(adapter) not in adapter_call  # executable is argv[0], never user data
    assert f"<{outputs['VERSION_TRACKER_TARGET_ASSET_OUTPUT']}>" in adapter_call
    assert f"<{outputs['VERSION_TRACKER_INVENTORY_JSON']}>" in adapter_call
    assert f"<{outputs['VERSION_TRACKER_INVENTORY_MARKDOWN']}>" in adapter_call


def test_secrets_cannot_redirect_bound_database_path(tmp_path):
    trace, _, _, env = _stubbed_daily_environment(tmp_path)
    secrets = tmp_path / "secrets"
    secrets.write_text(f"VERSION_TRACKER_DB='{tmp_path / 'redirected.db'}'\n")
    env["VERSION_TRACKER_SECRETS_FILE"] = str(secrets)

    result = _run_daily(tmp_path, **env)

    assert result.returncode != 0
    assert "VERSION_TRACKER_DB: readonly variable" in result.stderr
    assert not trace.exists()


def test_daily_maintenance_requires_explicit_absolute_database_path(tmp_path):
    for invalid in (None, "relative.db"):
        case = tmp_path / ("missing" if invalid is None else "relative")
        case.mkdir()
        trace, _, _, env = _stubbed_daily_environment(case)
        if invalid is None:
            del env["VERSION_TRACKER_DB"]
        else:
            env["VERSION_TRACKER_DB"] = invalid

        result = _run_daily(case, **env)

        assert result.returncode != 0
        assert "VERSION_TRACKER_DB must be an explicit absolute path" in result.stderr
        assert not trace.exists()


def test_daily_maintenance_requires_every_derived_output_path(tmp_path):
    for missing in (
        "VERSION_TRACKER_TARGET_ASSET_OUTPUT",
        "VERSION_TRACKER_INVENTORY_JSON",
        "VERSION_TRACKER_INVENTORY_MARKDOWN",
    ):
        case = tmp_path / missing.lower()
        case.mkdir()
        trace, _, _, env = _stubbed_daily_environment(case)
        del env[missing]

        result = _run_daily(case, **env)

        assert result.returncode != 0
        assert missing in result.stderr
        assert not trace.exists()


def test_daily_maintenance_fails_when_mandatory_derived_refresh_fails(tmp_path):
    trace, _, _, env = _stubbed_daily_environment(tmp_path)
    env["ADAPTER_EXIT"] = "23"

    result = _run_daily(tmp_path, **env)

    assert result.returncode == 23
    calls = trace.read_text().splitlines()
    assert any(call.startswith("adapter ") for call in calls)
    assert not any("DELETE FROM version_observation" in call for call in calls)


def test_30_minute_poller_does_not_publish_derived_artifacts():
    text = (ROOT / "cron/version-tracker-30m.sh").read_text()

    assert "DERIVED_ARTIFACT" not in text
    assert "target-asset-output" not in text
    assert "inventory-json" not in text
