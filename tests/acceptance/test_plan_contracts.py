from bbr.plan_contract import plan_contract


def test_phase3_plan_and_destroy_contract():
    contract = plan_contract("smoke-vm")
    assert contract.expected_count == 7
    assert len(contract.expected_create_addresses) == 7
    assert len(contract.expected_destroy_addresses) == 7
    assert contract.expected_backend_prefix == "labs/smoke-vm-001"


def test_phase4_plan_and_destroy_contract():
    contract = plan_contract("wordpress-smoke")
    assert contract.expected_count == 9
    assert len(contract.expected_create_addresses) == 9
    assert len(contract.expected_destroy_addresses) == 9
    assert contract.expected_backend_prefix == "labs/wordpress-smoke-001"
    assert "google_storage_bucket_iam_member" in contract.allowed_resource_types
