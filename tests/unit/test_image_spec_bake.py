from pathlib import Path

SPEC = Path(__file__).resolve().parents[2] / "platform/your-lab-name/packs/wordpress-smoke/image-bake-spec.md"


def test_bake_spec_required_tools():
    text = SPEC.read_text()
    for tool in ("curl", "sha256sum", "minisign", "jq", "tar", "unzstd"):
        assert tool in text
