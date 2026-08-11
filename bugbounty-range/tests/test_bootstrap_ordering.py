import shlex
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "packs/wordpress-smoke/provisioning/bootstrap.sh"

INSTALL = "/var/lib/bbr/provisioning/install-wordpress.sh"
NGINX_DIRECTORY_CHECK = "test -d /etc/nginx/sites-available"
FASTCGI_SNIPPET_CHECK = "test -f /etc/nginx/snippets/fastcgi-php.conf"
NGINX_CONFIG = "cat > /etc/nginx/sites-available/default <<'EOF'"
CONFIGURE = "/var/lib/bbr/provisioning/configure.sh"
RESTART = "systemctl restart mariadb php8.2-fpm nginx"
HEALTHCHECK = "/var/lib/bbr/provisioning/healthcheck.sh"

EXPECTED_NGINX_CONFIG_BLOCK = """\
cat > /etc/nginx/sites-available/default <<'EOF'
server {
  listen 80 default_server;
  root /var/www/html;
  index index.php index.html;
  location / { try_files $uri $uri/ /index.php?$args; }
  location ~ \\.php$ {
    include snippets/fastcgi-php.conf;
    fastcgi_pass unix:/run/php/php8.2-fpm.sock;
  }
}
EOF
"""


def _bootstrap() -> str:
    return BOOTSTRAP.read_text()


def _line_number(script: str, text: str) -> int:
    return next(
        number
        for number, line in enumerate(script.splitlines(), start=1)
        if text in line
    )


def test_install_precedes_nginx_configuration():
    script = _bootstrap()

    assert script.index(INSTALL) < script.index(NGINX_CONFIG)


def test_nginx_directory_check_precedes_configuration():
    script = _bootstrap()

    assert script.index(NGINX_DIRECTORY_CHECK) < script.index(NGINX_CONFIG)


def test_fastcgi_snippet_check_precedes_configuration():
    script = _bootstrap()

    assert script.index(FASTCGI_SNIPPET_CHECK) < script.index(NGINX_CONFIG)


def test_stage_exit_codes_are_preserved():
    script = _bootstrap()

    assert f"{INSTALL} || exit 36" in script
    assert f"{CONFIGURE} || exit 37" in script
    assert f"{RESTART} || exit 38" in script
    assert f"{HEALTHCHECK} || exit 39" in script


def test_bootstrap_does_not_use_apt():
    script = _bootstrap()

    assert "apt update" not in script
    assert "apt install" not in script


def test_nginx_configuration_block_is_unchanged():
    assert EXPECTED_NGINX_CONFIG_BLOCK in _bootstrap()


def test_runtime_stage_line_order():
    script = _bootstrap()
    install_line = _line_number(script, INSTALL)
    directory_check_line = _line_number(script, NGINX_DIRECTORY_CHECK)
    nginx_config_line = _line_number(script, NGINX_CONFIG)
    configure_line = _line_number(script, CONFIGURE)
    restart_line = _line_number(script, RESTART)
    healthcheck_line = _line_number(script, HEALTHCHECK)

    assert install_line < directory_check_line < nginx_config_line
    assert nginx_config_line < configure_line < restart_line < healthcheck_line


def test_missing_nginx_directory_exits_36_before_later_stages(tmp_path):
    script = _bootstrap()
    runtime_stages = script[script.index(INSTALL) :]
    missing_directory = tmp_path / "missing/sites-available"
    missing_snippet = tmp_path / "missing/snippets/fastcgi-php.conf"
    nginx_config = tmp_path / "missing/sites-available/default"

    runtime_stages = runtime_stages.replace(INSTALL, "install_wordpress")
    runtime_stages = runtime_stages.replace(CONFIGURE, "configure")
    runtime_stages = runtime_stages.replace(HEALTHCHECK, "healthcheck")
    runtime_stages = runtime_stages.replace(
        "/etc/nginx/sites-available", str(missing_directory)
    )
    runtime_stages = runtime_stages.replace(
        "/etc/nginx/snippets/fastcgi-php.conf", str(missing_snippet)
    )
    runtime_stages = runtime_stages.replace(
        f"cat > {missing_directory}/default",
        f"cat > {shlex.quote(str(nginx_config))}",
    )
    marker = tmp_path / "calls"
    stubbed_script = "\n".join(
        (
            "set -euo pipefail",
            f"marker={shlex.quote(str(marker))}",
            'install_wordpress() { printf "install\\n" >> "$marker"; }',
            'configure() { printf "configure\\n" >> "$marker"; }',
            'healthcheck() { printf "healthcheck\\n" >> "$marker"; }',
            'systemctl() { printf "systemctl %s\\n" "$*" >> "$marker"; }',
            'log() { printf "log %s\\n" "$*" >> "$marker"; }',
            runtime_stages,
        )
    )

    result = subprocess.run(
        ["bash", "-c", stubbed_script],
        text=True,
        capture_output=True,
    )

    assert result.returncode == 36, result.stderr
    assert marker.read_text().splitlines() == ["install"]
