from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "platform/your-lab-name/src/bbr/cli.py"
STARTUP = ROOT / "platform/your-lab-name/terraform/modules/compute-node/templates/raw-vm-startup.sh.tftpl"


def test_production_cli_has_no_synthetic_verify_surface():
    text = CLI.read_text()
    assert 'add_argument("--synthetic"' not in text
    assert "BBR_VERIFY_MODE" not in text


def test_restricted_gcs_vips_and_host_are_explicit():
    text = STARTUP.read_text()
    assert "--resolve" in text
    assert "storage.googleapis.com:443:$vip" in text
    for vip in ("199.36.153.4", "199.36.153.5", "199.36.153.6", "199.36.153.7"):
        assert vip in text
    assert "https://storage.googleapis.com/" in text


def test_live_verify_checks_tags_scopes_and_bucket_iam():
    text = CLI.read_text()
    assert 'row.get("targetTags") != [lab_id]' in text
    assert "devstorage.read_only" in text
    assert "roles/storage.objectViewer" in text
    assert '--filter=name:' not in text
