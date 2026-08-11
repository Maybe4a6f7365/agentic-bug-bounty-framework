# Per-lab Terraform root — Phase 3 generic single-lab lifecycle.
#
# This root is independent of the foundation root. It reads
# the foundation outputs through `terraform_remote_state` and
# produces a lab-lifetime Terraform plan that touches only the
# per-lab resources (1 subnet, 1 service account, 1 service
# account IAM member, 1 VM, 3 firewalls = 7 resources).

terraform {
  required_version = ">= 1.5.0"

  # Backend values are supplied at init time to the partial gcs block.
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0, < 7.0"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
  zone    = var.gcp_zone
}
