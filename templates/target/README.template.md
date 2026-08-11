# <Target name>

## Target

- **Target ID:** `<target-id>`
- **Program:** `<HackerOne program name and URL>`
- **Assets:** `<authorized applications, repositories, hosts, or packages>`

## Scope

Describe the in-scope assets, explicit exclusions, testing constraints, and the
date on which the program policy was last reviewed. The target-specific rules
belong in [`contract.yaml`](contract.yaml), which inherits the authoritative
repository contract from [`OPEN_CONTRACT.yaml`](../../OPEN_CONTRACT.yaml).

## Status

- **Lifecycle:** `<active | paused | parked | candidate | archived>`
- **Current focus:** `<short summary>`
- **Last reviewed:** `<YYYY-MM-DD>`

Add `STATE.md` when lifecycle context or an unblock condition must be recorded.

## Attacker model

- **Attacker access:** `<unauthenticated, authenticated, local app, supply-chain, …>`
- **Required preconditions:** `<preconditions>`
- **Victim action:** `<none or exact required action>`
- **Claimed security boundary:** `<boundary being tested>`

## Canonical state

- [`findings-manifest.json`](findings-manifest.json) — finding identity,
  qualification, evidence, severity, research state, and closure.
- [`pre_scan.yaml`](pre_scan.yaml) — current policy and asset-fingerprint
  snapshot.
- [`contract.yaml`](contract.yaml) — target scope, authorization, and overrides
  to [`OPEN_CONTRACT.yaml`](../../OPEN_CONTRACT.yaml).
