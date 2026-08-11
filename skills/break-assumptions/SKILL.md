---
name: break-assumptions
description: Map the implicit contract a development team encoded into an attack surface — what they assumed about reachability, upstream validation, identifier secrecy, caller identity, parser agreement, and execution context — then rank those assumptions by what breaks if false. Load after recon and before the CWE hunters, or whenever a candidate stalls and you need to know which control is actually holding. Triggers — break assumptions, what did the devs assume, assumption ledger, why is this not exploitable, what control is holding, threat-model this surface, is this intended behavior.
---

# Break-Assumptions

Apply only against assets you are explicitly authorized to test under the relevant program's
published HackerOne policy and the repository's
[`SECURITY-RESEARCH-POLICY.md`](../../SECURITY-RESEARCH-POLICY.md). This skill is analysis, not
exploitation — it produces ranked hypotheses, never findings. Every surviving assumption still
owes its hunter a dynamic proof through
[`dynamic-poc-validation`](../dynamic-poc-validation/SKILL.md). Skills are optional and
non-normative; the contracts and gates always take precedence.

## Why this skill exists

Across this repository's 15 targets, 62 findings have been closed. The closure reasons are not
detection failures:

| Closure reason | Count | What actually went wrong |
|---|---|---|
| `no_impact` | 20 | The assumption was broken, but breaking it changed nothing an attacker wants |
| `control_held` | 17 | A control we had not named was enforcing the assumption |
| `intended_behavior` | 10 | The assumption was a documented, deliberate design decision |
| `version_mismatch` | 7 | The assumption was false in some version, not the pinned one |
| `privilege_equivalent` | 3 | The attacker already held what breaking it would grant |
| `unsupported_authorization_inference` | 2 | We asserted a boundary that was never claimed |

**~47 of 62 kills are assumption-analysis failures, not detection failures.** We find real code
behavior constantly; we lose on whether anyone ever promised that behavior would not happen. This
skill front-loads that analysis so candidates die in minutes instead of after a PoC and a report
draft (see the sunk-cost failure mode, [`METHODOLOGY.md`](../../METHODOLOGY.md) §9).

## Where it runs

Two entry points:

1. **After [`recon`](../recon/SKILL.md), before the hunters.** Recon yields a candidate surface;
   this skill converts that surface into a ranked assumption ledger and routes each surviving
   assumption to the hunter that can falsify it.
2. **Mid-hunt, when a candidate stalls.** When a hunter proves a behavior but cannot show impact,
   run steps 3–5 before writing anything. That is where `control_held` and `intended_behavior`
   are caught.

It is *not* a per-finding review of a completed report — that is adversarial validation, which
attacks a conclusion. This attacks a design.

## Step 1 — Enumerate the implicit contract

For each trust boundary on the surface, write down what the code must be assuming to be correct.
These recur across every target class in this repo:

| Assumption class | The developer belief | What falsifies it |
|---|---|---|
| **Reachability** | "only our own code calls this" | Exported component, undocumented route, alternate interface (REST vs GraphQL vs job handler) |
| **Upstream validation** | "this input was already sanitized before it got here" | A second caller that skips the validating layer |
| **Identifier secrecy** | "this ID is unguessable" | Sequential, UUIDv1, email-derived, or public identifier |
| **Caller identity** | "the sender field equals the authenticated signer" | Message-construction path that sets the field independently |
| **Parser agreement** | "these two components read this the same way" | Front-end vs back-end, validator vs consumer, two URL/path parsers |
| **Execution context** | "this only runs at build time / by an operator / in dev" | A trigger that reaches it at request time or from a PR |
| **Client enforcement** | "the UI prevents this" | Direct API call bypassing UI sequencing |
| **Asset ownership** | "this file/artifact/dependency is ours" | Mutable tag, unverified download, fork replacement, attacker-writable path |
| **Serialization fidelity** | "what we export is what we import" | Genesis/state export dropping fields; round-trip asymmetry |

Write each as a falsifiable sentence naming a subject and an object: *"the `x/liquid` handler
assumes `msg.Sender` is the authenticated signer."* An assumption you cannot phrase that way is
not yet an assumption — it is a vibe.

## Step 2 — Build the assumption ledger

