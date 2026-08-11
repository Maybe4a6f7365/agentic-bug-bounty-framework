import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bbr.cli import _destroy_addresses_are_valid  # noqa: E402
from bbr.plan_contract import WORDPRESS_ADDRESSES  # noqa: E402


NODE_ADDRESS = "module.lab_node.google_compute_instance.node"


def _destroy_plan(addresses):
    return {
        "resource_changes": [
            {
                "address": address,
                "change": {"actions": ["delete"]},
            }
            for address in addresses
        ]
    }


def test_full_lab_with_nine_deletes_passes():
    plan = _destroy_plan(WORDPRESS_ADDRESSES)

    assert _destroy_addresses_are_valid(
        plan,
        WORDPRESS_ADDRESSES,
        WORDPRESS_ADDRESSES,
    )


def test_lab_without_node_with_eight_deletes_passes():
    state_addresses = tuple(
        address for address in WORDPRESS_ADDRESSES if address != NODE_ADDRESS
    )
    plan = _destroy_plan(state_addresses)

    assert _destroy_addresses_are_valid(
        plan,
        state_addresses,
        WORDPRESS_ADDRESSES,
    )


def test_destroy_plan_with_resource_missing_from_state_fails():
    state_addresses = tuple(
        address for address in WORDPRESS_ADDRESSES if address != NODE_ADDRESS
    )
    plan = _destroy_plan(WORDPRESS_ADDRESSES)

    assert not _destroy_addresses_are_valid(
        plan,
        state_addresses,
        WORDPRESS_ADDRESSES,
    )
