from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STARTUP = ROOT / "platform/your-lab-name/terraform/modules/compute-node/templates/raw-vm-startup.sh.tftpl"
BOOTSTRAP = ROOT / "platform/your-lab-name/packs/wordpress-smoke/provisioning/bootstrap.sh"


def test_bootstrap_stage_order():
    startup = STARTUP.read_text()
    bootstrap = BOOTSTRAP.read_text()
    positions = [
        startup.index('CURRENT_STAGE="download"'),
        startup.index('CURRENT_STAGE="minisign"'),
        startup.index('CURRENT_STAGE="sha256"'),
        startup.index('CURRENT_STAGE="manifest"'),
        startup.index('CURRENT_STAGE="extract"'),
    ]
    assert positions == sorted(positions)
    install = bootstrap.index("install-wordpress.sh")
    configure = bootstrap.index("configure.sh")
    start = bootstrap.index("systemctl restart")
    health = bootstrap.index("healthcheck.sh")
    assert install < configure < start < health
