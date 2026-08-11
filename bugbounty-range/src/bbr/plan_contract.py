"""Pack-specific Terraform plan contracts."""

from dataclasses import dataclass


PHASE3_ADDRESSES = (
    "module.lab_network.google_compute_subnetwork.lab",
    "module.lab_network.google_service_account.lab_runtime",
    "module.lab_network.google_service_account_iam_member.operator_sa_user",
    "module.lab_node.google_compute_firewall.egress_deny",
    "module.lab_node.google_compute_firewall.iap_ssh",
    "module.lab_node.google_compute_firewall.wireguard_admin",
    "module.lab_node.google_compute_instance.node",
)

WORDPRESS_ADDRESSES = (
    "module.bootstrap_egress.google_compute_firewall.bootstrap_egress",
    "module.lab_network.google_compute_subnetwork.lab",
    "module.lab_network.google_service_account.lab_runtime",
    "module.lab_network.google_service_account_iam_member.operator_sa_user",
    "module.lab_node.google_compute_firewall.egress_deny",
    "module.lab_node.google_compute_firewall.iap_ssh",
    "module.lab_node.google_compute_firewall.wireguard_admin",
    "module.lab_node.google_compute_instance.node",
    "module.wordpress_bucket_binding.google_storage_bucket_iam_member.bootstrap_reader",
)

PHASE3_TYPES = (
    "google_compute_firewall",
    "google_compute_instance",
    "google_compute_subnetwork",
    "google_service_account",
    "google_service_account_iam_member",
)


@dataclass(frozen=True)
class PlanContract:
    expected_create_addresses: tuple[str, ...]
    expected_destroy_addresses: tuple[str, ...]
    allowed_resource_types: tuple[str, ...]
    expected_count: int
    expected_backend_prefix: str
    gate_label: str


def plan_contract(pack_id: str) -> PlanContract:
    if pack_id == "smoke-vm":
        return PlanContract(
            PHASE3_ADDRESSES,
            PHASE3_ADDRESSES,
            PHASE3_TYPES,
            7,
            "labs/smoke-vm-001",
            "BBR_PHASE3_EXECUTE_CONFIRM",
        )
    if pack_id == "wordpress-smoke":
        return PlanContract(
            WORDPRESS_ADDRESSES,
            WORDPRESS_ADDRESSES,
            PHASE3_TYPES + ("google_storage_bucket_iam_member",),
            9,
            "labs/wordpress-smoke-001",
            "BBR_PHASE4_EXECUTE_CONFIRM",
        )
    raise ValueError(f"unsupported plan contract pack_id: {pack_id}")
