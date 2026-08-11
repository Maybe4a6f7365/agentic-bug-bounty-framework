---
source_type: roadmap
last_updated: 2026-07-22
status: living
---

# Skills Roadmap — toward a complete, holistic bug-bounty pipeline

Inventory of the current skill library, the structural gap, and a prioritized build order.
This is a **living planning doc**, not a contract — it never overrides `CONTRACT.md`,
`METHODOLOGY.md`, or any target's gates. Grounded in the repo's own evidence:
[`METHODOLOGY.md`](../METHODOLOGY.md) (our failure retrospective),
[`knowledge-sources/INTEGRATION-RECOMMENDATIONS.md`](../knowledge-sources/INTEGRATION-RECOMMENDATIONS.md)
(stated build order), and [`CLAUDE.md`](../CLAUDE.md) (recon-first / mine-JS-bundles).

## Current inventory (by pipeline role)

| Pipeline role | Skills present | State |
|---|---|---|
| Vuln-class detection/exploitation | access-control, auth-bypass, business-logic, idor, info-disclosure, path-traversal, privesc, sqli, xss-reflected, xss-stored | 10 CWE hunters — strong |
| Chaining / RCE | rce-chaining | 1 |
| Patch analysis | patch-review-hunter | 1 |
| Engineering-context ingest | case-bundle-builder | 1 |
| New CWE hunter (this sprint) | **ssrf-hunter** | methodology-seeded; corpus back-fill pending |
| Shared references | negative-control-taxonomy, audit-invariants | 2 |
| Process skills (built) | **recon**, **break-assumptions**, **scope-policy-qualification**, **dynamic-poc-validation**, **duplicate-preflight** | surface routing + assumption analysis + scope/reportability + manifest-aligned gate/checklist |
| Process stages still missing (severity, reporting, adversarial review) | — (only `tools/*.sh` + METHODOLOGY prose) | **gap** |

**Library registration (2026-07-28).** The library is loaded through the `.claude/skills` symlink;
frontmatter `description` is the only routing signal (the former `trigger:` field was inert and has
been folded into the descriptions). `tools/validate-skills.sh` + CI enforce registration,
frontmatter validity, and index sync. Adding skills is now cheap — the constraint is description
*discrimination*, not count, so every new skill must say when to load it and which sibling to
prefer.

Every hunt skill carries an `## AI-assisted augment (NahamSec seed)` section applying
LLM-assisted techniques to its CWE class (see `knowledge-sources/creators/03-nahamsec.md`).

## Diagnosis: the library is middle-heavy

Every skill answers *"given a surface, how do I hunt CWE-X?"* But `METHODOLOGY.md` records
0 bounties from 3 submissions, and all three failed at **qualification, novelty, and
control analysis** — not at detection. The named failure modes (duplicate-preflight never
done, static-before-dynamic bias, severity inflation, self-test artifacts, policy-boundary
misses) all live at the **front and back** of the pipeline, which currently have **no
loadable skills**. Highest leverage is therefore process/orchestration skills, then breadth.

## Build order

### Tier 0 — Foundational (pipeline is incomplete without these)
1. **recon / attack-surface-mapping** — **DONE this sprint.** JS-bundle mining first, then
   subdomain/asset enum → live-host probe → crawl → historical URLs → param mining → `gf`
   class-triage, routing the candidate surface to each hunter (carries the recon-signal → CWE
   routing map). Writes a surface map to `notes/` and conservatively refreshes `pre_scan.yaml`.
2. **duplicate-preflight** — **DONE this sprint.** Prepares the novelty search set, runs
   `tools/duplicate_preflight_checklist.sh`, and hands off to the human (agent never queries
   Hacktivity — `duplicate_preflight` is human-filled per CONTRACT). (YELP-F01 was a duplicate.)
3. **scope-policy-qualification** — **DONE this sprint.**
   Resolves the `in_scope` / `program_reportable` gates from the live policy + `contract.yaml`;
   builds the allowlist, sets identification headers + rate budget, gates target entry and
   handoff, and refreshes `pre_scan.yaml` policy freshness.

