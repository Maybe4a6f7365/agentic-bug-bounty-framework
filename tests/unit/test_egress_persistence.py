import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_egress_persists_until_destroy():
    manifest = json.loads((ROOT / "platform/your-lab-name/packs/wordpress-smoke/manifest.json").read_text())
    assert manifest["topology"]["bootstrap_egress_policy"]["remove_after_bootstrap"] is False
    sources = "\n".join(p.read_text() for p in [
        ROOT / "platform/your-lab-name/src/bbr/cli.py",
        ROOT / "platform/your-lab-name/terraform/modules/bootstrap-egress/main.tf",
    ])
    assert "bootstrap_complete_marker" not in sources
