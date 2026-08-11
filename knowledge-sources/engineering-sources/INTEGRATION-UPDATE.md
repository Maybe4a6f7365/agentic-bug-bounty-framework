---
source_type: integration
last_updated: 2026-07-22
priority: P0
reliability: high
---

# Integration Update — wiring engineering sources into the existing pipeline

How this scouting output plugs into the **10 existing per-CWE skills** (`~/Research-Repo/skills/`),
the H1 corpus (`~/projects/h1-skills/`), and the skill-architecture council report
(`~/projects/h1-skills/council/skill-architecture-report.md`) — **without rewriting any existing
skill**. This wave *enriches* and *evaluates*; it does not replace.

## Relationship to the existing knowledge-sources

- `creators/`, `tools/`, `conferences/`, `blogs/`, `papers/`, `cve-trends/` — **unchanged**. They
  cover *who* researches and *what techniques* exist (attacker mindset + tooling).
- `engineering-sources/` (this folder) — the **ground-truth + evaluation** layer: vulnerable code,
  patches, tests, negatives, and held-out oracles. Complementary, non-overlapping.

## Per existing skill: what to back-fill

Each of the 10 CWE skills gains four new blocks, sourced as follows:

| Skill block (new) | Filled from | Source file |
|---|---|---|
| `version_boundaries` (introduced/fixed exemplars) | GHSA/OSV | [02](./sources/02-ghsa-osv.md) |
| `patch_motifs` (cross-project root-cause patterns) | MoreFixes v4 | [03](./sources/03-morefixes.md) |
| `evidence_requirements` (what triagers demand) | issue-tracker maintainer Qs | [01](./sources/01-public-issue-trackers.md) |
| `false_positive_conditions` + `stop_conditions` | invalid H1 + patched/safe siblings | [08](./sources/08-negative-controls.md) |

These map 1:1 onto the case-bundle fields, so ingestion = "emit bundles, then project bundle fields
into the skill files."

## New skills this wave enables (draft, not built here)

- **Business-logic / trust-boundary skill** — from audit reports ([06](./sources/06-audit-reports.md)).
  Highest bounty ROI, weakest scanner coverage.
- **AI/ML-supply-chain skill** — from Huntr ([07](./sources/07-real-finding-streams.md)): pickle/joblib
  RCE, unsafe model loaders, model-file path traversal, notebook escapes. Aligns with the repo's
  Anthropic/mcpb + AI targets.

## Pipeline placement (RAG vs direct vs eval)

- **Direct into skill files:** invariants, patch motifs, evidence requirements, negatives (curated,
  small, high-signal).
- **RAG store:** the bulk MoreFixes/GHSA/OSV corpus + audit-report invariant tables + lab writeups —
  retrieved at recon/hypothesis time, keyed by CWE + language + framework.
- **Eval harness (never RAG, never training):** the Wave-3 benchmarks — held-out only
  ([HOLD-OUT-EVALUATION.md](./HOLD-OUT-EVALUATION.md)).
- **Quarantine (lab-only):** HackerSignal + exploit archives — discovery/retrieval index only.

## Contract / governance alignment (repo CLAUDE.md, CONTRACT.md)

- **Evidence accuracy:** bundles carry `researcher_evidence` (may be static) separate from
  `engineering_evidence` (the patch/test) and `behavioral_model.exploit_oracle` (dynamic). Never
  present a static motif match as dynamic validation.
- **Provenance:** every bundle records sources/versions/licenses/hashes/human-reviewer — satisfies the
  "factual, evidence-backed, attributed" rule and keeps upstream code licenses intact.
- **Scope discipline:** the `triage` 3-label split (`technically_vulnerable` / `in_scope` /
  `reportable`) operationalizes the repo's "impact before severity, self-kill low-impact early".
- **Non-normative:** like all `skills/` and `knowledge-sources/` material, these files are optional
  guidance and never override the contracts or readiness gates.

## Suggested first move

Wave 1, step 1.1: clone `github/advisory-database`, back-fill `introduced`/`fixed` + CWE for the CVEs
already cited in the 10 skills. It's low-effort, license-clean (CC-BY-4.0), and immediately upgrades
every skill's "which versions are actually affected" precision — the cheapest high-value integration.
