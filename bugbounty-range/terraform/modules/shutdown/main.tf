# Shutdown module — Phase 0.

# Phase 1+ will create:
#   google_compute_resource_policy.daily_stop
#     instance_schedule_policy with time_zone "Europe/Berlin"
#     and a schedule that stops the instance at 02:00 each
#     day. No automatic start is configured.
# No active resource definitions in Phase 0.

output "policy_self_link" {
  description = "Phase 0 stub."
  value       = null
}