---
source_type: contrastive-code-dataset
last_updated: 2026-07-22
priority: P1
reliability: high
---

# PrimeVul + MegaVul (contrastive vulnerable/benign code)

## What it is

Two large **function-level** C/C++ (MegaVul also Java) datasets pairing vulnerable functions with
their fixed/benign counterparts, with CWE/CVE metadata. Not primarily for building web-bounty skills —
their value is **contrastive/negative-control training**: teaching the agent to distinguish
*actually-vulnerable* from *security-adjacent*, *patched*, and *superficially-similar-but-safe* code.

## Concrete endpoints / URLs

- **PrimeVul:** `https://github.com/DLVulDet/PrimeVul` — ~**6,968 vulnerable + 228,800 fixed**
  function-level C/C++ examples, **140+ CWEs**, with de-noising/de-dup filtering rules and paired
  CWE/CVE metadata.
- **MegaVul:** paper `https://arxiv.org/abs/2406.12415` — **17,380 vulnerable + 322,168
  non-vulnerable** functions from **9,019 commits** (C/C++, later revisions add Java), extracted with
  code-parsing tools and de-duplicated across CVEs. Data crawled from CVE DB + 28 git hosts.

## What it adds beyond HackerOne

- **Massive benign baseline** — the ~40:1 benign:vulnerable ratio is exactly the real-world class
  imbalance the agent must survive without over-flagging.
- **Paired vulnerable↔fixed functions** — direct `negative_control` and `neighboring_safe_behavior`
  material for the case bundle.
- **Breadth of CWEs (140+)** far beyond the H1 corpus's practical spread.

## Filter criteria for our use-case

- Use **only** for the contrastive/false-positive-avoidance layer, **not** as primary skill source.
- For memory-safety-adjacent skills (deserialization, parser confusion) sample the relevant CWEs.
- Prefer **paired** examples (vuln + its fix) over unpaired singletons.
- Deprioritize for web/API skills — isolated function snippets lack request/trust-boundary context;
  use MoreFixes (repo diffs) there instead.

## License notes

- Both are research datasets of upstream OSS functions; **underlying code carries upstream licenses**.
  Cite the dataset paper + repo. Use extracted functions for evaluation/contrastive signals; avoid
  redistributing large verbatim code without honoring source licenses.

## Risks / caveats

- **C/C++ (+ some Java) only** — limited transfer to our JS/Python/API bounty surface.
- **Function-level snippets lose context** — no request path, no auth boundary, no reachability; a
  function can look vulnerable in isolation yet be unreachable in practice (over-flag risk).
- **Label noise** — even with de-dup/de-noise rules, mislabeled pairs remain; sample-audit.

## Concrete next steps

- **First skill to benefit:** CWE-502 (deserialization) and CWE-611 (XXE) contrastive negatives, plus
  a shared **"is-this-actually-vulnerable" gate** used across all skills.
- **Wave point:** Wave 4 (negatives/contrastive), not the ground-truth waves.

## Honest ledger

- **Verified (web):** PrimeVul repo `DLVulDet/PrimeVul` with ~6,968 vuln / 228,800 fixed / 140+ CWEs;
  MegaVul arXiv 2406.12415 with 17,380 vuln / 322,168 non-vuln / 9,019 commits.
- **Training knowledge (medium):** exact license terms per dataset — confirm each repo's LICENSE
  before redistribution.
