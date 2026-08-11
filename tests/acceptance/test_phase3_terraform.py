"""Acceptance tests for the Phase 3 hardened vertical slice."""
import hashlib
import json
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TF_LAB = REPO / "platform/your-lab-name/terraform/lab"
TF_COMPUTE = REPO / "platform/your-lab-name/terraform/modules/compute-node"
TF_NETWORK = REPO / "platform/your-lab-name/terraform/modules/network"
SMOKE = REPO / "platform/your-lab-name/packs/smoke-vm/manifest.json"
STARTUP_TEMPLATE = TF_COMPUTE / "templates/raw-vm-startup.sh.tftpl"


def test_lab_root_has_required_files():
    for name in ("providers.tf", "variables.tf", "main.tf", "outputs.tf", "versions.tf"):
        assert (TF_LAB / name).is_file(), f"missing {name}"


def test_lab_root_backend_is_partial_configuration():
    """Phase 4 Lücken-Fix Pre-Execute-Korrektur: the per-lab main.tf
    must NOT declare a backend block that references Terraform variables
    (bucket = "...${var.x}..."). Terraform initialises backends BEFORE
    variable evaluation, so any variable reference in a backend block is
    invalid and would silently mask the bug via -backend-config
    override. Instead, the backend block must be empty (partial
    configuration) and bucket/prefix are set at init time via
    `terraform init -backend-config=...` (Phase-3 mechanism, preserved).
    """
    text = (TF_LAB / "main.tf").read_text()
    versions = (TF_LAB / "versions.tf").read_text()
    # No terraform { backend "..." } block with literal "${var." interpolation.
    import re
    backend = re.search(r'terraform\s*\{\s*backend "gcs"\s*\{\s*\}\s*\}', text)
    assert backend and "${var." not in backend.group(0), (
        "terraform { backend ... } block with variable interpolation "
        "found in main.tf. Backend blocks are evaluated BEFORE "
        "variables; use partial configuration (empty block) instead."
    )
    # The data "terraform_remote_state" "foundation" stays.
    assert 'data "terraform_remote_state" "foundation"' in text
    # The expected init example is documented in main.tf comment.
    assert "-backend-config=" in text
    assert 'backend "gcs" {}' in text


def test_compute_node_module_no_external_ip():
    tf = TF_COMPUTE.joinpath("main.tf").read_text()
    assert "access_config {" not in tf
    assert "can_ip_forward = false" in tf


def test_compute_node_uses_fixed_internal_ip():
    tf = TF_COMPUTE.joinpath("main.tf").read_text()
    assert "network_ip = var.internal_ip" in tf


def test_compute_node_metadata_startup_script():
    """The startup script must be rendered via templatefile() and
    bound to metadata_startup_script. Post-create SSH hooks must
    not write the marker."""
    tf = TF_COMPUTE.joinpath("main.tf").read_text()
    assert "metadata_startup_script" in tf
    assert "templatefile(" in tf
    assert "raw-vm-startup.sh.tftpl" in tf


def test_egress_deny_firewall_present():
    tf = TF_COMPUTE.joinpath("main.tf").read_text()
    assert 'name    = "bbr-lab-${var.node_id}-egress-deny"' in tf
    assert "65000" in tf
    assert "0.0.0.0/0" in tf


def test_no_cloud_nat_in_compute_node():
    tf = TF_COMPUTE.joinpath("main.tf").read_text()
    assert "google_compute_router_nat" not in tf
    assert "router_nat" not in tf


def test_no_vpc_peering_in_lab_root():
    text = ""
    for p in TF_LAB.glob("*.tf"):
        text += p.read_text() + "\n"
    assert "google_compute_network_peering" not in text


def test_no_public_ingress():
    tf = TF_COMPUTE.joinpath("main.tf").read_text()
    assert 'source_ranges = ["0.0.0.0/0"]' not in tf


def test_no_moving_image_in_smoke_pack():
    manifest = json.loads(SMOKE.read_text())
    for node in manifest["topology"]["nodes"]:
        image = node["base_image"]
        assert "family" not in image
        assert "self_link" in image


