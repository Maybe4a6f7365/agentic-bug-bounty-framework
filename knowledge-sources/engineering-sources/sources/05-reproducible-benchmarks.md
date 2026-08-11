---
source_type: reproducible-benchmark
last_updated: 2026-07-22
priority: P0
reliability: high
---

# Reproducible Vulnerability Benchmarks (executable held-out eval)

## What it is

Benchmarks that ship **executable vulnerable/fixed environments with objective success oracles** —
run a PoC, get a machine-verifiable pass/fail. These are our **held-out evaluation harness**: we do
NOT mine them for skill content; we test whether a skill generalizes to a different product /
framework / later disclosure date. Reversed, each provides a positive oracle, a negative control, and
a functionality-preserving constraint.

## Concrete endpoints / URLs

| Benchmark | Repo / paper | Scope | Oracle |
|---|---|---|---|
| **CVE-Bench** | `github.com/uiuc-kang-lab/cve-bench` · arXiv `2503.17332` | **40 critical web CVEs** in Docker | machine-verifiable exploit success (also in `inspect_evals`) |
| **VLoc Bench** | Cisco Foundation AI "Antares" (blogs.cisco.com, released **2026-07-21**) | **500-entry** vuln-localization; brief: 500 vulns / 290 repos / 6 ecosystems / 147 CWEs | file-level localization accuracy |
| **PatchEval** | `github.com/bytedance/PatchEval` · `patcheval.github.io` | **1,000 vulns** (CVEs 2015–2025), 65 CWEs, Go/JS/Python; **230 Dockerized** (~2 GB each) | `vul-run.sh` / `fix-run.sh` / unit tests |
| **Vul4J** | `github.com/tuhh-softsec/vul4j` · MSR 2022 DOI `10.1145/3524842.3528482` | **79 Java vulns / 51 projects / 25 CWEs**, human patches + PoV tests | PoV test case per vuln |
| **ARVO** | `github.com/n132/ARVO` + `n132/ARVO-Meta` · arXiv `2408.02153` | **5,000→6,000+ C/C++ memory vulns / 250→300+ projects** (OSS-Fuzz) | triggering input + rebuild at vuln/patched revs |
| **CrossCommitVuln-Bench** | `github.com/motornomad/crosscommitvuln-bench` · arXiv `2604.21917` (AIware 2026) | **15 Python CVEs**, multi-commit root cause | per-commit vs cumulative detection |

## What it adds beyond HackerOne

- **Objective pass/fail** — replaces subjective "looks exploitable" with a runnable oracle.
- **PatchEval reversal** (the key trick):
  - `vul-run.sh` → **positive oracle** (unpatched code IS exploitable)
  - `fix-run.sh` → **negative control** (patched code is NOT exploitable)
  - `unit_test.sh` → **functionality-preserving constraint**
  - `llm.patch` → **root-cause evidence** (the ground-truth patch); `prepare.sh` resets repo state.
- **CrossCommitVuln-Bench lesson** — 87% of its chains are invisible to per-commit SAST; even
  full-codebase scanning catches only ~27%. Teaches the agent: **one unsafe line ≠ a vulnerability**;
  root cause can span commits.
- **Vul4J** targets the exact classes we care about: deserialization, path traversal, XML/XXE, EL
  injection, auth/access-control, unsafe reflection.

## Filter criteria for our use-case

- **Never train on these** — reserve strictly for held-out eval to avoid leakage.
- Web/API relevance: **CVE-Bench** (web) and **PatchEval** (Go/JS/Python) are the primary eval
  targets; Vul4J for Java classes; ARVO for native/parser skills; CrossCommit for the
  multi-commit-reasoning stress test.
- Enforce the four held-out axes (see HOLD-OUT-EVALUATION.md): different product / different
  framework / later disclosure date / unused source / patched+benign version.

## License notes

- Each repo has its own license (mostly permissive research licenses); **Docker images bundle
  upstream code under upstream licenses**. Use for evaluation; attribute the benchmark; don't
  redistribute the images as if they were ours.

## Risks / caveats

- **CVE-Bench: RCE over-representation**, under-represents access-control / info-disclosure — our
  highest-ROI bounty classes. Don't let it define "success".
- **VLoc/Antares are brand-new (2026-07-21)** — localization ≠ exploitation; the 290-repos /
  6-ecosystems / 147-CWEs breakdown is from the brief, not independently confirmed.
- **PatchEval measures *patching*, not *finding*** — reverse it carefully for a detection oracle.
- **ARVO/PrimeVul are C/C++-heavy** — limited transfer to web skills.
- **Storage:** PatchEval's 230 containers ≈ 460 GB; ARVO images are large too — plan disk budget.

## Concrete next steps

- **First use:** wire **CVE-Bench** + **PatchEval (Go/JS/Python subset)** as the standing regression
  eval for every skill build; add **CrossCommitVuln-Bench** as the multi-commit stop-condition test.
- **Wave point:** Wave 3 (executable validation) — stand these up *after* the ground-truth skills
  exist so each skill has something to be evaluated against.

## Honest ledger

- **Verified (web):** CVE-Bench (40 web CVEs, Docker, arXiv 2503.17332, uiuc-kang-lab repo); PatchEval
  (1,000 vulns / 65 CWEs / Go-JS-Python / 230 Docker / vul-run+fix-run+unit_test+llm.patch+prepare,
  bytedance repo); Vul4J (79/51/25, tuhh-softsec repo, MSR 2022); ARVO (5,001→6,000+ C/C++, n132
  repos, arXiv 2408.02153); CrossCommitVuln-Bench (15 Python, per-commit 13% / cumulative 27%,
  motornomad repo, arXiv 2604.21917); VLoc = Cisco Antares release dated 2026-07-21, 500-entry
  localization benchmark.
- **NOT independently verified:** VLoc's 290 repos / 6 ecosystems / 147 CWEs and ARVO's exact
  6,100 / 311 / 81% / 89.4% figures (later-snapshot numbers from the brief) — treat as approximate.
