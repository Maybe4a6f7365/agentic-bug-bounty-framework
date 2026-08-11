# ADR-0007 — Cost and TTL model

## Status

Accepted, 2026-07-25.

## Context

The platform runs on the lab owner's GCP promotional credit.
The current rest credit at Phase 0 time is 245 EUR (see
the lab owner's manual statement, 2026-07-25). The credit
expires 2026-09-27 (62 days from Phase 0). The platform
must enforce a hard cap, a per-lab cap, a per-cycle cap,
and a forced-teardown deadline.

## Decision

### Hard cap

`BUDGET_EUR_EQUIVALENT` is the hard cap for the entire
platform, not per-lab. The lab owner supplies this value at
Phase 1. The default is the lab owner's rest credit at
Phase 1 creation time. The platform creates a GCP billing
budget equal to this value, with alerts at 25 %, 50 %, 75
%, 90 %, and 100 % of the cap.

The platform also enforces an internal stop cap of 120 EUR
as a safety net, regardless of `BUDGET_EUR_EQUIVALENT`.

### Per-lab cap

Every lab pack declares a `cost_limits` object. The control
plane rejects `bbr create` if the sum of `per_lab_eur_estimate`
across active labs plus the platform's reserved overhead
exceeds `BUDGET_EUR_EQUIVALENT - safety_margin`. The
`safety_margin` is 50 % of the cap by default.

### Per-cycle cap

Every lab pack declares a `per_cycle_eur_limit`. The control
plane projects cost per cycle from the pack's `cost_limits`,
the active lab's `ttl`, and the platform's hourly overhead.
If the projection exceeds `per_cycle_eur_limit`, `bbr
create` is rejected.

### Forced-teardown deadline

The lab owner supplies `CREDIT_EXPIRY_DATE`. The platform
schedules a forced teardown at
`CREDIT_EXPIRY_DATE - 48 hours`. The teardown is recorded
as an automatic state transition.

### TTL

Every lab pack declares a `ttl.max_lifetime`. The control
plane schedules a teardown at
`<lab-created-at> + ttl.max_lifetime`. A second TTL,
`ttl.idle_timeout`, schedules a stop (not destroy) at the
configured idle threshold.

### Cost re-check at every phase

Every `notes/PHASE-N-REPORT.md` includes:

- actual uptime since last gate;
- projected total cost at current burn rate;
- whether the projection is still under the 120 EUR internal
  cap;
- days remaining until the forced-teardown deadline;
- whether the daily 02:00 Europe/Berlin stop is still
  active.

### Out-of-scope costs

- The lab owner's workstation. The WireGuard client key is
  generated locally; the workstation itself is not in GCP.
- Any HackerOne target or production system. The platform is
  forbidden from contacting any such destination.

## Consequences

- The lab owner can predict the cost of the platform from
  the platform's report, not from a third-party tool.
- The platform never spends more than 120 EUR (the internal
  safety cap), even if `BUDGET_EUR_EQUIVALENT` is higher.
- A lab that exceeds its TTL is destroyed automatically.
- The credit expiry is a hard wall.

## Alternatives considered

- **No internal cap; rely on the GCP budget.** Rejected
  because GCP budgets are alerts, not hard stops, and a
  runaway lab could spend the entire credit before the
  operator noticed.
- **Per-hour rate limiting.** Considered but rejected
  because the active-lab cap, the TTL, and the internal
  safety cap are sufficient.
- **Operator-supplied cap override at run-time.** Rejected
  because the cap is bound to the credit, which is fixed
  at Phase 1 creation.