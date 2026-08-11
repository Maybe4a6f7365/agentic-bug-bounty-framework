# Case-bundle schema reference

## Authority and scope

This reference summarizes
`../../../knowledge-sources/engineering-sources/CASE-BUNDLE-SCHEMA.md`. The upstream file is the
canonical schema; resolve any disagreement in its favor. The unit of ingestion is one
vulnerability with attacker narrative, engineering ground truth, negative controls, triage, and
provenance. Keep all eight sections even when values are unknown.

## Top-level identifier

- `case_id` — required stable, unique, zero-padded or repository-standard case identifier.

## 1. `classification`

Required fields:

- `cwe_leaf` — most specific supported CWE, or `null` with reason.
- `cwe_class` — broader vulnerability class, or `null` with reason.
- `mapping_confidence` — `auto`, `reviewed`, or `disputed`.
- `alternative_mappings` — list; use `[]` when none survive review.

Use OSV/GHSA CWE metadata as a starting point. A human promotes `auto` to `reviewed`; preserve
credible alternatives rather than forcing false precision.

## 2. `environment`

Required fields: `product`, `framework`, `language`, `component`, `vulnerable_version`, and
`fixed_version`. Populate ranges from OSV/GHSA events and repository tags. Do not translate
`introduced: "0"` into a commit SHA. If framework or component is not established, use `null`
with a reason.

## 3. `researcher_evidence`

Required fields: `original_report`, `reproduction`, `demonstrated_impact`,
`required_privileges`, and `attack_preconditions`. These describe the attacker narrative from a
public report, VRP/H1 disclosure, advisory, or reproducible lab evidence. A PoC link is optional;
never imply it was executed without a log.

## 4. `engineering_evidence`

Required fields:

- `vulnerable_repository`, `vulnerable_commit`, and `fix_commit`;
- `patch_diff` ★ — artifact reference, comparison endpoints, and hash;
- `changed_tests` ★ — test paths/names, fix commit, oracle, and execution status;
- `maintainer_discussion` ★ — issue/PR/comment permalinks and concise notes;
- `root_cause_summary` — reviewed explanation grounded in the patch.

The three star fields require human review. Missing public artifacts remain `null` with the search
performed and reason. Do not paste a large patch into YAML.

## 5. `behavioral_model`

Required fields: `attacker_controlled_input`, `trust_boundary`,
`missing_or_incorrect_control`, `sensitive_operation`, `exploit_oracle`, `negative_control` ★,
and `neighboring_safe_behavior`. The negative control must show a patched or safe behavior that
must not trigger. A neighboring safe behavior is optional only when no defensible sibling exists;
record that absence explicitly.

## 6. `agent_guidance`

Required fields: `applicability_signals`, `hypotheses`, `low_impact_probes`,
`evidence_requirements`, `false_positive_conditions` ★, `stop_conditions`, and
`prohibited_actions`. Use lists even for one item. The star field requires human review and must
encode concrete cases in which the agent should not report.

## 7. `triage`

Required fields: `technically_vulnerable`, `in_scope`, `reportable`, `severity`, and
`reviewer_reasoning`. Keep the first three labels independent. Use `unknown` during build when the
local consumer permits it; otherwise use `null` with a reason until a human decides. Severity does
not substitute for any label.

## 8. `provenance`

Required fields:

- `sources` — primary URLs and stable local artifact identifiers.
- `source_versions` — advisory revision, commit SHA, tag, dataset release, or API version.
- `licenses` — per-source license or `unknown — review required`.
- `retrieved_at` — ISO 8601 timestamp with timezone.
- `content_hashes` — hashes of the exact ingested bytes.
- `human_reviewer` — reviewer identity, or `null` until review.

## `provenance.content_hashes`

Include SHA-256 for every artifact that supports a material claim:

- raw OSV request/response and GitHub advisory response;
- commit metadata and issue/PR API responses used;
- introduced-to-fixed patch and changed-file listing;
- preserved maintainer discussion or release-note snapshot;
- regression-test source and execution log when executed;
- researcher report/PoC snapshot when licensing permits preservation;
- final bundle via a detached ledger or consumer-defined non-self-referential convention.

Prefer `sha256:<hex>  <relative-path>` or an equivalent mapping supported by the pipeline. Hash
raw bytes before normalization. Never embed a bundle hash inside the same bytes it hashes. Redact
secrets before preservation, then hash the redacted artifact and document the transformation.

## Required versus optional handling

The template fields are structurally required: retain each key. Evidence may be unavailable, in
which case the value may be `null` only with a concise reason in the value or adjacent review
ledger. Optional enrichments include PoC links, safe-neighbor examples, alternative mappings, and
additional API metadata; their absence must not erase a canonical key.

## Human-review gate

The following cannot become ingestion-ready through automation alone:

1. `behavioral_model.negative_control`
2. `engineering_evidence.maintainer_discussion`
3. `engineering_evidence.patch_diff`
4. `engineering_evidence.changed_tests`
5. `agent_guidance.false_positive_conditions`

Keep `[HUMAN-REVIEW-REQUIRED]` in a permitted extension or sibling review ledger until an
identified reviewer signs off. Do not modify the canonical schema to add the marker.
