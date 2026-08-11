---
source_type: discovery-index
last_updated: 2026-07-22
priority: P2
reliability: medium
---

# HackerSignal — handle carefully (discovery layer, NOT training corpus)

## What it is

A large-scale, multi-source dataset linking **hacker-community discourse to the CVE lifecycle**:
forum/exploit/advisory/fix-commit text stitched together across a 36-year window. Extremely useful as
a **source-discovery / retrieval map** — it tells you *where* to look and how sources connect — but
its governance forbids using it as an unrestricted skill-training corpus.

## Concrete endpoints / URLs

- **Paper:** `https://arxiv.org/abs/2605.03158` — "HackerSignal: A Large-Scale Multi-Source Dataset
  Linking Hacker Community Discourse to the CVE Vulnerability Lifecycle".
- **Code:** `https://github.com/BenAmpel/hackersignal`.
- **Data:** HuggingFace Hub (governed release; source-specific access modes).

## What it adds beyond HackerOne

- **Cross-source CVE linkage** — connects hacker discourse ↔ exploit DBs ↔ advisories ↔ fix commits;
  a ready-made *map* from a CVE to every place it's discussed.
- **Scale/coverage** — ~7.45M deduplicated docs from 64 source identifiers across 8 layers (ExploitDB,
  0day.today, Packet Storm, ZeroScience, Vulnerability-Lab + GitHub Advisory, CISA KEV, HackerOne,
  CVEfixes). Use it to **discover which sources exist** for a given CWE/CVE, then go to the primary.
- **Temporal splits** — prospective (later-date) evaluation design we can mirror for held-out.

## Filter criteria for our use-case

- **Use as a discovery/retrieval benchmark and source index — not as training data.**
- When it links a CVE to a primary source (advisory, fix commit), **fetch the primary source
  directly** (GHSA/OSV/MoreFixes/tracker) and ingest *that* under its own license.
- Never route the exploit-DB text (ExploitDB/0day.today) into skill-training; treat as lab-only.

## License notes

- **Governed public release, academic + defensive use only.** Explicitly **prohibits fine-tuning
  exploit models.** CVE links are **metadata-derived, not expert-adjudicated** — do not treat a
  HackerSignal CVE↔doc link as ground truth. Respect the HuggingFace access modes and paper terms.

## Risks / caveats

- **Governance risk** — misuse (training an offensive model) violates its terms; keep it out of the
  training path entirely.
- **Unadjudicated links** — the CVE↔discourse mapping is heuristic; verify against primary sources.
- **Exploit-archive content** (ExploitDB/0day.today/Packet Storm) is offensive payload data → belongs
  in the **quarantined, lab-only** enrichment bucket (P2), if used at all.

## Concrete next steps

- **First use:** as a **retrieval index** to expand coverage of an existing skill's CVEs — "given
  CWE-918, which advisories/exploits/commits exist?" — then pull primaries.
- **Wave point:** cross-cutting discovery aid; not a wave deliverable. Keep quarantined.

## Honest ledger

- **Verified (web):** HackerSignal paper (arXiv 2605.03158), repo `BenAmpel/hackersignal`,
  HuggingFace release, academic/defensive-only governance, ~7.45M docs / 64 sources, no-fine-tune-
  exploit-models clause, metadata-derived CVE links.
- **Position (this doc):** the "discovery-not-training" classification is José's brief's guidance,
  reinforced here as a hard boundary.
