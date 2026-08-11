"""Phase 0 + Phase 1 boundary acceptance tests.

Run with:
    python3 -m pytest tests/acceptance/test_phase0_acceptance.py -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
PLATFORM_ROOT = REPO_ROOT
WORKSPACE_ROOT = PLATFORM_ROOT.parents[1]
FOUNDATION_DIR = PLATFORM_ROOT / "terraform" / "foundation"
_plan_output = os.environ.get("BBR_PHASE1_PLAN_OUTPUT")
PLAN_OUTPUT_PATH = Path(_plan_output) if _plan_output else None


def _load_pack_manifest(pack_name: str) -> dict:
    return json.loads(
        (PLATFORM_ROOT / "packs" / pack_name / "manifest.json").read_text()
    )


def _validate_pack_manifest(pack_name: str) -> None:
    from jsonschema import Draft7Validator, RefResolver
    schema_dir = PLATFORM_ROOT / "schemas"
    schema_uri = (schema_dir / "lab-pack.schema.json").as_uri()
    scenario_uri = (schema_dir / "scenario.schema.json").as_uri()
    schema = json.loads((schema_dir / "lab-pack.schema.json").read_text())
    scenario_schema = json.loads(
        (schema_dir / "scenario.schema.json").read_text()
    )
    store = {
        schema_uri: schema,
        scenario_uri: scenario_schema,
    }
    resolver = RefResolver(base_uri=schema_uri, referrer=schema, store=store)
    Draft7Validator.check_schema(schema)
    manifest = _load_pack_manifest(pack_name)
    Draft7Validator(schema, resolver=resolver).validate(manifest)


def test_smoke_compose_manifest_loads_and_validates():
    _validate_pack_manifest("smoke-compose")


def test_smoke_vm_manifest_loads_and_validates():
    _validate_pack_manifest("smoke-vm")


def test_wordpress_pack_manifest_loads_and_validates():
    _validate_pack_manifest("wordpress-wp2shell")


def test_invalid_lifecycle_transition_rejected():
    sys.path.insert(0, str(PLATFORM_ROOT / "src"))
    from bbr.lifecycle import LabState, LifecycleError, StateMachine

    sm = StateMachine()
    # Defined -> Validated is allowed.
    sm.assert_transition(LabState.DEFINED, LabState.VALIDATED)
    # Ready -> Destroyed is not allowed; must raise.
    with pytest.raises(LifecycleError):
        sm.assert_transition(LabState.READY, LabState.DESTROYED)


def test_active_lab_hard_cap_enforced():
    sys.path.insert(0, str(PLATFORM_ROOT / "src"))
    from bbr.network import (
        HARD_MAX_ACTIVE_LABS,
        ActiveLabLimitExceeded,
        assert_within_active_lab_limit,
    )

    # At or above the hard cap the assertion fails.
    with pytest.raises(ActiveLabLimitExceeded):
        assert_within_active_lab_limit(HARD_MAX_ACTIVE_LABS)
    with pytest.raises(ActiveLabLimitExceeded):
        assert_within_active_lab_limit(HARD_MAX_ACTIVE_LABS + 1)
    # One below the hard cap is accepted.
    assert_within_active_lab_limit(HARD_MAX_ACTIVE_LABS - 1)
    assert HARD_MAX_ACTIVE_LABS == 2


def test_subnet_allocation_deterministic_collision_free():
    sys.path.insert(0, str(PLATFORM_ROOT / "src"))
    from bbr.network import (
        PLATFORM_VPC_CIDR,
        allocate_subnet,
    )

    # Two consecutive allocations produce different /24 subnets.
    a = allocate_subnet("lab-a", [])
    b = allocate_subnet("lab-b", [a.cidr_block])
    assert a.cidr_block != b.cidr_block
    # Both stay within the platform VPC range.
    assert a.cidr_block.subnet_of(PLATFORM_VPC_CIDR)
    assert b.cidr_block.subnet_of(PLATFORM_VPC_CIDR)


def test_unregistered_scenario_destination_rejected():
    sys.path.insert(0, str(PLATFORM_ROOT / "src"))
    from bbr.scenarios import (
        DestinationRejected,
        validate_destination_ref,
    )

    lab_state = {
        "topology": {
            "nodes": [
                {
                    "node_id": "redis-1",
                    "exposed_private_services": [
                        {"name": "redis", "port": 6379}
                    ],
                }
            ]
        }
    }
    # Registered node + service is accepted.
    validate_destination_ref("redis-1:redis", lab_state=lab_state)
    # Unregistered node is rejected.
    with pytest.raises(DestinationRejected):
        validate_destination_ref(
            "missing-node:redis", lab_state=lab_state
        )


def test_public_ip_scenario_destination_rejected():
    sys.path.insert(0, str(PLATFORM_ROOT / "src"))
    from bbr.scenarios import DestinationRejected, validate_destination_ref

    lab_state = {
        "topology": {
            "nodes": [
                {
                    "node_id": "redis-1",
                    "exposed_private_services": [
                        {"name": "redis", "port": 6379}
                    ],
                }
            ]
        }
    }
    with pytest.raises(DestinationRejected):
        validate_destination_ref(
            "203.0.113.42:6379", lab_state=lab_state
        )
    with pytest.raises(DestinationRejected):
        validate_destination_ref(
            "https://example.com/path", lab_state=lab_state
        )


def test_no_symlinks_under_platform_root():
    """No symbolic links anywhere under platform/your-lab-name/.
    Decision 3 forbids symbolic links; the migration script
    copies files instead."""
    for path in PLATFORM_ROOT.rglob("*"):
        if path.is_symlink():
            pytest.fail(f"symbolic link found: {path}")


def test_pack_references_cannot_escape_repository():
    """Pack references must remain below the research repository.

    Phase-0 skeleton packs may declare files delivered in later phases, but
    references must not resolve outside the controlled repository.
    """
    for pack_dir in (PLATFORM_ROOT / "packs").iterdir():
        manifest_path = pack_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text())
        referenced: list[str] = []
        for node in manifest.get("topology", {}).get("nodes", []):
            for hook in (
                node.get("lifecycle_hooks") or {}
            ).values():
                if hook:
                    referenced.append(hook)
            for hook in (
                node.get("snapshot_hooks") or {}
            ).values():
                if hook:
                    referenced.append(hook)
            driver_payload = node.get("driver_payload") or {}
            for ref in driver_payload.values():
                if isinstance(ref, str) and ref.endswith(
                    (".sh", ".yml", ".yaml")
                ):
                    referenced.append(ref)
        for rel in referenced:
            candidate = Path(rel)
            assert not candidate.is_absolute()
            assert (pack_dir / candidate).resolve().is_relative_to(
                WORKSPACE_ROOT
            )


def test_no_concrete_private_key_paths_in_committed_files():
    """No file in platform/your-lab-name/ may contain a
    literal ~/.hermes/secrets/wireguard/... path or a Hermes
    internal cache path. BBR_WG_PRIVATE_KEY_FILE is the only
    allowed reference."""
    import re

    forbidden_patterns = [
        r"~/\.hermes/secrets/wireguard",
        r"/home/admin/\.hermes/cache/documents",
    ]
    allowed_reference = "BBR_WG_PRIVATE_KEY_FILE"

    offenders: list[str] = []
    for path in PLATFORM_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.resolve() == Path(__file__).resolve():
            continue
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        for pat in forbidden_patterns:
            if re.search(pat, text):
                offenders.append(f"{path}: pattern {pat!r}")
    assert not offenders, "\n".join(offenders)


# ─────────────────────────────────────────────────────────────────────
# Phase 1 boundary checks
# ─────────────────────────────────────────────────────────────────────

PHASE1_EXPECTED_RESOURCES = {
    "google_billing_budget.platform",
    "google_project.bbr",
    'google_project_service.foundation["billingbudgets.googleapis.com"]',
    'google_project_service.foundation["cloudbilling.googleapis.com"]',
    'google_project_service.foundation["cloudresourcemanager.googleapis.com"]',
    'google_project_service.foundation["compute.googleapis.com"]',
    'google_project_service.foundation["iam.googleapis.com"]',
    'google_project_service.foundation["iap.googleapis.com"]',
    'google_project_service.foundation["storage.googleapis.com"]',
    "google_storage_bucket.state",
}


@pytest.mark.skipif(
    PLAN_OUTPUT_PATH is None or not PLAN_OUTPUT_PATH.exists(),
    reason="no current plan supplied via BBR_PHASE1_PLAN_OUTPUT",
)
def test_phase1_plan_resources_only_foundation():
    """Phase 1 plan must list exactly the 10 documented
    foundation resources and nothing else."""
    content = PLAN_OUTPUT_PATH.read_text()
    actual = set()
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("# ") and " will be created" in line:
            actual.add(line[2:].split(" will be created")[0])
    assert actual == PHASE1_EXPECTED_RESOURCES, (
        f"Phase 1 plan resources mismatch.\n"
        f"  expected: {sorted(PHASE1_EXPECTED_RESOURCES)}\n"
        f"  actual:   {sorted(actual)}"
    )


@pytest.mark.skipif(
    PLAN_OUTPUT_PATH is None or not PLAN_OUTPUT_PATH.exists(),
    reason="no current plan supplied via BBR_PHASE1_PLAN_OUTPUT",
)
def test_phase1_plan_no_compute_network_or_firewall():
    """No compute, container, SQL, network, or firewall
    resources may appear in the Phase 1 plan. Operator
    correction 1."""
    content = PLAN_OUTPUT_PATH.read_text()
    forbidden_prefixes = (
        "google_compute_instance",
        "google_compute_network",
        "google_compute_subnetwork",
        "google_compute_firewall",
        "google_compute_address",
        "google_container_cluster",
        "google_sql_",
        "google_redis_",
        "google_folder",
    )
    offenders: list[str] = []
    for line in content.splitlines():
        line = line.strip()
        for prefix in forbidden_prefixes:
            if prefix in line and "will be created" in line:
                offenders.append(line)
    assert not offenders, (
        "Phase 1 plan contains forbidden resource types:\n"
        + "\n".join(offenders)
    )
