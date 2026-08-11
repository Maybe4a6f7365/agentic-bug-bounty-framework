from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "platform/your-lab-name/terraform/modules/bootstrap-egress"
LAB = ROOT / "platform/your-lab-name/terraform/lab"


def test_module_priority_1000():
    assert "priority           = 1000" in (MODULE / "main.tf").read_text()


def test_module_destination_ranges_default():
    text = (MODULE / "variables.tf").read_text()
    assert 'default = ["199.36.153.4/30"]' in text
    assert "34.117.0.0/16" not in text


def test_module_removal_on_complete_marker():
    assert "bootstrap_complete_marker" not in (MODULE / "main.tf").read_text()


def test_module_instantiated_in_lab_main_tf():
    """Phase 4 Lücken-Fix Blocker B: the bootstrap-egress module must be
    instantiated from the per-lab main.tf so its firewall appears in
    the terraform plan. Without this, the lab VM cannot reach GCS
    during the BOOTSTRAPPING phase (Default-Deny at priority 65000)."""
    text = (LAB / "main.tf").read_text()
    assert 'module "bootstrap_egress"' in text
    assert "../modules/bootstrap-egress" in text
    assert "target_tags" in text and "[var.lab_id]" in text


def test_lab_main_tf_instantiates_exactly_one_extra_module():
    """Phase 4 Pre-Execute-Korrektur Blocker B: with the bootstrap_egress
    module instantiated, the lab root must instantiate exactly the three
    lab modules — lab_network, lab_node, bootstrap_egress. Adding more
    lab modules or removing one would break the expected plan count of
    9 add / 0 change / 0 destroy."""
    text = (LAB / "main.tf").read_text()
    modules = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith('module "') and line.endswith('" {'):
            modules.append(line.split('"')[1])
    assert "lab_network" in modules
    assert "lab_node" in modules
    assert "bootstrap_egress" in modules
    # No other lab modules should be present at this stage.
    assert "wordpress_bucket_binding" in modules
    assert len(modules) == 4, (
        f"expected exactly 4 lab modules in main.tf, got {modules}"
    )


def test_lab_main_tf_has_no_backend_block_with_variables():
    """Phase 4 Pre-Execute-Korrektur Blocker A: lab/main.tf must NOT
    contain a `terraform { backend "..." { ... } }` block that uses
    Terraform variables. Variables in backend blocks are invalid because
    backends are initialised before variable evaluation; the value would
    be the literal string "${var.foo}" instead of the variable's value.
    The Phase-3 mechanism (`terraform init -backend-config=...`) is
    preserved as the correct approach."""
    text = (LAB / "main.tf").read_text()
    # A bare `terraform {` could be either backend-block or version-block;
    # the version-block has no inner `backend "..."`. We assert that
    # any `backend "..."` block within a `terraform { ... }` does not
    # contain any ${var. reference.
    import re
    tf_blocks = re.findall(r"terraform\s*\{[^}]*\}", text, re.DOTALL)
    for blk in tf_blocks:
        assert "${var." not in blk


def test_bootstrap_egress_module_no_public_internet_allow():
    """Phase 4 Pre-Execute-Korrektur Blocker B: the bootstrap egress
    firewall must not allow 0.0.0.0/0 (general internet); it must be
    restricted to the GCS API ranges. Read from the module source."""
    main_tf = (ROOT / "platform/your-lab-name/terraform/modules/bootstrap-egress/main.tf").read_text()
    variables_tf = (ROOT / "platform/your-lab-name/terraform/modules/bootstrap-egress/variables.tf").read_text()
    # Default values for egress_destination_ranges must not include 0.0.0.0/0
    assert "0.0.0.0/0" not in variables_tf, (
        "bootstrap-egress default destination_ranges must not include 0.0.0.0/0"
    )
    assert "199.36.153.4/30" in variables_tf
    assert "34.117.0.0/16" not in variables_tf
    # The protocol must be tcp, ports ["443"]
    assert 'protocol = var.egress_protocol' in main_tf
    assert 'ports    = var.egress_ports' in main_tf
    # Default values for protocol and ports (whitespace-insensitive).
    assert re.search(r'default\s*=\s*"tcp"', variables_tf)
    assert re.search(r'default\s*=\s*\["443"\]', variables_tf)
