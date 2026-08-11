---
source_type: fix-commit-dataset
last_updated: 2026-07-22
priority: P0
reliability: medium
---

# MoreFixes (CVE → fix-commit dataset)

## What it is

The largest open dataset that mines CVEs to their **actual fixing commits** across GitHub projects,
with per-CVE / per-commit / per-file / per-method + CWE metadata and a heuristic `score` for how
confidently a commit is the security fix. It is the workhorse for **variant extraction**: the same
root cause patched the same way across many projects reveals a reusable patch motif.

## Concrete endpoints / URLs

- **Repo (tooling + schema):** `https://github.com/JafarAkhondali/Morefixes`
- **Paper:** "MoreFixes: A Large-Scale Dataset of CVE Fix Commits Mined through Enhanced Repository
  Discovery", PROMISE/MSR 2024 — DOI `10.1145/3663533.3664036`.
- **Dataset (Zenodo):**
  - v2 (2024-09-26): `https://zenodo.org/records/13983082` — **26,617 CVEs / 6,945 projects /
    31,883 fix commits** (web-verified figures).
  - **v4 (2026-06-20): `https://zenodo.org/records/20776007`** — the June-2026 release the brief
    cites (uses NVD 2.0 feeds; CVEs through ~2026-06-02). *v4 headline counts per the brief:
    43,357 CVEs / 9,972 projects / 47,616 fix commits / 52,672 patch files — see ledger; not
    independently confirmed this session.*

The dataset ships as a PostgreSQL dump; query it locally rather than via an API.

## What it adds beyond HackerOne

- **Vulnerable-vs-fixed code at scale** — the exact diff, not a prose "we patched it".
- **Repeated patch motifs** — cross-project variants of one root cause (e.g. the same missing
  `escapeHtml` across 40 templating libs) → generalizable invariant, not a payload.
- **File/method/commit granularity** — feeds the `engineering_evidence.patch_diff` and
  `changed_tests` fields of the case bundle.
- **CWE per fix** — lets us bucket motifs straight into the per-CWE skills.

## Filter criteria for our use-case

- **Languages:** JavaScript/TypeScript, Python, Java/Kotlin, PHP, Ruby, Go, C#.
- **`score` / `fix_score >= 65`** — the brief's threshold; the `score` field ranks how likely a
  commit is the genuine security fix. Above ~65 = high-confidence patch. *(Understand the exact
  `score` column semantics from the repo README before trusting the cutoff.)*
- One identifiable security-relevant patch, a reachable **vulnerable parent revision**, and (ideally)
  an available regression test.
- A specific base/variant CWE and a **network-reachable / user-controlled** attack surface (drop
  build-only, CI-only, or local-privilege bugs unless building that skill).

## License notes

- MoreFixes aggregates public commits/CVE data; the dataset is released for research on Zenodo (check
  the record's stated license — typically CC-BY). Underlying **commit diffs carry their upstream
  repo licenses** (GPL/MIT/Apache/etc.). For *training/derivation* keep provenance + upstream license
  per commit; treat verbatim large diffs as licensed code, extract the *motif/invariant* not the code.

## Risks / caveats

- **Version discrepancy (flag):** the brief's v4 counts differ from the web-verified paper/v2 counts
  — confirm the actual v4 numbers from `zenodo.org/records/20776007` before quoting them anywhere.
- **`score` is heuristic** — false-positive "fix" commits exist; the threshold reduces but doesn't
  eliminate noise. Human-review high-value bundles.
- **Isolated-diff bias:** a fix commit alone can hide multi-commit root causes (see
  CrossCommitVuln-Bench in file 05) — don't teach "one unsafe line = vuln".
- **License heterogeneity** across thousands of repos — track per-commit provenance.

## Concrete next steps

- **First skill to benefit:** CWE-79 (XSS) and CWE-89 (SQLi) — dense, well-labeled patch motifs;
  ideal for invariant + contrastive extraction.
- **For web/API skills prioritize MoreFixes over PrimeVul/MegaVul** (real repo diffs, not isolated
  C/C++ function snippets).
- **Wave point:** Wave 1, after GHSA/OSV — use OSV boundaries to sanity-check MoreFixes parent/fixed
  revisions.

## Honest ledger

- **Verified (web):** repo `JafarAkhondali/Morefixes`; PROMISE/MSR 2024 paper DOI; v2 Zenodo record
  13983082 with 26,617 CVEs / 6,945 projects / 31,883 commits; a **v4 dated 2026-06-20 at Zenodo
  record 20776007** using NVD 2.0.
- **NOT independently verified:** the brief's v4 headline counts (43,357 / 9,972 / 47,616 / 52,672)
  and the precise definition/units of the `score`/`fix_score` field — confirm from the v4 record and
  repo README before relying on them.
