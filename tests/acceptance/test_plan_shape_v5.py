from bbr.cli import _assert_plan_shape

EXPECTED = [
    "module.lab_network.google_compute_subnetwork.lab",
    "module.lab_network.google_service_account.lab_runtime",
    "module.lab_network.google_service_account_iam_member.operator_sa_user",
    "module.lab_node.google_compute_instance.node",
    "module.lab_node.google_compute_firewall.wireguard_admin",
    "module.lab_node.google_compute_firewall.iap_ssh",
    "module.lab_node.google_compute_firewall.egress_deny",
    "module.bootstrap_egress.google_compute_firewall.bootstrap_egress",
    "module.wordpress_bucket_binding.google_storage_bucket_iam_member.bootstrap_reader",
]


def test_exact_v5_addresses():
    plan = {"resource_changes": [
        {"address": address, "change": {"actions": ["create"]}} for address in EXPECTED
    ]}
    assert _assert_plan_shape(plan) == []
