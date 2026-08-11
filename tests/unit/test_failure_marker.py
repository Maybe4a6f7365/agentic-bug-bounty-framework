from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[2] / "platform/your-lab-name/terraform/modules/compute-node/templates/raw-vm-startup.sh.tftpl"


def test_failure_marker_is_complete_and_sanitized():
    function = TEMPLATE.read_text().split("write_failure_marker()", 1)[1].split("trap ", 1)[0]
    for field in ("stage", "exit_code", "utc_time", "artifact_uri"):
        assert field in function
    for forbidden in ("access_token", "artifact_signature", "signature body", "Bearer"):
        assert forbidden not in function
