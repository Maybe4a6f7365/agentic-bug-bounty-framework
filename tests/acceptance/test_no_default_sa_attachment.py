from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_no_default_sa_or_external_access_config():
    main = (ROOT / "platform/your-lab-name/terraform/modules/compute-node/main.tf").read_text()
    assert "use_default_service_account" not in main
    assert "email  = var.runtime_service_account_email" in main
    assert "access_config {" not in main
