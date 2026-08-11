---
source_type: evaluation-plan
last_updated: 2026-07-22
priority: P0
reliability: high
---

# Held-Out Evaluation

The reproducible benchmarks ([`sources/05`](./sources/05-reproducible-benchmarks.md)) exist to
**test generalization, never to train**. A skill only counts as working if it fires on cases it has
not seen. This doc maps each benchmark to the skill classes it validates and the four held-out axes.

## The four held-out axes (per José's brief)

A valid held-out case must differ from the training bundle on **at least one** axis:

1. **Different product** — same CWE, different application.
2. **Different framework** — same class, different stack.
3. **Later disclosure date** — CVE disclosed after the training cutoff (temporal split).
4. **Unused source / patched+benign version** — pulled from a source not in training, or the
   patched revision as a negative control.

Leakage guard: a benchmark used for eval must **never** contribute bundles to Wave 1/2/4.

## Benchmark → skill mapping

| Benchmark | Oracle type | Validates (skill classes) | Held-out axis it best exercises |
|---|---|---|---|
| **CVE-Bench** (40 web CVEs, Docker) | exploit success (machine-verifiable) | web app: XSS, SQLi, SSRF, auth, upload | different product; RCE-heavy (see caveat) |
| **PatchEval** (1,000; 230 Docker; Go/JS/Python) | `vul-run.sh`=+ / `fix-run.sh`=− / unit=constraint | web/API + backend across 65 CWEs | patched+benign version (fix-run = negative) |
| **Vul4J** (79 Java, PoV tests) | PoV test per vuln | deserialization, path traversal, XXE/XML, EL injection, authz, unsafe reflection | different framework (Java stacks) |
| **ARVO** (5–6k C/C++, OSS-Fuzz) | triggering input + rebuild at both revs | native parsers, memory-safety, file-format | different product; native surface |
| **CrossCommitVuln-Bench** (15 Python, multi-commit) | per-commit vs cumulative detection | multi-commit root cause / anti-"one line = vuln" | later disclosure + unused source; stop-condition |
| **VLoc / Antares** (500, localization) | file-level localization accuracy | recon: connect advisory→file | different product; localization (not exploitation) |

## Metrics per skill

- **Recall** on positive oracles (did it find the real bug?).
- **Precision / false-positive rate** on negatives (`fix-run.sh`, patched versions, benign siblings) —
  the primary guard against the documented **over-acceptance** failure mode.
- **Functionality-preserving check** (PatchEval `unit_test.sh`) where the skill proposes a fix.
- **Stop-condition correctness** (CrossCommitVuln-Bench): does it *refrain* when only one commit is
  present and the chain is incomplete?

## Reversing PatchEval into a detection oracle

PatchEval measures patching, so use it inverted:
- `vul-run.sh` passing on the unpatched tree = **positive oracle** (the bug is real & reachable).
- `fix-run.sh` passing on the patched tree = **negative control** (must NOT flag).
- `unit_test.sh` = **functionality constraint** (a proposed fix must keep these green).
- `llm.patch` = **root-cause evidence** to grade the skill's explanation against.

## Caveats that shape scoring

- **CVE-Bench over-weights RCE**, under-weights access-control / info-disclosure — our top bounty
  classes. Don't treat CVE-Bench score as the headline; weight PatchEval + Vul4J for authz/logic.
- **VLoc/Antares (2026-07-21)** measure *localization*, not exploitation — a good recon proxy, not an
  end-to-end success metric; its 290/6/147 breakdown is unconfirmed.
- **ARVO/PrimeVul are C/C++** — treat as native-surface transfer tests, low weight for web skills.
- **Disk:** PatchEval 230 × ~2 GB ≈ 460 GB; ARVO images large — budget before Wave 3.
