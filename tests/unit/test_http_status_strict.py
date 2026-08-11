from pathlib import Path

HEALTH = Path(__file__).resolve().parents[2] / "platform/your-lab-name/packs/wordpress-smoke/provisioning/healthcheck.sh"


def test_http_requires_exact_200():
    text = HEALTH.read_text()
    assert "-w '%{http_code}'" in text
    assert '[[ "$http_status" != "200" ]]' in text
    assert "curl -f" not in text
