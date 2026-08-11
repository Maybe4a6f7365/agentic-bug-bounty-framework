# terraform/modules/network — per-lab subnet module

This module allocates a dedicated subnet for one lab inside
the shared access VPC. The module takes a `lab_id` and a
`cidr_block` and returns the subnet self-link plus the
network tags and the runtime service account used to target
the lab's firewall rules.

No resource is enabled in Phase 0. The skeleton shows the
intended inputs and outputs.

```hcl
module "lab_network" {
  source = "../modules/network"

  lab_id            = "wp-cve-2026"
  cidr_block        = "10.77.0.0/24"
  vpc_self_link     = data.terraform_remote_state.foundation.outputs.vpc_self_link
  region            = "europe-west3"

  runtime_service_account_id = "bbr-lab-wp-cve-2026"

  labels = {
    purpose  = "security-research-lab"
    platform = "your-lab-name"
    lab      = "wp-cve-2026"
    operator = "operator:your-researcher-handle"
  }
}
```

The module must NOT contain product-specific code.