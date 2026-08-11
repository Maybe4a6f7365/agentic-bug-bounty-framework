import logging
import os
import stat
import subprocess
import pytest

from bbr.bootstrap.secrets import (
    generate_db_password, secret_safe_context, write_secret_file,
)


def test_generate_db_password_length_and_uniqueness():
    first, second = generate_db_password(), generate_db_password()
    assert len(first) >= 40 and first != second


def test_generate_db_password_uses_openssl(monkeypatch):
    seen = {}
    def run(cmd, **kwargs):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, "secret\n", "")
    monkeypatch.setattr(subprocess, "run", run)
    assert generate_db_password() == "secret"
    assert seen["cmd"] == ["openssl", "rand", "-base64", "32"]


def test_secret_file_mode_0600(tmp_path):
    if os.geteuid() != 0:
        pytest.skip("root ownership requires a privileged test runner")
    path = tmp_path / "secret"
    write_secret_file(path, "private")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_secret_file_owner_root(tmp_path):
    if os.geteuid() != 0:
        pytest.skip("root ownership requires a privileged test runner")
    path = tmp_path / "secret"
    write_secret_file(path, "private")
    assert path.stat().st_uid == 0 and path.stat().st_gid == 0


def test_secret_safe_context_unsets_ps4(monkeypatch):
    monkeypatch.setenv("PS4", "trace")
    with secret_safe_context():
        assert "PS4" not in os.environ


def test_secret_safe_context_restores_ps4(monkeypatch):
    monkeypatch.setenv("PS4", "trace")
    with secret_safe_context():
        pass
    assert os.environ["PS4"] == "trace"


def test_secrets_not_in_logs(caplog):
    with caplog.at_level(logging.DEBUG):
        secret = generate_db_password()
    assert secret not in caplog.text
