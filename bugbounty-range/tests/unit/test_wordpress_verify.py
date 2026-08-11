from bbr.cli import (
    _advance_wordpress_verified_state,
    _wordpress_artifact_sha_command,
    _wordpress_firewall_names,
    _wordpress_wp_cli,
)


def test_wordpress_verify_uses_exact_terraform_firewall_names():
    assert _wordpress_firewall_names("wordpress-smoke-001") == {
        "bbr-lab-wordpress-smoke-001-egress-deny",
        "bbr-lab-wordpress-smoke-001-iap-ssh",
        "bbr-lab-wordpress-smoke-001-wg-admin",
        "bbr-wordpress-smoke-001-bootstrap-egress",
    }


def test_wordpress_verify_runs_wp_cli_with_privilege_for_root_owned_config():
    assert _wordpress_wp_cli("core is-installed") == (
        "sudo wp --allow-root --path=/var/www/html core is-installed"
    )


def test_wordpress_verify_hashes_root_only_artifact_with_privilege():
    assert _wordpress_artifact_sha_command().startswith(
        "sudo sha256sum /opt/bbr/artifact.tar.zst"
    )


def test_wordpress_verify_is_idempotent_from_healthy():
    state = {
        "state": "HEALTHY",
        "transition_history": [{"to": "HEALTHY"}],
    }

    assert _advance_wordpress_verified_state(state, "operator") is state
