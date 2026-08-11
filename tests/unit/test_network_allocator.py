"""Unit tests for the network allocator."""
from pathlib import Path

import pytest

from bbr.network.allocator import (
    AllocationError,
    CONTROL_PLANE_CIDR,
    _all_pool_cidrs,
    allocate_cidr,
    in_pool,
    list_active_labs,
    list_local_state_cidrs,
)


def _make_state(tmp_path: Path, lab_id: str, cidr: str, state: str = "READY"):
    import json
    (tmp_path / f"{lab_id}.json").write_text(
        json.dumps(
            {
                "lab_id": lab_id,
                "pack_id": "smoke-vm",
                "state": state,
                "lab_subnet_cidr": cidr,
            }
        )
    )


def test_first_allocation_is_10_200_1_0_24(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "bbr.network.allocator.list_gcp_subnet_cidrs",
        lambda *a, **k: [CONTROL_PLANE_CIDR],
    )
    result = allocate_cidr(tmp_path, "fake-project")
    assert result.cidr == "10.200.1.0/24"


def test_control_plane_cidr_excluded_from_pool():
    pool = _all_pool_cidrs()
    assert CONTROL_PLANE_CIDR not in pool
    assert pool[0] == "10.200.1.0/24"


def test_active_lab_limit_enforced(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "bbr.network.allocator.list_gcp_subnet_cidrs",
        lambda *a, **k: [CONTROL_PLANE_CIDR, "10.200.1.0/24"],
    )
    _make_state(tmp_path, "smoke-vm-001", "10.200.1.0/24")
    with pytest.raises(AllocationError):
        allocate_cidr(tmp_path, "fake-project", active_lab_limit=1)


def test_in_use_cidrs_skipped(monkeypatch, tmp_path):
    """If 10.200.1.0/24 is taken, the next allocation must be 10.200.2.0/24."""
    monkeypatch.setattr(
        "bbr.network.allocator.list_gcp_subnet_cidrs",
        lambda *a, **k: [CONTROL_PLANE_CIDR, "10.200.1.0/24"],
    )
    result = allocate_cidr(tmp_path, "fake-project")
    assert result.cidr == "10.200.2.0/24"


def test_in_pool_helper():
    assert in_pool("10.200.5.0/24")
    assert not in_pool(CONTROL_PLANE_CIDR)
    assert not in_pool("10.201.0.0/24")
    assert not in_pool("not-a-cidr")


def test_list_active_labs_ignores_destroyed(tmp_path):
    _make_state(tmp_path, "a", "10.200.5.0/24", state="READY")
    _make_state(tmp_path, "b", "10.200.6.0/24", state="DESTROYED")
    _make_state(tmp_path, "c", "10.200.7.0/24", state="CREATED")
    assert sorted(list_active_labs(tmp_path)) == ["a", "c"]


def test_list_local_state_cidrs_empty_dir(tmp_path):
    assert list_local_state_cidrs(tmp_path) == []
