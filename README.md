# agentic-bug-bounty-framework

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Shell: bash](https://img.shields.io/badge/Shell-bash-4EAA25?logo=gnubash&logoColor=white)](https://www.gnu.org/software/bash/)
[![Terraform](https://img.shields.io/badge/Terraform-1.x-7B42BC?logo=terraform&logoColor=white)](https://www.terraform.io/)
[![Tests: pytest](https://img.shields.io/badge/Tests-pytest-0A9EDC?logo=pytest&logoColor=white)](https://docs.pytest.org/)

A multi-target, agentic bug-bounty research framework. Modular skills,
dynamic-PoC validation, a reproducible GCP-based lab, and a code-quality
loop that keeps the repo honest. Used in active bug-bounty work. Project
data lives in a separate private workspace.

## What this is

A working framework for taking a vulnerability hypothesis from observation
to report-ready, with reproducible PoCs and source attribution. The core
ideas in short form:

- Evidence-first, source-of-truth explicit. Every finding lives in a
  canonical manifest (`findings-manifest.json`). Every change appends to a
  revision history. No silent rewrites.
- Multi-target, low ceremony. A new target is a copy of
  `templates/target/` and a fresh `contract.yaml`. Discovery is
  structural: any directory with a `findings-manifest.json` is a target.
- Deterministic handoff. Run state is append-only. Adversarial reviews,
  decisions, and external events are recorded with byte-stable headers so
  reviewers can see what changed.
- Generatable views. Rollups, indices, and outcome summaries are derived
  from canonical sources. The validators detect drift.

The framework is agentic because most of the loop is run by AI agents
that read canonical inputs and write canonical outputs. The skills in
`skills/` are reusable across targets and across engagements.

## The loop

A target engagement runs through a fixed sequence of stages. Each stage
has a gate. You cannot skip gates, and you cannot lie about passing them.

| Stage | What it does | Where it lives |
|---|---|---|
| 1. Scope and policy qualification | Pull the live program policy, parse scope, rate limits, safe harbor. Reject non-qualifying targets. | `skills/scope-policy-qualification/` |
| 2. Recon | Host-graph, source-map, dependency walk, asset fingerprint. | `skills/recon/` |
| 3. Class-driven hunting | Pick a vulnerability class, run the matching hunter, surface candidates. | `skills/<class>-hunter/` |
| 4. Duplicate preflight | Cross-check public Hacktivity, GitHub Security Lab, Project Zero, and the framework's own manifests. | `skills/duplicate-preflight/` |
| 5. Dynamic PoC validation | Drive a real PoC against the target, end to end, with negative controls. | `skills/dynamic-poc-validation/` |
| 6. Adversarial review | An independent reviewer (different model family, different context, different framing) attempts disproof. | `skills/break-assumptions/` |
| 7. Manifest promotion | Append-only record of the qualified finding with full provenance. | `templates/target/findings-manifest.template.json` |
| 8. Submission | Final report, sanitized evidence bundle, post-submission triage ledger. | `version-tracker/`, target-local `submit/` |

The agent's job is to read canonical inputs, write canonical outputs,
and never lie about whether a gate passed. The framework's job is to make
that honest.

## Skills in the framework

Each skill is a self-contained playbook with a `SKILL.md`, optional
references, and scripts. The skills are organized by what they do.

Discovery and qualification:

- `skills/scope-policy-qualification/` reads a live program policy and
  decides whether the target is worth an investment.
- `skills/recon/` does host-graph, source-map, and dependency walk.
- `skills/duplicate-preflight/` runs a public Hacktivity, GitHub Security
  Lab, and Project Zero check before any new candidate is qualified.

Class-driven hunters (one per class):

- `skills/auth-bypass-hunter/`
- `skills/access-control-hunter/`
- `skills/idor-hunter/`
- `skills/sqli-hunter/`
- `skills/xss-reflected-hunter/`, `skills/xss-stored-hunter/`
- `skills/ssrf-hunter/`
- `skills/rce-chaining/`
- `skills/path-traversal-hunter/`
- `skills/privesc-hunter/`
- `skills/info-disclosure-hunter/`
- `skills/business-logic-hunter/`

Validation and review:

- `skills/dynamic-poc-validation/` builds a PoC against a target the
  agent owns, with a negative control next to the positive claim.
- `skills/patch-review-hunter/` reads a real CVE or GHSA, joins the
  patch diff to a candidate, and reasons about exposure.
- `skills/break-assumptions/` is the adversarial-review function. It
  asks "what would have to be true for this to be intended behavior?"
- `skills/case-bundle-builder/` joins researcher evidence with
  engineering evidence, patch diffs, and maintainer discussion.

## The lab

A framework without a way to run a PoC is a framework full of fantasies.
The lab is a reproducible GCP-based environment that lets you prove
impact without touching production.

- `platform/bugbounty-range/` is a multi-package Terraform stack that
  provisions an isolated network, a bastion, a build VM, and a target
  VM. The target VM is intentionally vulnerable. Bring it up, run the
  PoC, tear it down. The same code that tears down the lab unsubscribes
  the WireGuard peer and rotates the SSH keys.
- `setup/gcp-avd/` is the bring-up recipe for a cloud-hosted Android
  emulator rig with Frida and Caido. It is written as a deploy-your-own
  recipe; every concrete identifier is a placeholder.

## Code-quality loop

The repo is short on ceremony and long on enforcement. The validators
are the tests.

- `tools/validate-manifests.sh` checks JSON schemas, relationships,
  writeup-path resolution, and the canonical duplicate-preflight shape.
- `tools/check_appendonly_yaml.sh` detects rewrites of handoff headers.
- `tools/regenerate_readme.sh` regenerates the README rollup from
  canonical sources; `--check` flags stale rollups.

Generated views are disposable. Open the owner, fix it, regenerate, and
commit.

## Layout

```
agentic-bug-bounty-framework/
├── skills/                   # modular research skills (12 class hunters + 7 cross-cutting)
├── tools/                    # validators and regenerators
├── templates/                # copy-ready scaffolding for target contracts, manifests, personas
├── tests/                    # unit and acceptance tests (pytest)
├── platform/
│   └── bugbounty-range/      # reproducible GCP-based dynamic-testing environment
├── labs/                     # sample lab walkthroughs
├── setup/
│   └── gcp-avd/              # cloud-hosted Android emulator rig (deploy-your-own)
├── version-tracker/          # schema reference and small pipeline for program scope and version drift
├── knowledge-sources/        # curated reference corpora (advisories, papers, benchmarks)
├── docs/                     # public-friendly architecture and reference material
├── METHODOLOGY.md            # the end-to-end methodology
├── SECURITY-RESEARCH-POLICY.md  # hard rules: scope, safe harbor, traffic discipline
├── CONTRACT.md               # the shared machine contract between agents and reviewers
├── AGENTS.md                 # repository guidelines
├── LICENSE                   # MIT
└── README.md                 # this file
```

## Quick start

```bash
git clone https://github.com/Maybe4a6f7365/agentic-bug-bounty-framework.git
cd agentic-bug-bounty-framework

# Spin up a new target workspace
cp -r templates/target targets/<platform-handle>
${EDITOR:-vi} targets/<platform-handle>/contract.yaml

# Validate the manifest structurally
./tools/validate-manifests.sh

# Run the test suite
pytest tests/
```

## What is not here, and why

This is a public, scrubbed stage of an internal framework. The internal
workspace retains:

- Concrete target contracts, pre-scan files, and finding manifests for
  live programs.
- Run state, handoff ledgers, and adversarial-review outputs.
- Operator-identifying information: GCP project IDs, account handles,
  WireGuard keys, personal emails, hashed APK manifests.
- AI-council, Codex, and Claude output files, council analyses, and
  any intermediate research artifacts.

The split is deliberate. Operator privacy, active-research isolation,
and program safe-harbor rules all require that concrete project data
stays out of a public repo.

## License

MIT. See [`LICENSE`](./LICENSE).
