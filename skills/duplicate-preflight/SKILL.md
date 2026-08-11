---
name: duplicate-preflight
description: Prepare the novelty/duplicate check for a candidate finding — assemble search terms and candidate-match context, run the checklist tool, and hand off to the human who queries HackerOne Hacktivity and fills the manifest. Load after a candidate is qualified and before submission. The agent MUST NOT query Hacktivity. Triggers — duplicate preflight, novelty check before submission, is this a known bug, check Hacktivity.
---

# Duplicate Preflight

**Hard boundary — per [`CONTRACT.md`](../../CONTRACT.md), `duplicate_preflight` is
HUMAN-FILLED ONLY.** The agent assembles the search-term set and candidate context and runs
the checklist tool; it **MUST NOT** fetch HackerOne Hacktivity or write the
`duplicate_preflight` manifest block. The agent's deliverable is the prepared checklist; a
human performs the query and records the result.

## Method

Two phases, per [`METHODOLOGY.md`](../../METHODOLOGY.md) `## Duplicate-preflight procedure`:

- **Fast preflight** — right after discovery, before >30–60 min of qualification/writing.
- **Final preflight** — immediately before submission, to catch newly disclosed reports.

This skill operationalizes that procedure and wraps the existing tool; it does not restate the
search methodology beyond what the agent must assemble.

## What the agent prepares

Build the search-term set from the candidate's own evidence (do not invent target facts):

- Program and endpoint name; route, feature, and product name.
- Vulnerability class plus close synonyms.
- Distinctive error messages and response fields.
- Mobile activity/intent/deep-link/scheme names, where relevant.
- Historical disclosures and changelog terms; adjacent endpoints sharing the root cause.

Record these terms and the closest self-identified matches alongside the finding, ready for the
human to query.

## Run the checklist tool

`tools/duplicate_preflight_checklist.sh` enumerates every finding whose `duplicate_preflight`
is `null` and emits a Markdown checklist for the human to work through:

```bash
./tools/duplicate_preflight_checklist.sh
# or filter by severity:
./tools/duplicate_preflight_checklist.sh --min-severity Medium
```

Hand the generated checklist plus the prepared search terms to the human. Stop here — the
agent does not proceed to query.

## Human hand-off + manifest block

The human queries Hacktivity, assesses first-mover territory, and fills the block, then re-runs
`bash tools/validate-manifests.sh` to confirm the update:

```json
"duplicate_preflight": {
  "hacktivity_queried": true,
  "anonymous_titles_visible": true,
  "queried_at": "2026-MM-DD",
  "queried_by": "your-handle",
  "first_mover_territory": "moderate"
}
```

Only after this block exists (and its evidence) may `duplicate_preflight_completed` be treated
as true for submission.

## Stop conditions (verified negatives)

Each stop condition below carries one of the 12 categories from
[`skills/references/negative-control-taxonomy.md`](../references/negative-control-taxonomy.md).
Apply ALL applicable labels. Never advance a candidate that triggers any category below.

**Decision split (apply separately, never collapse):**
- `technically_vulnerable`: is the candidate itself a real, proven bug?
- `in_scope`: does the program's policy cover this asset?
- `program_reportable`: does the demonstrated impact meet the program's threshold — *and is it
  novel*?
A finding can be yes/yes/no, yes/no/yes, etc. Novelty is a gate, not an afterthought.

- `[duplicate_root_cause]` A prior/known report shares the same underlying cause, asset,
  exploit path, and impact. A similar *class* alone is not a duplicate — distinguish root
  cause, affected asset, exploit path, or impact before closing. `[technical_placeholder]`
- `[real_but_below_program_impact_threshold]` The finding is genuine but already tracked or
  below the reward bar; record and close rather than submit. `[technical_placeholder]`

These entries are `[technical_placeholder]`: this is a methodology-seeded process skill, so the
taxonomy is their source of authority until curated negatives back them.

## Anti-patterns

- The agent MUST NOT query HackerOne Hacktivity or fabricate `duplicate_preflight` data — it
  prepares and hands off only.
- Do not abandon a finding solely because a similar class exists; check whether the root cause,
  asset, exploit path, or impact is materially distinct.
- Do not set `duplicate_preflight_completed: true` without the human-filled block and its
  recorded evidence.

## AI-assisted augment (NahamSec seed)

Transferable techniques from Ben Sadeghipour (NahamSec), public PlexTrac "Homework for Hackers"
webinar (`Ue-OIJoM0bA`); see
[`knowledge-sources/creators/03-nahamsec.md`](../../knowledge-sources/creators/03-nahamsec.md).
Guardrail: model output is a hypothesis; the human's Hacktivity query is the oracle. Never send
confidential target vocabulary to an unapproved model
(`nahamsec-ai-sanitize-before-sharing`, CWE-200).

- **Neighbor search-term generation (`nahamsec-ai-neighbor-path-ideas`).** From the observed
  feature/endpoint/product vocabulary, ask an approved model for synonyms, abbreviations,
  adjacent-feature names, and likely disclosure phrasings to widen the human's search set —
  then the human decides what to query and how to interpret matches. This expands recall of the
  novelty check without the agent ever touching Hacktivity.

## Version boundaries

Null — this is a process skill, not version-bound.
