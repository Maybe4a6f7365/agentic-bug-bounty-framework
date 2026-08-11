# Bug-Bounty Skills

Reusable, **non-target-specific** methodology references ("skills") for the
research in this repository. A skill captures a repeatable technique or checklist
— how to hunt a bug class, chain primitives, or validate impact — independent of
any single HackerOne program. Target-specific findings, evidence, and PoCs stay in
their target directory; the transferable *method* lives here.

This folder is a repo-level shared resource, like the
[`setup/gcp-avd/`](../setup/gcp-avd/) cloud AVD rig and
[`METHODOLOGY.md`](../METHODOLOGY.md), and is not tied to any one target.

## Authorization

Skills are optional, **non-normative** guidance. They never override the
repository's contracts, qualification gates, or scope rules. Apply any technique
here only against assets you are explicitly authorized to test under the relevant
program's published HackerOne policy and the mandatory
[`SECURITY-RESEARCH-POLICY.md`](../SECURITY-RESEARCH-POLICY.md). Stay in scope,
respect each program's rate limits and identification headers, avoid destructive
actions, and redact all evidence before committing.

## How skills load

Every skill is a folder — `skills/<name>/SKILL.md` — opening with YAML frontmatter that declares
`name` and `description`. **The `description` is the only routing signal**: the agent harness reads
it to decide when to load the skill, so each one states what it does *and when to load it*, plus
the vocabulary that should trigger it and which sibling skill to prefer when they overlap.

The library is registered through the `.claude/skills` symlink at the repo root, which resolves to
this directory. Without that symlink these files are documentation that nothing loads. Run
[`tools/validate-skills.sh`](../tools/validate-skills.sh) to verify registration, frontmatter, and
that this index has not drifted; CI enforces it.

## Available skills

**Analysis / process skills** (pipeline stages, not CWE classes):

| Skill | Summary |
|---|---|
| [`recon`](recon/) | Map the external attack surface — JS-bundle mining first — and route the candidate surface to the right hunter; the front of the funnel every hunter consumes. |
| [`break-assumptions`](break-assumptions/) | Map the implicit contract the developers encoded into a surface, rank assumptions by impact-if-false, and kill `intended_behavior` / `control_held` / `privilege_equivalent` candidates before PoC work. Runs after recon, before the hunters. |
| [`scope-policy-qualification`](scope-policy-qualification/) | Resolve the `in_scope` + `program_reportable` gates from the live policy and `contract.yaml`; gates target entry and handoff. |
| [`dynamic-poc-validation`](dynamic-poc-validation/) | Execute the Dynamic PoC Readiness Gate and emit the manifest `qualification` block. |
| [`duplicate-preflight`](duplicate-preflight/) | Prepare the novelty check and hand off to the human — the agent never queries Hacktivity. |
| [`rce-chaining`](rce-chaining/) | Chain primitives (file write, file read, SSRF, JS execution in headless browsers, deserialization) into RCE — headless Chrome + DevTools, Perforce file write → DLL hijack, vulnerable components, SSRF → cloud metadata. |
| [`case-bundle-builder`](case-bundle-builder/) | Build a `case-bundle.yaml` from a CVE/GHSA + repo + fix-commit pair (engineering-source ingest). |
| [`patch-review-hunter`](patch-review-hunter/) | Decide whether a security patch is complete, or whether "already patched" means "actually fixed". |

**Per-CWE hunt skills:** `access-control-hunter`, `auth-bypass-hunter`, `business-logic-hunter`,
`idor-hunter`, `info-disclosure-hunter`, `path-traversal-hunter`, `privesc-hunter`, `sqli-hunter`,
`ssrf-hunter`, `xss-reflected-hunter`, `xss-stored-hunter`. Each carries an
`## AI-assisted augment (NahamSec seed)` section applying transferable LLM-assisted techniques to
that CWE class, sourced from
[`knowledge-sources/creators/03-nahamsec.md`](../knowledge-sources/creators/03-nahamsec.md).

## Shared references

Cross-cutting references under [`references/`](references/) that individual skills link to:

| Reference | Summary |
|---|---|
| [Negative-Control Taxonomy](references/negative-control-taxonomy.md) | The shared 12-category stop-condition vocabulary and 3-label decision split every hunt skill uses to decide when *not* to file. |
| [Audit Invariants](references/audit-invariants.md) | Reusable trust-boundary and workflow/state-machine invariants extracted from disclosed audits; linked by access-control and business-logic hunters. |

## Roadmap

See [`ROADMAP.md`](ROADMAP.md) for the current inventory, the middle-heavy gap analysis,
and the prioritized build order toward a complete pipeline (recon, dynamic-PoC validation,
duplicate-preflight, qualification, reporting, and the remaining CWE hunters).

## Adding a skill

1. Add a new `skills/<skill-name>/SKILL.md` folder skill (the convention every skill follows),
   with YAML frontmatter declaring `name` (matching the folder) and `description`, and a lead
   scope/authorization line consistent with the repo's norms. Root-level `skills/<skill-name>.md`
   files are not loadable and are rejected by the validator.
2. Write the `description` for the router, not for a human index: state what it does, **when to
   load it**, the trigger vocabulary, and which sibling skill to prefer when they overlap. Do not
   add a `trigger:` field — it is not read.
3. List it in the relevant table/paragraph above (analysis skill, per-CWE hunter, or reference).
4. Wire stop conditions to `references/negative-control-taxonomy.md` (preamble + 3-label split)
   and end with an `## AI-assisted augment` section; keep it method-focused and reusable, with
   no target-specific evidence or PII.
5. Run `./tools/validate-skills.sh` before committing.
