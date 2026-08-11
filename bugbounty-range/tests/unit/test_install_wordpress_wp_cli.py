from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "packs/wordpress-smoke/provisioning/install-wordpress.sh"


def test_wp_core_install_uses_wp_cli_2_12_supported_options():
    script = INSTALLER.read_text()
    install_command = script.split("core install \\", 1)[1].split("\nfi", 1)[0]

    assert "--skip-content" not in install_command
    for option in (
        "--url=",
        "--title=",
        "--admin_user=",
        "--admin_password=",
        "--admin_email=",
    ):
        assert option in install_command
