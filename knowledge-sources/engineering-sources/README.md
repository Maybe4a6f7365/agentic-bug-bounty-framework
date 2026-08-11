---
source_type: index
last_updated: 2026-07-22
priority: P0
reliability: high
---

# Engineering Sources — the next source wave

The H1 disclosed-reports corpus (`~/projects/h1-skills/`) already covers the **attacker's
narrative**: discovery path, reproduction, impact argument, bounty triage. This sub-area scouts the
sources that fill what H1 reports *do not* contain:

- the exact **vulnerable code** and developer **patch**;
- **regression tests** and **exploit oracles**;
- **maintainer discussion** explaining *why* the behavior was vulnerable;
- **failed hypotheses, disputed impact, and benign look-alikes**;
- **cross-project variants** of the same root cause;
- **reproducible environments** for testing the generated skill.

This is a **scouting output**, not an ingestion: endpoints and structures are documented and (where
possible) validated, but no source was bulk-fetched. It extends `knowledge-sources/` without touching
the existing `creators/`, `tools/`, `conferences/`, `blogs/`, `papers/`, `cve-trends/` files.

## Contents

| File | Purpose |
|---|---|
| [`CASE-BUNDLE-SCHEMA.md`](./CASE-BUNDLE-SCHEMA.md) | The ingestion unit: one vuln instrumented with attacker + engineering evidence + negatives. Worked example. |
| [`INGESTION-PLAN.md`](./INGESTION-PLAN.md) | 4 Waves with concrete steps, exit criteria, effort estimates. |
| [`HOLD-OUT-EVALUATION.md`](./HOLD-OUT-EVALUATION.md) | Benchmark→skill mapping + the 4 held-out axes + metrics. |
| [`INTEGRATION-UPDATE.md`](./INTEGRATION-UPDATE.md) | How this wires into the 10 existing skills + the pipeline. |
| [`templates/case-bundle.yaml`](./templates/case-bundle.yaml) | Fillable case-bundle. |
| `sources/01..09` | One file per source family (see below). |

## Source inventory & priority

| # | Source family | Priority | Reliability | Primary use |
|---|---|---|---|---|
| [01](./sources/01-public-issue-trackers.md) | Public issue trackers (Chromium, Mozilla Bugzilla, GH Security Lab) | P0 | high | maintainer discussion, tests, false starts |
| [02](./sources/02-ghsa-osv.md) | GitHub Advisory DB + OSV.dev | P0 | high | **enrichment spine** — CWE + version boundaries |
| [03](./sources/03-morefixes.md) | MoreFixes v4 (fix-commit dataset) | P0 | medium | variant extraction / patch motifs |
| [04](./sources/04-primevul-megavul.md) | PrimeVul + MegaVul | P1 | high | contrastive vulnerable/benign (C/C++/Java) |
| [05](./sources/05-reproducible-benchmarks.md) | CVE-Bench / VLoc / PatchEval / Vul4J / ARVO / CrossCommit | P0 | high | **held-out evaluation** |
| [06](./sources/06-audit-reports.md) | Trail of Bits / Cure53 / OSTIF | P0 | high | business-logic & design skills |
| [07](./sources/07-real-finding-streams.md) | Google/Meta VRP, Huntr, research labs, CERT/CC | P1 | high | non-H1 narratives, AI/ML classes |
| [08](./sources/08-negative-controls.md) | Invalid H1 / patched / safe siblings / rejected alerts | P1 | high | stop-conditions, false-positive avoidance |
| [09](./sources/09-hackersignal.md) | HackerSignal | P2 | medium | **discovery index only — not training** |

## Top priorities to ingest first (highest ROI)

1. **GHSA + OSV (02)** — the spine. Seed it first; every diff, boundary, and CWE label joins here.
   Two endpoints live-verified this session.
2. **MoreFixes v4 (03)** — cross-project patch motifs at scale = the variant-extraction engine.
   *Confirm v4 counts + `score` semantics before quoting.*
3. **Issue trackers (01)** — the maintainer discussion + regression tests that make a bundle worth
   more than an H1 report.
4. **Audit reports (06)** — the only good teacher for the business-logic/authz skill (our top ROI,
   weakest scanner coverage).
5. **Negatives (08)** — the anti-over-acceptance lever; cheap, highest precision return.

## How skills are derived (4 tasks, per the brief)

1. **Invariant extraction** — the common security invariant across reports, *not* payloads.
2. **Contrastive analysis** — vulnerable vs patched vs benign-neighbor vs rejected.
3. **Operationalization** — applicability conditions, recon signals, hypotheses, probes, control
   requests, evidence oracles, stop conditions.
4. **Held-out evaluation** — different product / framework / later date / unused source / patched.

## Guardrails

- No PII, no private contacts, no tokens. Reference-only for copyrighted audit PDFs.
- HackerSignal + exploit archives are **discovery/lab-only**, never in the training path.
- Represent evidence accurately (static vs dynamic) per repo CLAUDE.md; keep provenance + licenses.
