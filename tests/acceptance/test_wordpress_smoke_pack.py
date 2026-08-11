import json
from pathlib import Path

from bbr.pack_validation import validate_pack

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "platform/your-lab-name/packs/wordpress-smoke"


def test_pack_manifest_valid():
    manifest = json.loads((PACK / "manifest.json").read_text())
    validate_pack(manifest, ROOT / "platform/your-lab-name/schemas/lab-pack.schema.json")


def test_pack_provisioning_scripts_present():
    for name in ("bootstrap.sh", "install-wordpress.sh", "configure.sh",
                 "healthcheck.sh", "rollback.sh", "preflight.sh",
                 "post_destroy.sh", "wp-config.php.tmpl"):
        assert (PACK / "provisioning" / name).is_file()


def test_pack_build_environment_documented():
    assert (PACK / "BUILD-ENVIRONMENT.md").is_file()


def test_pack_bootstrap_egress_policy_in_manifest():
    policy = json.loads((PACK / "manifest.json").read_text())["topology"]["bootstrap_egress_policy"]
    assert policy["enabled"] and policy["remove_after_bootstrap"] is False


def test_pack_minisign_trust_store_in_manifest():
    payload = json.loads((PACK / "manifest.json").read_text())["topology"]["nodes"][0]["driver_payload"]
    assert payload["minisign_trust_store"]
