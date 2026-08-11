# Phase 1 foundation inputs.

variable "gcp_project_id" {
  description = "Dedicated GCP project ID. Must be globally unique."
  type        = string
  sensitive   = true

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.gcp_project_id))
    error_message = "gcp_project_id must be 6-30 lowercase letters, digits, or hyphens, start with a letter, and end with a letter or digit."
  }
}

variable "billing_account_id" {
  description = "GCP billing account ID used for the project and budget alert."
  type        = string
  sensitive   = true
}

variable "gcp_organization_id" {
  description = "Existing GCP organization ID that will own the project. Exactly one of gcp_organization_id or gcp_folder_id must be set."
  type        = string
  default     = null
  nullable    = true
}

variable "gcp_folder_id" {
  description = "Existing GCP folder ID that will own the project. Exactly one of gcp_organization_id or gcp_folder_id must be set. No folder is created by this module."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition = (
      (var.gcp_folder_id == null && var.gcp_organization_id != null) ||
      (var.gcp_folder_id != null && var.gcp_organization_id == null)
    )
    error_message = "Set exactly one of gcp_organization_id or gcp_folder_id."
  }
}

variable "gcp_region" {
  description = "Default region for later platform resources."
  type        = string
  default     = "europe-west3"
}

variable "gcp_zone" {
  description = "Default zone for later compute resources."
  type        = string
  default     = "europe-west3-a"
}

variable "platform_operator_label" {
  description = "GCP-compatible operator label value, for example your-researcher-handle."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9_-]{1,63}$", var.platform_operator_label))
    error_message = "platform_operator_label must contain only lowercase letters, digits, underscores, or hyphens."
  }
}

variable "lab_owner_label" {
  description = "GCP-compatible owner label value applied to platform resources."
  type        = string
  default     = "unknown"

  validation {
    condition     = can(regex("^[a-z0-9_-]{1,63}$", var.lab_owner_label))
    error_message = "lab_owner_label must contain only lowercase letters, digits, underscores, or hyphens."
  }
}

variable "active_lab_limit" {
  description = "Maximum number of simultaneously active labs."
  type        = number
  default     = 1

  validation {
    condition     = var.active_lab_limit >= 1 && var.active_lab_limit <= 2
    error_message = "active_lab_limit must be 1 or 2."
  }
}

variable "budget_eur_equivalent" {
  description = "Monthly GCP budget-alert amount in EUR. This is not a hard spending cap."
  type        = number
  default     = 245

  validation {
    condition     = var.budget_eur_equivalent > 0
    error_message = "budget_eur_equivalent must be greater than zero."
  }
}

variable "credit_expiry_date" {
  description = "Operator-supplied credit expiry date in YYYY-MM-DD format."
  type        = string

  validation {
    condition     = can(regex("^20[0-9]{2}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01])$", var.credit_expiry_date))
    error_message = "credit_expiry_date must use YYYY-MM-DD format."
  }
}

variable "vpn_allowed_static_cidrs" {
  description = "WireGuard UDP/51820 ingress source CIDRs; each entry must be an operator-approved static /32."
  type        = list(string)
  default     = []
  sensitive   = true

  validation {
    condition = alltrue([
      for cidr in var.vpn_allowed_static_cidrs :
      can(cidrhost(cidr, 0)) && can(regex("/32$", cidr))
    ])
    error_message = "vpn_allowed_static_cidrs entries must be valid IPv4 /32 CIDRs."
  }
}

variable "bbr_operator_principal" {
  description = "Operator principal granted IAP tunnel access and OS Login on the bastion."
  type        = string
  default     = "user:your-contact@example.com"
}

variable "bbr_operator_wg_public_key" {
  description = "Operator WireGuard public key. Public material only. Terraform reads this value and embeds it directly into the bastion bootstrap script. The operator's private key never enters Terraform."
  type        = string
  sensitive   = true

  validation {
    condition = can(regex(
      "^[A-Za-z0-9+/]{43}=$",
      var.bbr_operator_wg_public_key
    ))
    error_message = "bbr_operator_wg_public_key must be a 44-character base64 WireGuard public key ending in '='."
  }
}
