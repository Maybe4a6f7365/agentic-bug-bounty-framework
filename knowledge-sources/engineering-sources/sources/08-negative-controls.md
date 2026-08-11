---
source_type: negative-control
last_updated: 2026-07-22
priority: P1
reliability: high
---

# Invalid Reports & Negative Controls (contrastive stop-conditions)

## What it is

Curated **negatives**: reports and findings that are *not* valid vulnerabilities, and the *reasons
why*. This is the single biggest lever against the documented LLM failure mode — **over-acceptance of
invalid reports**. Structured rejection knowledge teaches the agent *stop conditions*,
false-positive avoidance, and reportability decisions.

## Concrete endpoints / URLs

- **H1 disclosed non-accepted reports** — already in the local corpus (`~/projects/h1-skills/`):
  filter `substate ∈ {N/A, Informative, Spam, Duplicate}` and mine the closing comment.
- **Study — "From Reviewers' Lens: Understanding Bug Bounty Report Invalid Reasons with LLMs"** —
  arXiv `2511.18608` (IEEE): **9,942 disclosed reports incl. 1,400 invalid**; SOTA LLMs (GPT-5,
  DeepSeek, fine-tuned RoBERTa) **over-accept**; a rejection-reason taxonomy in a RAG framework
  improves invalidity detection. (Also older: "Why Some Bug-bounty Vulnerability Reports are
  Invalid?", ESEM 2021, DOI `10.1145/3475716.3484193`.)
- **Patched revisions** — the `fixed` boundary from OSV/GHSA gives you a guaranteed-safe version =
  free negative.
- **Safe sibling endpoints** — the endpoint next to the vulnerable one that enforces the control.
- **Rejected scanner alerts** — Semgrep/CodeQL "closed as won't-fix / false-positive" and
  **security-issues-closed-as-non-security** on trackers.

## What it adds beyond HackerOne (positives)

- **Explicit rejection reasons** — why triagers said no, in their words.
- **Three independent labels** the agent must learn to separate:
  - `technically_vulnerable`
  - `program_in_scope`
  - `program_reportable`
  A finding can be technically real yet out-of-scope or below the impact threshold — the agent must
  not conflate these.

## Negative categories to tag per CWE skill

```
technically_not_vulnerable          missing_security_boundary
expected_product_behavior           theoretical_without_oracle
control_exists_elsewhere            vulnerable_third_party_but_target_not_affected
missing_attacker_control            patched_version
out_of_scope_asset                  duplicate_root_cause
prohibited_test_method              real_but_below_program_impact_threshold
```

Each per-CWE skill should carry **several** negatives spanning these categories → feeds the case
bundle's `false_positive_conditions` and `stop_conditions`.

## Filter criteria for our use-case

- Per skill, assemble ≥1 negative per major category above (esp. `expected_product_behavior`,
  `control_exists_elsewhere`, `missing_attacker_control`, `theoretical_without_oracle`).
- Pair each positive case with its **nearest safe neighbor** (patched version or sibling endpoint).
- Prefer negatives with a stated reason over bare "closed".

## License notes

- H1 disclosed content already governed by the local corpus's terms. The invalid-reason **study** is
  academic — cite it (arXiv id, authors); its taxonomy is reusable as *structure*, not verbatim data.
  Scanner/tracker closures are public but attribute the project.

## Risks / caveats

- **HackerSignal caution applies** (see file 09) — don't fine-tune exploit models on governed data.
- **Reputation bias in labels** — the study shows high-rep reporters get favorable borderline calls;
  don't learn "famous reporter ⇒ valid".
- **Reason text is terse/noisy** — normalize into the fixed category set above.
- **Negatives are underrepresented** in disclosed data — actively balance the corpus.

## Concrete next steps

- **First skill to benefit:** every existing skill gets a `false_positive_conditions` +
  `stop_conditions` block back-filled from these negatives — highest precision ROI.
- **Wave point:** Wave 4 (negatives) — the closing wave that makes the agent *decline* well.

## Honest ledger

- **Verified (web):** the 9,942/1,400 invalid-reasons study (arXiv 2511.18608) and its
  over-acceptance finding + RAG-taxonomy remedy; the ESEM 2021 predecessor exists (DOI above).
- **Design (this doc):** the 12-category negative taxonomy and 3-label split are transcribed from
  José's brief; adopt as the labeling contract.
