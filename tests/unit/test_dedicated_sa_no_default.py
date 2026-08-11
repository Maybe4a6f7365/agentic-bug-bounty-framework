"""Phase 4A Pre-Execute-Korrektur: dedicated SA + narrow OAuth scope.

The lab VM must attach a dedicated service account (not the GCE default
SA) and must use only the narrowest OAuth scope that allows reading the
bootstrap artifact from the GCS bucket — that is
`https://www.googleapis.com/auth/devstorage.read_only`.

`cloud-platform` is explicitly forbidden because it grants project-wide
authority and would defeat the bucket-scoped IAM binding.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPUTE_NODE_MAIN = (
    ROOT / "platform/your-lab-name/terraform/modules/compute-node/main.tf"
)
COMPUTE_NODE_VARS = (
    ROOT / "platform/your-lab-name/terraform/modules/compute-node/variables.tf"
)
PACK_MANIFEST = (
    ROOT / "platform/your-lab-name/packs/wordpress-smoke/manifest.json"
)


def test_compute_node_no_cloud_platform_scope_literal():
    """The compute-node main.tf must not contain a literal cloud-platform
    scope string. The scope must come from the `runtime_service_account_scopes`
    variable (default = devstorage.read_only)."""
    text = COMPUTE_NODE_MAIN.read_text()
    assert "cloud-platform" not in text, (
        "compute-node/main.tf still references 'cloud-platform' scope. "
        "Phase 4A requires the narrow devstorage.read_only scope, "
        "sourced from the runtime_service_account_scopes variable."
    )


def test_compute_node_scopes_use_variable():
    """The compute-node main.tf must wire `scopes = var.runtime_service_account_scopes`."""
    text = COMPUTE_NODE_MAIN.read_text()
    assert "var.runtime_service_account_scopes" in text, (
        "compute-node/main.tf must wire the OAuth scopes via the "
        "runtime_service_account_scopes variable."
    )


def test_compute_node_scopes_variable_default_is_readonly():
    """The default for runtime_service_account_scopes must be
    devstorage.read_only, not cloud-platform."""
    text = COMPUTE_NODE_VARS.read_text()
    assert "devstorage.read_only" in text
    # Default is devstorage.read_only.
    import re
    m = re.search(
        r'variable\s+"runtime_service_account_scopes"[^}]*default\s*=\s*\[([^\]]+)\]',
        text,
        re.DOTALL,
    )
    assert m is not None, "runtime_service_account_scopes variable missing default"
    default = m.group(1)
    assert "devstorage.read_only" in default
    assert "cloud-platform" not in default


def test_pack_manifest_use_default_service_account_false():
    """The WordPress pack manifest must explicitly disable the GCE
    default service account and require the dedicated lab SA."""
    import json
    text = PACK_MANIFEST.read_text()
    assert "use_default_service_account" in text, (
        "Pack manifest must declare use_default_service_account explicitly."
    )
    # Parse and check the value.
    m = json.loads(text)
    payload = m["topology"]["nodes"][0]["driver_payload"]
    val = payload.get("use_default_service_account")
    assert val is False, (
        f"Expected use_default_service_account=False, got {val!r}"
    )