# packs/smoke-compose — driver-genericity proof

This pack proves that the `compose_vm` driver is generic. It
deploys a small, deliberately non-vulnerable two-service
Compose topology and exercises every required driver
capability.

The pack has no WordPress code. It has no WordPress-
specific configuration. It validates against
`schemas/lab-pack.schema.json` without any change to the
platform core.

## Topology

Two services running on two nodes:

- `redis-1` — a Redis instance with deterministic fixture
  data.
- `counter-1` — a small Python HTTP service that reads the
  Redis key and exposes `/value`.

The two nodes form a dependency chain: `counter-1` waits
for `redis-1` to be reachable before serving requests.

## Scenarios

A single deterministic scenario that requests
`/value` on `counter-1` and asserts the response is
`{"value": "smoke-compose-baseline"}`.

## Snapshots

A baseline snapshot is taken after `bbr verify` succeeds.
The scenario is then re-run against the restored snapshot to
prove deterministic restoration.