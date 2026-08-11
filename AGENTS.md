# Repository Guidelines

This is the public, scrubbed version of an internal bug-bounty research
framework. It contains the methodology, skills, tooling, lab plumbing, and
document templates you need to build and run a multi-target
vulnerability-research setup. Project data, including concrete targets,
findings, evidence, and run logs, does not live in this repo. That data
lives in a separate, private workspace and is never committed here.

## Project structure and module organization

The repo is framework-first, not target-first. Concretely.

- `skills/` contains modular, reusable research skills. Each skill is a
  self-contained playbook with a `SKILL.md`, optional `references/`, and
  scripts.
- `tools/` contains shell and Python utilities that validate manifests,
  regenerate rollups, and run the daily quality loop.
- `templates/` contains copy-ready scaffolding, target contracts, finding
  manifests, and agent personas, for spinning up a new target workspace.
- `tests/` contains shell and Python validators for the manifests and the
  run state. These are the repo's tests.
- `version-tracker/` contains an AI-friendly schema reference and a small
  SQLite pipeline for tracking program scope, version changes, and asset
  drift.
- `platform/bugbounty-range/` contains a reproducible GCP-based
  dynamic-testing environment, an Android emulator or a vulnerable web
  app, for proving PoCs end to end without touching production.
- `labs/` contains sample lab walkthroughs that demonstrate the
  framework's flow on generic targets.
- `setup/` contains operator onboarding scripts and `gcp-avd/` for the
  Android rig.
- `knowledge-sources/` contains curated reference corpora (advisories,
  papers, benchmarks). It never includes operator-identifying
  subscriptions.
- `docs/` contains public-friendly architecture and reference material.

## Build, test, and development commands

There is no compiled build. Run repository checks from the root. Bash and
`jq` are required. CI also uses Python with PyYAML.

```bash
./tools/validate-manifests.sh                 # validate JSON schemas and relationships
./tools/check_appendonly_yaml.sh              # detect rewritten handoff history

./tools/regenerate_readme.sh --check          # detect a stale README rollup
./tools/regenerate_readme.sh --write          # refresh that rollup
```

For the version-tracker pipeline, point the script at an explicit database
path. There is no portable default.

```bash
python3 version-tracker/scripts/current_target_assets.py \
  --db /path/to/version_tracker.db \
  --output CURRENT_TARGET_ASSETS.md \
  --check
```

## Coding style and naming conventions

Follow nearby files. Use two-space YAML indentation, consistently formatted
JSON, short Markdown sections with relative links, and quoted Bash
variables. New shell tools should use `#!/usr/bin/env bash`,
`set -euo pipefail`, `snake_case` functions and locals, and uppercase
environment constants. Use lowercase target IDs and exact manifest
finding IDs in paths, for example `targets/<id>/evidence/<FINDING-ID>/`.

## Testing guidelines

The shell validators and the framework's own test suite are the tests. Run
checks affected by your change and inspect generated diffs. Place
finding-specific tests or PoCs in `repro/<finding-id>/`. Document
prerequisites, exact commands, expected results, and negative controls.
Never describe static analysis as dynamic validation.

## Commit and pull request guidelines

Recent commits favor concise prefixes such as `research:`, `skills:`, and
`chore:`, plus scoped Conventional Commit forms like `fix(tools): ...`.
Keep each commit focused and use an imperative summary. Pull requests
should identify the target or finding, explain scope and evidence level,
list validation commands, link relevant issues or reports, and call out
regenerated files. Include screenshots only when they materially clarify
evidence or documentation changes.

## Security and configuration

Read `SECURITY-RESEARCH-POLICY.md`, `METHODOLOGY.md`, and the per-program
policy before any testing. Stay in scope and obey program headers and
rate limits. Never commit PII, tokens, cookies, raw APKs, full
decompiled trees, `.env` files, or unredacted logs. Keep sensitive local
artifacts in ignored paths. This public repo is deliberately scrubbed.

## Public cleansing: what is not here

This repo is a public stage of an internal framework. The internal
workspace retains:

- Concrete target contracts (`contract.yaml`), pre-scan files, and
  findings manifests for live programs.
- All run state, handoff ledgers, and adversarial-review outputs.
- Operator-identifying information. GCP project IDs, account handles,
  WireGuard keys, personal emails, hashed APK manifests.
- AI-council, Codex, and Claude output files, council analyses, and any
  intermediate research artifacts.

Anything in those lists belongs in the private workspace, not in this
repo. The public repo is the framework, methodology, and lab plumbing. The
private workspace is the operational reality.
