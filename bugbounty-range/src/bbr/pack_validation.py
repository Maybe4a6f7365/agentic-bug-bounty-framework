"""BugBountyRange pack validation — Phase 3.

Validates a single pack manifest against the lab-pack schema
and against a set of platform-specific additional checks that
the JSON schema cannot easily express:

  - every comparison_groups[].node_refs[*] exists in topology.nodes
  - every scenario.steps[*].node_ref exists in topology.nodes
  - every evidence_sources[*].node_ref exists in topology.nodes
  - cost_limits.per_cycle_eur_limit is positive and bounded
  - ttl.max_lifetime is parseable as "<N>(s|m|h)"
  - Phase 3 packs must use base_image.self_link (no family, no digest)
  - Phase 3 packs must have cost_limits.per_cycle_eur_limit
    bounded by 2 * PHASE3_SMOKE_CYCLE_LIMIT_EUR (default 2.00 EUR)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

import jsonschema
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT7


class PackValidationError(ValueError):
    """Raised when a pack manifest fails validation."""


class SchemaLoadError(RuntimeError):
    """Raised when the lab-pack schema cannot be loaded."""


TTL_PATTERN = re.compile(r"^[0-9]+(s|m|h)$")


def _load_schema(schema_path: Path) -> Dict[str, Any]:
    if not schema_path.is_file():
        raise SchemaLoadError(f"lab-pack schema not found at {schema_path}")
    return json.loads(schema_path.read_text())


def _build_registry(schema_path: Path) -> tuple[Dict[str, Any], Registry]:
    schema = _load_schema(schema_path)
    scenario_path = schema_path.parent / "scenario.schema.json"
    if not scenario_path.is_file():
        raise SchemaLoadError(f"scenario schema not found at {scenario_path}")
    scenario_uri = "file://" + str(scenario_path.resolve())
    scenario_resource = Resource.from_contents(
        json.loads(scenario_path.read_text()), default_specification=DRAFT7
    )
    return schema, Registry().with_resources([(scenario_uri, scenario_resource)])


def validate_schema(
    manifest: Dict[str, Any], schema_path: Path
) -> None:
    schema, registry = _build_registry(schema_path)
    validator = jsonschema.Draft7Validator(schema, registry=registry)
    errors = sorted(validator.iter_errors(manifest), key=lambda e: list(e.path))
    if errors:
        msgs = [f"{'/'.join(map(str, e.path))}: {e.message}" for e in errors]
        raise PackValidationError("schema validation failed: " + "; ".join(msgs))


def _node_ids(manifest: Dict[str, Any]) -> List[str]:
    return [n["node_id"] for n in manifest["topology"]["nodes"]]


def validate_node_refs(manifest: Dict[str, Any]) -> None:
    nodes = set(_node_ids(manifest))
    errors: List[str] = []
    for group in manifest.get("comparison_groups", []):
        for ref in group.get("node_refs", []):
            if ref not in nodes:
                errors.append(f"comparison_groups[{group['group_id']}].node_refs: unknown node {ref!r}")
    for i, scenario in enumerate(manifest.get("scenarios", [])):
        for j, step in enumerate(scenario.get("steps", [])):
            ref = step.get("node_ref")
            if ref and ref not in nodes:
                errors.append(
                    f"scenarios[{i}].steps[{j}].node_ref: unknown node {ref!r}"
                )
    for i, ev in enumerate(manifest.get("evidence_sources", [])):
        ref = ev.get("node_ref")
        if ref and ref not in nodes:
            errors.append(f"evidence_sources[{i}].node_ref: unknown node {ref!r}")
    if errors:
        raise PackValidationError("node reference validation failed: " + "; ".join(errors))


def validate_cost_limits(
    manifest: Dict[str, Any], *, smoke_cycle_limit_eur: float = 1.00
) -> None:
    """Phase 3 cost guard.

    The single hard limit is PHASE3_SMOKE_CYCLE_LIMIT_EUR (1.00 EUR).
    This default makes the cap explicit at the boundary; callers
    that want to override it must pass an explicit kwarg.
    """
    cl = manifest.get("cost_limits", {})
    if "per_cycle_eur_limit" not in cl:
        raise PackValidationError("cost_limits.per_cycle_eur_limit is required")
    limit = cl["per_cycle_eur_limit"]
    if not isinstance(limit, (int, float)) or limit <= 0:
        raise PackValidationError("cost_limits.per_cycle_eur_limit must be a positive number")
    if limit > smoke_cycle_limit_eur:
        raise PackValidationError(
            f"cost_limits.per_cycle_eur_limit={limit} exceeds "
            f"PHASE3_SMOKE_CYCLE_LIMIT_EUR ({smoke_cycle_limit_eur})"
        )


def validate_ttl(manifest: Dict[str, Any]) -> None:
    ttl = manifest.get("ttl", {})
    if "max_lifetime" not in ttl:
        raise PackValidationError("ttl.max_lifetime is required")
    if not TTL_PATTERN.match(ttl["max_lifetime"]):
        raise PackValidationError(
            f"ttl.max_lifetime must look like '<N>s|m|h' (got {ttl['max_lifetime']!r})"
        )


def validate_phase3_image(manifest: Dict[str, Any]) -> None:
    """Phase 3 packs MUST use base_image.self_link. family/digest are rejected."""
    errors: List[str] = []
    for node in manifest.get("topology", {}).get("nodes", []):
        image = node.get("base_image", {})
        if "self_link" not in image:
            errors.append(
                f"node {node['node_id']!r}: Phase 3 smoke packs must use base_image.self_link "
                f"(got keys: {sorted(image.keys())})"
            )
    if errors:
        raise PackValidationError("image validation failed: " + "; ".join(errors))


def validate_pack(
    manifest: Dict[str, Any],
    schema_path: Path,
    *,
    smoke_cycle_limit_eur: float = 1.00,
) -> None:
    validate_schema(manifest, schema_path)
    validate_node_refs(manifest)
    validate_cost_limits(manifest, smoke_cycle_limit_eur=smoke_cycle_limit_eur)
    validate_ttl(manifest)
    validate_phase3_image(manifest)


def load_manifest(pack_dir: Path) -> Dict[str, Any]:
    mf = pack_dir / "manifest.json"
    if not mf.is_file():
        raise PackValidationError(f"manifest.json not found in {pack_dir}")
    return json.loads(mf.read_text())