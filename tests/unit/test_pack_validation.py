"""Unit tests for the pack validation module."""
from pathlib import Path

import jsonschema  # noqa: F401
import pytest

from bbr.pack_validation import (
    PackValidationError,
    load_manifest,
    validate_cost_limits,
    validate_node_refs,
    validate_pack,
    validate_phase3_image,
    validate_schema,
    validate_ttl,
)

REPO = Path(__file__).resolve().parents[2]
SCHEMA = REPO / "platform/your-lab-name/schemas/lab-pack.schema.json"
SMOKE = REPO / "platform/your-lab-name/packs/smoke-vm/manifest.json"


def test_smoke_vm_validates():
    manifest = load_manifest(SMOKE.parent)
    validate_pack(manifest, SCHEMA)


def test_invalid_pack_rejected():
    bad = {
        "pack_id": "Invalid ID",
        "version": "0.0.1",
        "topology": {"nodes": []},
        "comparison_groups": [],
        "scenarios": [],
        "ttl": {"max_lifetime": "1x"},
        "cost_limits": {"per_cycle_eur_limit": 0.0},
        "teardown_requirements": [],
    }
    with pytest.raises((PackValidationError, jsonschema.ValidationError)):
        validate_pack(bad, SCHEMA)


def test_unknown_node_reference_rejected():
    manifest = load_manifest(SMOKE.parent)
    # mutate: point comparison_groups.node_refs at a node that does not exist
    manifest["comparison_groups"][0]["node_refs"] = ["does-not-exist"]
    with pytest.raises(PackValidationError):
        validate_node_refs(manifest)


def test_control_plane_cidr_never_allocated():
    from bbr.network.allocator import CONTROL_PLANE_CIDR, _all_pool_cidrs
    assert CONTROL_PLANE_CIDR not in _all_pool_cidrs()


def test_cost_limit_zero_rejected():
    with pytest.raises(PackValidationError):
        validate_cost_limits({"cost_limits": {"per_cycle_eur_limit": 0.0}})


def test_ttl_format_check():
    with pytest.raises(PackValidationError):
        validate_ttl({"ttl": {"max_lifetime": "forever"}})


def test_phase3_image_requires_self_link():
    m = {
        "topology": {
            "nodes": [
                {
                    "node_id": "x",
                    "base_image": {"family": "debian-12"},
                }
            ]
        }
    }
    with pytest.raises(PackValidationError):
        validate_phase3_image(m)
