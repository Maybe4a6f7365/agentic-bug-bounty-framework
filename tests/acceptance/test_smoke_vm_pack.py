"""Acceptance test: the smoke-vm pack validates against the live schema
and respects all Phase 3 policy invariants."""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCHEMA = REPO / "platform/your-lab-name/schemas/lab-pack.schema.json"
SMOKE = REPO / "platform/your-lab-name/packs/smoke-vm/manifest.json"

manifest = json.loads(SMOKE.read_text())


def test_smoke_vm_pack_exists():
    assert SMOKE.is_file()


def test_smoke_vm_has_one_node():
    assert len(manifest["topology"]["nodes"]) == 1
    node = manifest["topology"]["nodes"][0]
    assert node["node_id"] == "smoke-vm-001"
    assert node["driver"] == "raw_vm"
    assert node["machine_type"] == "e2-micro"
    assert node["disk_type"] == "pd-standard"
    assert node["disk_size_gb"] == 10


def test_smoke_vm_image_is_pinned_self_link():
    node = manifest["topology"]["nodes"][0]
    image = node["base_image"]
    assert "self_link" in image
    assert image["self_link"].startswith("projects/")
    assert "family" not in image
    assert "digest" not in image


def test_smoke_vm_default_deny_egress():
    policy = manifest["topology"]["runtime_egress_policy"]
    assert policy["default"] == "deny"


def test_smoke_vm_ttl_values():
    ttl = manifest["ttl"]
    assert ttl["max_lifetime"] == "8h"
    assert ttl["idle_timeout"] == "30m"


def test_smoke_vm_cost_within_cycle_limit():
    cl = manifest["cost_limits"]
    assert cl["per_cycle_eur_limit"] <= 2.0  # 2x the smoke cycle guard of 1.0 EUR