Use the ledger format already defined in [`METHODOLOGY.md`](../../METHODOLOGY.md) §10
(chain-of-assumptions) so there is one vocabulary, not two:

| # | Assumption | Where encoded | What breaks it | Dynamically testable? | Impact if false |
|---|---|---|---|---|---|
| 1 | Caller is first-party | `AndroidManifest.xml` `exported=true` | Third-party intent | Yes — AVD rig | Depends on step 3 |
| 2 | Path stays in sandbox | `filepath.Join` with no `Clean` check | `../` traversal | Yes | Arbitrary read |

Rank by **impact if false**, not by how likely you are to break it. An assumption that is trivial
to break and grants nothing is worth less than a hard one that grants cross-tenant read. This
ordering is the whole point of the skill — it is what stops the 20 `no_impact` closures.

## Step 3 — The design-intent inverse check

**This is the step that would have prevented 10 `intended_behavior` closures.** Before treating a
broken assumption as a candidate, establish whether the developers *made it deliberately*:

- Search the code, docs, config comments, changelogs, and issue tracker for the behavior. A named
  escape hatch is a decision, not a bug — this repo already closed
  `AllowSimplePasswords is an explicit non-production escape hatch` for exactly this reason.
- Ask whether the program's own docs advertise the capability. If the product's documentation
  describes it, you are reporting a feature.
- Distinguish **implicit** assumptions (nobody wrote it down; the code just depends on it) from
  **defended** ones (there is a check, a comment, a test, or a doc). Implicit assumptions are
  candidates. Defended ones are only candidates if the defense is *incomplete* — hand those to
  [`patch-review-hunter`](../patch-review-hunter/SKILL.md).

If the assumption is deliberate and documented, close it now with `intended_behavior`. Do not
write a report to find out.

## Step 4 — Name the primary control

**This is the step that would have prevented 17 `control_held` closures.** For every assumption
you intend to break, answer in one sentence: *what actually stops me right now?*

- Name the control, the layer it lives on, and how you would observe it engaging.
- Then ask the question that decides reportability: **is the control I am claiming to break the
  control the vendor considers the security boundary?** This repo's `claude-code-action`
  submission was closed NA precisely here — the primary control was the write-access gate, and
  the sanitizer we bypassed was never the boundary.
- If a compensating control on another layer neutralizes the impact, that is
  `control_exists_elsewhere` — close it.
- A control you have not named is not absent. It is unexamined.

## Step 5 — The privilege-equivalence test

**This is the step that would have prevented 3 `privilege_equivalent` closures.** State the
attacker's starting privilege explicitly, then ask whether breaking the assumption grants
anything they did not already hold.

- If the prerequisite is repo write access, operator access, an admin session, or platform
  compromise, the "impact" is usually already implied by the prerequisite.
- Write the claim as *"an attacker holding X gains Y"* and check that Y is strictly larger than X.
- If Y ⊆ X, close it — no PoC will fix this.

## Step 6 — Route what survives

A surviving assumption is an **observation**, never a finding. Route by what falsifies it:

| Surviving assumption | Route to |
|---|---|
| Reachability / caller identity | [`access-control-hunter`](../access-control-hunter/SKILL.md), [`auth-bypass-hunter`](../auth-bypass-hunter/SKILL.md) |
| Identifier secrecy | [`idor-hunter`](../idor-hunter/SKILL.md) |
| Upstream validation, parser agreement | [`path-traversal-hunter`](../path-traversal-hunter/SKILL.md), [`sqli-hunter`](../sqli-hunter/SKILL.md), [`xss-reflected-hunter`](../xss-reflected-hunter/SKILL.md) |
| Execution context, asset ownership | [`ssrf-hunter`](../ssrf-hunter/SKILL.md), [`rce-chaining`](../rce-chaining/SKILL.md) |
| Client enforcement, serialization fidelity | [`business-logic-hunter`](../business-logic-hunter/SKILL.md) |
| Role reachable from lower privilege | [`privesc-hunter`](../privesc-hunter/SKILL.md) |

Version-bound assumptions ("this is vulnerable in some release") must be resolved against the
pinned artifact before routing — 7 closures were `version_mismatch`.

## Output

