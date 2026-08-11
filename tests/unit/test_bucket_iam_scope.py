from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_bucket_only_object_viewer():
    module = ROOT / "platform/your-lab-name/terraform/modules/wordpress-bucket-binding"
    text = "\n".join(p.read_text() for p in module.glob("*.tf"))
    assert "google_storage_bucket_iam_member" in text
    assert "roles/storage.objectViewer" in text
    assert "google_project_iam" not in text
