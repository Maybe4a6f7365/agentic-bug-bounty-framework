# terraform/modules/shutdown — daily 02:00 Europe/Berlin stop schedule

Attaches a daily stop schedule to a Compute Engine instance
resource policy. The schedule stops the instance at 02:00
Europe/Berlin each day. The platform does NOT auto-start
instances.

The module is generic. The schedule time is configurable.

Phase 1+ will create the resource policy and attach it to
the target instance. No resource is enabled in Phase 0.