Resolve the target directory with `tools/_target_discovery.sh`, then write the ledger to
`<target>/notes/assumptions/<surface>-ledger.md`, redacted. Research-time material stays in
`notes/` per [`CLAUDE.md`](../../CLAUDE.md); it is not a finding and must not be added to
`findings-manifest.json`. Track broken-but-unchainable assumptions as **gadgets** for
[`rce-chaining`](../rce-chaining/SKILL.md) — do not discard a working primitive for lack of
standalone impact.

After completing the six steps, look for assumptions the table did not name — the skill is a
floor, not a ceiling.

## Stop conditions (verified negatives)

Each carries one of the 12 categories from
[`references/negative-control-taxonomy.md`](../references/negative-control-taxonomy.md). Apply ALL
applicable labels.

**Decision split (apply separately, never collapse):**
- `technically_vulnerable` — is the assumption actually breakable?
- `in_scope` — does the policy + `contract.yaml` cover the asset it lives on?
- `program_reportable` — would breaking it meet the program's threshold?

- `[expected_product_behavior]` / `[missing_security_boundary]` The assumption is a documented,
  deliberate design decision (step 3) — close, do not report.
- `[control_exists_elsewhere]` A compensating control on another layer holds the assumption even
  when your input reaches the path (step 4).
- `[missing_attacker_control]` The value you would need to change is server-derived.
- `[theoretical_without_oracle]` The assumption is broken on paper with no observed effect —
  breaking it must be shown, not argued.
- `[real_but_below_program_impact_threshold]` Breaking it grants nothing beyond the attacker's
  starting privilege (step 5).
- `[patched_version]` / `[vulnerable_third_party_but_target_not_affected]` The assumption is false
  only outside the pinned artifact's version boundary.

## Anti-patterns

- Do not treat "the developers did not think of this" as impact. They may have, and written it down.
- Do not skip step 4 because the bug "obviously" works — an unnamed control is the single largest
  kill bucket in this repo after `no_impact`.
- Do not rank assumptions by how clever it is to break them; rank by impact if false.
- Do not let the ledger become the report. It is a research note; promotion happens through the
  gates.
- Do not enumerate assumptions on assets outside the allowlist — analysis of an out-of-scope asset
  is still out of scope for testing.

## Evidence basis and limits

**Corpus-grounded, not methodology-seeded**: the closure census in this file was computed from the
`closure_reason` fields across every `targets/*/findings-manifest.json` in this repository at the
time of writing, and the named examples (`AllowSimplePasswords`, `claude-code-action` NA,
`x/liquid` sender/signer) are real closures from this repo's own history. The assumption-class
table generalizes those cases and is therefore a hypothesis generator, not proof of coverage. The
counts drift as findings close; re-derive them rather than trusting this table indefinitely.

## AI-assisted augment (albinowax seed)

Transferable technique from James Kettle (albinowax), whose documented method is hunting *unknown*
vulnerability classes by looking for **behavioral discrepancies** rather than signatures; see
[`knowledge-sources/creators/07-albinowax.md`](../../knowledge-sources/creators/07-albinowax.md).
Guardrail: model output is a hypothesis, not evidence — resolve every candidate against live target
behavior, and never paste confidential target vocabulary, source, or evidence into an unapproved
model (CWE-200 prompt boundary). Never accept a model-recalled CVE ID.

- **Discrepancy-driven assumption discovery.** Where two components both interpret the same input
  (validator and consumer, front-end and back-end, exporter and importer), ask an approved model to
  enumerate inputs the two might read differently. Each divergence candidate is an unstated
  parser-agreement assumption; confirm by observing both components, never by the model's claim.
- **Inverted threat-model prompt.** Give an approved model the surface description and ask what the
  implementer must have believed for the code to be correct. Treat the output as a checklist to
  verify against the code — it reliably surfaces the implicit assumptions a reader skips, and
  reliably invents some that do not exist.
- **Consensus guard.** Independent agents inheriting the same framing agree for shared-premise
  reasons ([`METHODOLOGY.md`](../../METHODOLOGY.md) §11). Require each reviewer to state its
  assumptions separately before comparing conclusions.

## Version boundaries

Null — this is a process/analysis skill, not version-bound. The assumptions it discovers are
frequently version-bound; resolve those against the pinned artifact before routing.
