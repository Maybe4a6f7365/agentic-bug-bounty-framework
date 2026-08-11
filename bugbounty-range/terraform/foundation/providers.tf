terraform {
  required_version = ">= 1.6.0, < 2.0.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.40"
    }
  }

  # Partial GCS backend. Bucket and prefix are supplied at
  # init/migrate time via -backend-config. No interpolation.
  # Initialised and migrated after the bucket was created in
  # the Phase 1 apply.
  backend "gcs" {}
}

# Phase 1 bootstraps with local state because the GCS bucket does
# not exist before the first apply. After the bucket is created,
# migrate state with:
#
# terraform init -migrate-state \
#   -backend-config="bucket=bbr-state-<project-id>" \
#   -backend-config="prefix=foundation"
#
# The backend block is added only after the bucket exists; backend
# configuration cannot reference Terraform variables.

# Default provider. The bootstrap creates the project itself with
# this provider because no project exists yet, so the provider
# cannot route through the to-be-created project as quota project.
provider "google" {
  region = var.gcp_region
  zone   = var.gcp_zone
}

# Billing-budget provider. google_billing_budget APIs require
# the request to be charged to a specific GCP project. After the
# project is created the billing provider pins its quota project
# to var.gcp_project_id so that the budget is not routed through
# an unrelated ADC quota project.
provider "google" {
  alias                 = "billing"
  region                = var.gcp_region
  zone                  = var.gcp_zone
  user_project_override = true
  billing_project       = var.gcp_project_id
}
