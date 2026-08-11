import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "packs/wordpress-smoke/provisioning/install-wordpress.sh"
BOOTSTRAP = ROOT / "packs/wordpress-smoke/provisioning/bootstrap.sh"


def _script() -> str:
    return INSTALLER.read_text()


def _write_executable(path: Path, body: str) -> None:
    path.write_text("#!/usr/bin/env bash\nset -euo pipefail\n" + body)
    path.chmod(0o755)


def _run_install_phase(tmp_path: Path, apt_install_exit: int = 0):
    package_dir = tmp_path / "packages"
    package_dir.mkdir()
    for number in range(160):
        (package_dir / f"package-{number:03}.deb").touch()

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    calls = tmp_path / "calls"
    log = tmp_path / "install.log"
    nginx_sites = tmp_path / "etc/nginx/sites-available"
    nginx_snippets = tmp_path / "etc/nginx/snippets"
    nginx_sites.mkdir(parents=True)
    nginx_snippets.mkdir(parents=True)
    (nginx_snippets / "fastcgi-php.conf").touch()

    _write_executable(
        fake_bin / "apt-get",
        """
printf 'apt-get' >> "$CALLS"
printf ' <%s>' "$@" >> "$CALLS"
printf '\\n' >> "$CALLS"
if [[ "${1:-}" == check ]]; then
  exit 0
fi
exit "${APT_INSTALL_EXIT:-0}"
""",
    )
    _write_executable(
        fake_bin / "dpkg",
        """
printf 'dpkg' >> "$CALLS"
printf ' <%s>' "$@" >> "$CALLS"
printf '\\n' >> "$CALLS"
""",
    )
    _write_executable(
        fake_bin / "dpkg-query",
        """
printf 'dpkg-query' >> "$CALLS"
printf ' <%s>' "$@" >> "$CALLS"
printf '\\n' >> "$CALLS"
""",
    )
    _write_executable(fake_bin / "php", "exit 0\n")
    _write_executable(fake_bin / "mariadb", "exit 0\n")

    install_phase = _script().split(
        "# Database and WordPress configuration happens only after all packages install."
    )[0]
    install_phase = install_phase.replace(
        "LOG=/var/log/bbr/install.log", f"LOG={log}"
    ).replace(
        "/etc/nginx/sites-available", str(nginx_sites)
    ).replace(
        "/etc/nginx/snippets/fastcgi-php.conf",
        str(nginx_snippets / "fastcgi-php.conf"),
    )
    runner = tmp_path / "install-phase.sh"
    runner.write_text(install_phase)
    runner.chmod(0o755)

    env = os.environ | {
        "APT_INSTALL_EXIT": str(apt_install_exit),
        "CALLS": str(calls),
        "PACKAGE_DIR": str(package_dir),
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
    }
    result = subprocess.run([runner], env=env, text=True, capture_output=True)
    return result, calls.read_text() if calls.exists() else ""


def test_static_offline_apt_contract():
    script = _script()

    assert "dpkg --unpack" not in script
    assert "dpkg --configure -a" not in script
    assert "--force-depends" not in script
    assert "--ignore-depends" not in script
    assert "apt update" not in script
    assert "apt-get update" not in script
    assert "find \"$PACKAGE_DIR\"" in script
    assert "-type f -name '*.deb' -print" in script
    assert '"${packages[@]}"' in script
    assert "--no-download" in script
    assert "--no-remove" in script
    assert "--no-install-recommends" in script
    assert "Dir::Etc::sourcelist=${empty_sources}" in script
    assert "Dir::Etc::sourceparts=${empty_source_parts}" in script
    assert "trap cleanup EXIT" in script


def test_simulated_resolver_receives_all_local_packages_and_runs_gates(tmp_path):
    result, calls = _run_install_phase(tmp_path)
    assert result.returncode == 0, result.stderr

    lines = calls.splitlines()
    install_call = lines[0]
    install_args = [arg[:-1] for arg in install_call.split(" <")[1:]]
    local_package_args = install_args[install_args.index("install") + 1 :]
    package_args = [
        arg for arg in local_package_args if arg.endswith(".deb")
    ]
    assert len(package_args) == 160
    assert local_package_args == package_args
    assert all(arg.startswith("/") for arg in package_args)
    assert not any(arg.startswith(("http://", "https://")) for arg in package_args)
    assert " <--no-download>" in install_call
    assert " <--no-remove>" in install_call
    assert " <--no-install-recommends>" in install_call
    assert " <install>" in install_call
    assert lines[1:3] == ["dpkg <--audit>", "dpkg <--audit>"]
    assert lines[3] == "apt-get <check>"
    assert lines[4] == (
        "dpkg-query <-W> <nginx> <nginx-common> <php8.2-fpm> "
        "<mariadb-server> <mariadb-common> <gawk> <libmpfr6>"
    )


def test_missing_dependency_stops_before_application_setup(tmp_path):
    result, calls = _run_install_phase(tmp_path, apt_install_exit=100)

    assert result.returncode != 0
    assert calls.count("apt-get") == 1
    assert "dpkg <--audit>" not in calls
    later_stages = _script()[_script().index("# Database and WordPress") :]
    assert "mariadb-install-db" in later_stages
    assert "openssl rand" in later_stages
    assert "wp --allow-root" in later_stages
    assert "systemctl start mariadb" in later_stages


def test_no_remove_rejects_a_simulated_removal_plan(tmp_path):
    result, calls = _run_install_phase(tmp_path, apt_install_exit=100)

    assert result.returncode == 100
    assert " <--no-remove>" in calls.splitlines()[0]
    assert "dpkg <--audit>" not in calls


def test_complete_bootstrap_stage_order():
    installer = _script()
    bootstrap = BOOTSTRAP.read_text()

    assert installer.index("apt-get \\") < installer.index("dpkg --audit")
    assert installer.index("dpkg --audit") < installer.index("apt-get check")
    assert installer.index("apt-get check") < installer.index(
        "test -d /etc/nginx/sites-available"
    )
    assert installer.index("test -d /etc/nginx/sites-available") < installer.index(
        "mariadb-install-db"
    )
    assert installer.index("mariadb-install-db") < installer.index(
        "wp --allow-root --quiet"
    )
    assert bootstrap.index("install-wordpress.sh") < bootstrap.index(
        "cat > /etc/nginx/sites-available/default"
    )
    assert bootstrap.index("cat > /etc/nginx/sites-available/default") < bootstrap.index(
        "configure.sh"
    )
    assert bootstrap.index("configure.sh") < bootstrap.index("systemctl restart")
    assert bootstrap.index("systemctl restart") < bootstrap.index("healthcheck.sh")
