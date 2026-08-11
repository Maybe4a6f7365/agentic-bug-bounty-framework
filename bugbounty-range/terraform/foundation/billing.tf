# GCP budgets are alerts, not hard spending stops. Runtime enforcement
# remains the responsibility of the platform lifecycle and stop cap.
resource "google_billing_budget" "platform" {
  provider = google.billing

  billing_account = var.billing_account_id
  display_name    = "BugBountyRange monthly alert budget"

  amount {
    specified_amount {
      currency_code = "EUR"
      units         = tostring(floor(var.budget_eur_equivalent))
    }
  }

  threshold_rules {
    threshold_percent = 0.25
    spend_basis       = "CURRENT_SPEND"
  }

  threshold_rules {
    threshold_percent = 0.50
    spend_basis       = "CURRENT_SPEND"
  }

  threshold_rules {
    threshold_percent = 0.75
    spend_basis       = "CURRENT_SPEND"
  }

  threshold_rules {
    threshold_percent = 0.90
    spend_basis       = "CURRENT_SPEND"
  }

  threshold_rules {
    threshold_percent = 1.00
    spend_basis       = "CURRENT_SPEND"
  }

  threshold_rules {
    threshold_percent = 1.00
    spend_basis       = "FORECASTED_SPEND"
  }

  budget_filter {
    projects = ["projects/${google_project.bbr.number}"]
  }

  depends_on = [
    google_project_service.foundation["billingbudgets.googleapis.com"],
    google_project_service.foundation["cloudbilling.googleapis.com"],
  ]
}
