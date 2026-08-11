---
source_type: plan
last_updated: 2026-07-22
priority: P0
reliability: high
---

# Ingestion Plan — 4 Waves

Turns the scouted sources into an ordered, budgeted build. Each wave produces **case bundles**
(schema: [`CASE-BUNDLE-SCHEMA.md`](./CASE-BUNDLE-SCHEMA.md)) and feeds the four derivation tasks
(invariant extraction → contrastive analysis → operationalization → held-out eval). Waves 1–2 build
skills, Wave 3 evaluates them, Wave 4 makes them decline correctly. Estimates are order-of-magnitude
engineering effort, not calendar promises.

## Sequencing principle

GHSA/OSV first (it is the version/CWE spine every other source joins to), then diffs (MoreFixes +
trackers), then engagement knowledge, then executable eval, then negatives. Do **not** ingest
benchmarks (Wave 3) into the training path — they are held-out only.

---

## Wave 1 — Engineering ground truth  *(build spine + first bundles)*

| Step | Source | Action | Est. |
|---|---|---|---|
| 1.1 | **GHSA + OSV** ([02](./sources/02-ghsa-osv.md)) | Clone `github/advisory-database`; back-fill `introduced`/`fixed` + CWE for every existing skill's CVEs | 0.5–1 d |
| 1.2 | **MoreFixes v4** ([03](./sources/03-morefixes.md)) | Load Zenodo `20776007` PG dump; filter `score≥65` + our 7 languages + our CWEs; extract patch motifs | 1–2 d |
| 1.3 | **Issue trackers** ([01](./sources/01-public-issue-trackers.md)) | For top motifs, pull the tracker event-graph (maintainer Qs, tests) for 20–40 exemplar bugs | 1–2 d |
| 1.4 | — | Assemble **~50 seed case bundles** (5 per existing skill), human-review the ★ fields | 1–2 d |

**Exit criterion:** ≥50 bundles with non-null `patch_diff`, `changed_tests`, and version boundaries.

## Wave 2 — Engagement knowledge  *(design/business-logic skills)*

| Step | Source | Action | Est. |
|---|---|---|---|
| 2.1 | **Audit reports** ([06](./sources/06-audit-reports.md)) | Index Trail of Bits + Cure53 + OSTIF repos; extract threat-model/invariant tables (reference-only) | 1–2 d |
| 2.2 | **Real-finding streams** ([07](./sources/07-real-finding-streams.md)) | Pull Assetnote/PortSwigger/Project Zero chains + **Huntr AI/ML** disclosures; CERT/CC archive | 1–2 d |
| 2.3 | — | Draft a **business-logic / trust-boundary** skill + a **new AI/ML-supply-chain** skill from Huntr | 2–3 d |

**Exit criterion:** ≥2 new skills seeded with invariants + applicability signals (not payloads).

## Wave 3 — Executable validation  *(held-out eval harness)*

| Step | Source | Action | Est. |
|---|---|---|---|
| 3.1 | **CVE-Bench** ([05](./sources/05-reproducible-benchmarks.md)) | Stand up Docker harness; wire as standing web-skill regression eval | 1 d |
| 3.2 | **PatchEval** (Go/JS/Python 230-subset) | Reverse `vul-run.sh`=positive / `fix-run.sh`=negative / unit=constraint into a detection oracle | 1–2 d (≈460 GB disk) |
| 3.3 | **Vul4J / ARVO / CrossCommitVuln** | Add Java-class eval (Vul4J), native/parser (ARVO), multi-commit stop-condition test (CrossCommit) | 1–2 d |

**Exit criterion:** every skill has ≥1 executable held-out oracle it did **not** train on.

## Wave 4 — Negatives  *(precision / decline correctly)*

| Step | Source | Action | Est. |
|---|---|---|---|
| 4.1 | **H1 N/A/Informative/Spam** ([08](./sources/08-negative-controls.md)) | Mine local corpus closings; tag into the 12-category negative taxonomy | 1 d |
| 4.2 | **Patched revisions + safe siblings** | For each positive bundle, attach `negative_control` (fixed version) + `neighboring_safe_behavior` | 1 d |
| 4.3 | **Rejected scanner alerts / PrimeVul-MegaVul** ([04](./sources/04-primevul-megavul.md)) | Add contrastive benign functions + won't-fix closures | 1 d |
| 4.4 | — | Back-fill `false_positive_conditions` + `stop_conditions` into every skill | 1 d |

**Exit criterion:** every skill carries ≥1 negative per major category and the 3-label triage split.

---

## Cross-cutting: HackerSignal ([09](./sources/09-hackersignal.md))
Use as a **discovery index only** to expand coverage ("which sources exist for this CVE?"), then fetch
primaries. **Never** route its exploit-archive text into training. Quarantined, lab-only.

## Provenance discipline (all waves)
Every bundle records `sources`, `source_versions`, `licenses`, `retrieved_at`, `content_hashes`,
`human_reviewer`. Keep upstream code licenses per commit; extract the *motif/invariant*, not verbatim
licensed code. No PII, no embargoed content, no offensive-model fine-tuning.
