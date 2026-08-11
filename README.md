# agentic-bug-bounty-framework

A multi-target, agentic bug-bounty research framework. Modular skills, dynamic
PoC validation, a reproducible cloud lab, and a code-quality loop that keeps
the repo honest. Used in active bug-bounty research; project data stays
private.

## What this is, in plain language

You point the framework at a bug-bounty program on HackerOne or Bugcrowd. It
runs a structured loop:

1. Pull the live program policy and parse scope, rate limits, safe harbor.
2. Decide which targets are worth an investment.
3. Run a discovery pass with the recon skills.
4. Pick a vulnerability class, run the matching hunter, and qualify
   candidates against the framework's mandatory gates.
5. Build a reproducible PoC, end to end, on a lab you control.
6. Ship a clean report.

It is agentic because most of that loop is run by AI agents that read
canonical inputs and write to canonical outputs. It is a framework because
the skills, schemas, and validators are reusable. It is bug-bounty because
the contracts, headers, and pace are tuned for paid programs, not
consulting.

## What you can read here

| Layer | What you get |
|---|---|
| `METHODOLOGY.md` | The end-to-end methodology: target selection, qualification gates, severity, decision envelopes |
| `SECURITY-RESEARCH-POLICY.md` | Hard rules: scope, safe harbor, traffic discipline, no PII, no destructiveness |
| `CONTRACT.md` and `OPEN_CONTRACT.yaml` | The shared machine contract between agents and reviewers |
| `skills/` | Modular, pluggable research skills. Recon, dynamic-PoC validation, scope-policy qualification, case-bundle builder, patch-review hunter, more |
| `tools/` | Validators and regenerators that keep the repo honest |
| `platform/bugbounty-range/` | A reproducible GCP-based dynamic-testing environment for PoC qualification |
| `labs/` | Sample lab walkthroughs showing the framework's flow on generic targets |
| `setup/gcp-avd/` | Operator onboarding for a cloud-hosted Android emulator rig |
| `version-tracker/` | AI-friendly schema reference and a small pipeline that tracks program scope and version drift |
| `knowledge-sources/` | Curated reference corpora (advisories, papers, benchmarks) |
| `docs/` | Public-friendly architecture and reference material |

## How it is used

This framework has been used to identify and qualify new vulnerabilities in
third-party systems on paid programs. The full operational record lives in
a private workspace that is not mirrored into this repo. That split is
deliberate, for three reasons.

1. Operator privacy. The framework's deployment uses an
   operator-controlled GCP project, identity, and email alias. None of
   that is part of this public repo.
2. Active research isolation. Project data is time-sensitive. Program
   scope changes, bounty windows close, embargoes lift. Keeping the
   public repo slim avoids leaking the direction of ongoing research
   through file names, file sizes, or commit timestamps.
3. Program boundaries. Several live programs have explicit safe-harbor
   rules that forbid public disclosure of pre-fix findings. The public
   repo stays clean by design.

## What is not here

- No concrete targets. No `targets/<real-program>/` directories.
- No findings, no PoCs against live systems. No `findings/`,
  `evidence/`, `repro/`, or `submit/` content for any specific program.
- No run state. No `runs/`, no handoff ledgers, no checkpoint markdown.
- No AI-council, Codex, or Claude output files. Self-review reports,
  decision envelopes, and consolidation runs are operator-side artifacts.
- No operator identifiers. No HackerOne handles, GCP project IDs,
  email addresses, phone numbers, or WireGuard keys. The `setup/gcp-avd/`
  docs are written as a deploy-your-own recipe with `<your-...>`
  placeholders.
- No scraped hacktivity dumps, no raw HTML snapshots of in-scope assets,
  no CSV mining of public disclosure feeds.

## Quick start

```bash
git clone https://github.com/Maybe4a6f7365/agentic-bug-bounty-framework.git
cd agentic-bug-bounty-framework

# Spin up a new target workspace
cp -r templates/target targets/<platform-handle>
${EDITOR:-vi} targets/<platform-handle>/contract.yaml

# Verify the manifest structurally
./tools/validate-manifests.sh
```

## Repo layout

| Path | Purpose |
|---|---|
| `skills/` | Reusable research skills. Each is a self-contained playbook with a `SKILL.md`, optional `references/`, and scripts |
| `tools/` | Shell and Python quality-control utilities |
| `templates/` | Copy-ready scaffolding for target contracts, finding manifests, agent personas |
| `tests/` | Shell and Python validators |
| `platform/bugbounty-range/` | Reproducible GCP-based dynamic-testing environment |
| `labs/` | Sample lab walkthroughs |
| `setup/gcp-avd/` | Operator onboarding for a cloud-hosted Android emulator rig |
| `version-tracker/` | Schema reference and a small pipeline for tracking program scope and version drift |
| `knowledge-sources/` | Curated reference corpora |
| `docs/` | Public-friendly architecture and reference material |

## License

MIT. See [`LICENSE`](./LICENSE).
