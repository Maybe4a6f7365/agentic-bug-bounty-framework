import pytest

from bbr.bootstrap.errors import BootstrapError
from bbr.cli import contains_forbidden_egress_command, validate_wordpress_driver_payload


def _payload():
    return {
        "artifact_uri": "gs://bbr-bootstrap-project/artifacts/wordpress/1-r1/artifact.tar.zst",
        "artifact_sha256": "0" * 64,
        "artifact_signature": "signature",
        "minisign_trust_store": [{"key_id": "k", "public_key": "p", "valid_since": "now"}],
        "supported_platform": "projects/debian/global/images/debian-12",
    }


@pytest.mark.parametrize("field,value", [
    ("artifact_uri", "https://example.invalid/a"),
    ("artifact_sha256", "bad"),
    ("artifact_signature", ""),
    ("minisign_trust_store", []),
    ("supported_platform", "family/debian"),
])
def test_cli_rejects_invalid_payload(field, value):
    payload = _payload(); payload[field] = value
    with pytest.raises(BootstrapError):
        validate_wordpress_driver_payload(payload)


@pytest.mark.parametrize("command", [
    "  wp core update", "\tapt upgrade", "apt dist-upgrade",
    "composer update", "pip3 install thing", "npm update", " npm install x",
])
def test_egress_forbidden_keywords_extended(command):
    assert contains_forbidden_egress_command(command)