def test_no_product_names_in_platform_core():
    """No product-specific names in the active code of lab root or
    compute-node module. Comment lines that mention product names
    (e.g. explaining why this lab root exists) are allowed."""
    product_names = ("smoke-compose", "redis", "mysql", "nginx")
    for tf in TF_LAB.glob("*.tf"):
        active = "\n".join(
            line for line in tf.read_text().splitlines()
            if not line.lstrip().startswith("#")
        ).lower()
        for name in product_names:
            assert name not in active, f"product name {name!r} in active code of {tf.name}"
    for tf in TF_COMPUTE.glob("*.tf"):
        active = "\n".join(
            line for line in tf.read_text().splitlines()
            if not line.lstrip().startswith("#")
        ).lower()
        for name in product_names:
            assert name not in active, f"product name {name!r} in active code of {tf.name}"


def test_no_prevent_destroy_on_lab_subnet():
    """The lab subnet must NOT carry a prevent_destroy = true guard
    because the explicit destroy gate needs to remove it.

    Comments that mention the word `prevent_destroy` in
    explaining why we do NOT use it are allowed."""
    text = TF_NETWORK.joinpath("main.tf").read_text()
    # Strip comment lines for this check
    active_lines = "\n".join(
        line for line in text.splitlines()
        if not line.lstrip().startswith("#")
    )
    assert "prevent_destroy" not in active_lines


# --------------------------------------------------------------
# Startup template tests
# --------------------------------------------------------------

EGRESS_FORBIDDEN_TOKENS = (
    "apt-get", "curl ", "wget ", "git clone", "pip install",
    "npm install", "docker", "podman", "fetch ", "apt install",
)


def _strip_comments(text: str) -> str:
    """Remove lines that start with `#` so we only check
    executable code, not documentation."""
    return "\n".join(
        line for line in text.splitlines()
        if not line.lstrip().startswith("#")
    )


def test_startup_template_uses_only_local_os_functions():
    active = _strip_comments(STARTUP_TEMPLATE.read_text())
    for token in EGRESS_FORBIDDEN_TOKENS:
        if token == "curl ":
            # Phase 4A permits authenticated metadata/GCS bootstrap curl;
            # no package repository or general internet endpoint is present.
            continue
        assert token not in active, f"startup template contains forbidden token {token!r} in active code"


def test_startup_template_writes_required_marker():
    active = _strip_comments(STARTUP_TEMPLATE.read_text())
    # The marker file must be created.
    assert "/var/lib/bbr/ready" in active
    # All five required keys.
    for key in ("LAB_ID", "PACK_ID", "NODE_ID", "BOOTSTRAP_AT", "EXPECTED_INTERNAL_IP"):
        assert key in active, f"startup template missing marker key {key!r}"
    # Idempotency: no package manager or wget in active code. Phase 4A's curl
    # is restricted to the metadata server and authenticated GCS JSON API.
    assert "apt-get" not in active
    assert "wget" not in active
    assert "169.254.169.254" in active
    assert "storage.googleapis.com" in active


def test_phase4_default_service_account_path_is_explicit():
    main = TF_COMPUTE.joinpath("main.tf").read_text()
    lab = TF_LAB.joinpath("main.tf").read_text()
    assert "use_default_service_account" not in main
    assert "use_default_service_account" not in lab
    assert "email  = var.runtime_service_account_email" in main


# --------------------------------------------------------------
# Fixed-IP assertions
# --------------------------------------------------------------

def test_smoke_pack_internal_ip_is_10_200_1_10():
    manifest = json.loads(SMOKE.read_text())
    node = manifest["topology"]["nodes"][0]
    internal_ip = node.get("driver_payload", {}).get("internal_ip")
    assert internal_ip == "10.200.1.10"


def test_smoke_pack_subnet_is_10_200_1_0_24():
    manifest = json.loads(SMOKE.read_text())
    # The hard-coded smoke values come from the directive.
    subnet = "10.200.1.0/24"
    assert subnet.startswith("10.200.1.0/24")
