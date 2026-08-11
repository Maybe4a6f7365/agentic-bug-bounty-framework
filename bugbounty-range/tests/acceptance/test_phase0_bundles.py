import json
from pathlib import Path

import pytest

from bbr.pack_validation import PackValidationError, validate_schema


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas/lab-pack.schema.json"
BUNDLES = sorted(Path(__file__).parent.glob("*.bundle.json"))


@pytest.mark.parametrize("bundle_path", BUNDLES, ids=lambda path: path.stem)
def test_bundle_manifest_is_accepted(bundle_path):
    bundle = json.loads(bundle_path.read_text())
    manifest_path = (bundle_path.parent / bundle["manifest"]).resolve()
    manifest = json.loads(manifest_path.read_text())
    validate_schema(manifest, SCHEMA_PATH)
    counts = {
        driver: sum(
            node["driver"] == driver for node in manifest["topology"]["nodes"]
        )
        for driver in ("compose_vm", "raw_vm")
    }
    assert counts == bundle["expected_driver_counts"]


def test_intentionally_malformed_pack_is_rejected():
    malformed = {"pack_id": "INVALID", "version": "not-semver"}
    with pytest.raises(PackValidationError):
        validate_schema(malformed, SCHEMA_PATH)