3b. **break-assumptions** — **DONE 2026-07-28.** Converts a surface into a ranked assumption
   ledger (impact-if-false ordering), runs the design-intent inverse check, names the primary
   control, and applies the privilege-equivalence test before any PoC work. Grounded in this
   repo's own closure census: ~47 of 62 closed findings died on assumption analysis, not
   detection. Routes survivors to the hunters as observations.

### Tier 1 — Qualification & proof (where bounties are won/lost)
4. **dynamic-poc-validation** — **DONE this sprint.** Operationalizes the Dynamic PoC Readiness
   Gate (principal separation, authoritative outcome via an independent channel, negative
   control, 2× reproduction) and emits the manifest `qualification` block.
5. **impact-qualification** — observation → hypothesis → qualified state machine; falsifiable
   impact statement; the "should I report this?" decision tree.
6. **severity-calibration** — proven vs theoretical severity; anti-inflation checklist. Should
   inherit each hunter's stop conditions as its false-positive knowledge base and apply the
   3-label split independently ("is this really a P1 or a self-impact?").
7. **adversarial-validation** — a dedicated skeptical validator: knows the common
   false-positive patterns per CWE class (each hunter's stop conditions are the rulebook),
   actively tries to disprove the finding, calibrates severity against proven-not-theoretical
   impact. Disprove-not-confirm independent review; AI-consensus-illusion guard.

### Tier 2 — Output
8. **h1-report-writing** — impact-first report; redaction; report-quality ≥27/30 gate.

### Tier 3 — Missing CWE hunters (breadth, by ROI)
9. **ssrf-hunter** (CWE-918) — **DONE this sprint** (methodology-seeded; feeds rce-chaining).
10. ssti / template-injection (CWE-94/1336) · deserialization (CWE-502) · command-injection
    (CWE-78) · xxe (CWE-611) · open-redirect (CWE-601, chain primitive) · csrf (CWE-352) ·
    cors-misconfig · request-smuggling (CWE-444).
11. Cross-cutting extensions: graphql-abuse · jwt/oauth-deep (extend auth-bypass) ·
    file-upload→RCE · subdomain-takeover · race-condition (extend business-logic).

### Tier 4 — Supporting references
- recon-signal → CWE routing map — **DONE** (authored inline in `recon/SKILL.md`).
- primary-control identification reference.
- evidence-taxonomy reference (METHODOLOGY's 7 evidence types).

## First vertical slice — COMPLETE
`recon` → `ssrf-hunter` → `dynamic-poc-validation` → `duplicate-preflight`: one end-to-end
loop — *find surface → hunt a high-ROI class → prove it dynamically → check novelty* — the
loop METHODOLOGY says we keep breaking. All four skills now exist. Next: close the remaining
Tier 0–2 process gaps (severity-calibration, h1-report-writing,
adversarial-validation).

## Conventions for every new skill
- Match the per-CWE hunter format; wire stop conditions to
  `skills/references/negative-control-taxonomy.md` with the 3-label decision split.
- Include fallback toolchains for key steps (primary → fallback → manual equivalent).
- Close the method section with "the skill is a floor, not a ceiling" — encourage creative
  exploration beyond the checklist after completing the structured checks.
- Track proven-but-not-yet-chainable primitives as **gadgets** (observations that feed
  `rce-chaining`); do not discard a working primitive for lack of standalone impact.
- End with an `## AI-assisted augment (<creator> seed)` section: class-specific, model output
  is a hypothesis resolving to a live oracle, mandatory CWE-200 prompt boundary, no
  model-recalled CVE-IDs, attribution/provenance.
- Never fabricate H1 report IDs. If a skill is methodology-seeded rather than corpus-mined,
  say so and mark negatives `[technical_placeholder]`.
- When building or iterating a skill, validate with a dual-agent comparison: run one agent with
  the skill loaded and one freeform on the same target surface; diff what each found that the
  other missed.
