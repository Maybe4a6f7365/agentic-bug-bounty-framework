---
source_type: schema
last_updated: 2026-07-22
priority: P0
reliability: high
---

# Case-Bundle Schema

The **unit of ingestion** for the next source wave. Each bundle instruments *one* vulnerability with
both the attacker narrative (which the H1 corpus already covers) and the **engineering ground truth**
the H1 corpus lacks: the vulnerable code, the developer patch, the regression test, the maintainer
discussion, and — crucially — the **negatives** (patched variant, safe neighbor, false-positive
conditions). A fillable template lives at [`templates/case-bundle.yaml`](./templates/case-bundle.yaml).

## The seven sections

1. **classification** — CWE leaf + class, mapping confidence, alternatives. (from GHSA/OSV; a human
   promotes `auto` → `reviewed`.)
2. **environment** — product/framework/language/component + `vulnerable_version`/`fixed_version`
   (the OSV/GHSA `introduced`/`fixed` boundary — kills the "everything before latest is vulnerable"
   bias).
3. **researcher_evidence** — original report, reproduction, demonstrated impact, required privileges,
   preconditions. (H1 / VRP / lab writeup.)
4. **engineering_evidence** — vulnerable repo/commit, fix commit, **patch_diff**, **changed_tests**,
   **maintainer_discussion**, root-cause summary. (issue trackers + MoreFixes + fix commits.)
5. **behavioral_model** — attacker-controlled input, trust boundary, missing/incorrect control,
   sensitive operation, **exploit_oracle**, **negative_control**, neighboring safe behavior.
6. **agent_guidance** — applicability signals, hypotheses, low-impact probes, evidence requirements,
   **false_positive_conditions**, stop conditions, prohibited actions.
7. **triage** — three *independent* labels: `technically_vulnerable`, `in_scope`, `reportable`, plus
   severity and reviewer reasoning.
8. **provenance** — sources, source versions, licenses, retrieved_at, content hashes, human reviewer.

## The five most important fields ★

Per José's brief, these are what make a bundle worth more than an H1 report:

| Field | Section | Why it matters |
|---|---|---|
| `negative_control` | behavioral_model | Teaches *actually-vulnerable vs patched/safe* — the anti-over-acceptance lever |
| `maintainer_discussion` | engineering_evidence | Reveals the evidence a triager demands before accepting |
| `patch_diff` | engineering_evidence | The root-cause motif; source of cross-project variants |
| `changed_tests` | engineering_evidence | The exploit oracle the developers themselves wrote |
| `false_positive_conditions` | agent_guidance | Encodes stop conditions → precision, not just recall |

## The three independent triage labels

A finding is only reportable if **all three** hold — but the agent must reason about them separately:

- `technically_vulnerable` — is there a real security defect?
- `in_scope` — is the asset/method inside the program's scope + rules?
- `reportable` — does the demonstrated impact meet the program's threshold?

Conflating these is a top cause of invalid submissions (see [`sources/08-negative-controls.md`](./sources/08-negative-controls.md)).

## Worked mini-example (IDOR, illustrative)

```yaml
case_id: CASE-000123
classification: { cwe_leaf: CWE-639, cwe_class: CWE-862, mapping_confidence: reviewed, alternative_mappings: [] }
environment:
  product: ExampleCommerce; framework: Rails 7; language: ruby; component: /api/v2/orders/{id}
  vulnerable_version: 2.3.0; fixed_version: 2.3.4
researcher_evidence:
  original_report: "https://hackerone.com/reports/EXAMPLE"
  reproduction: "authenticated user A requests order id belonging to user B → 200 + PII"
  demonstrated_impact: "cross-tenant PII read"; required_privileges: "any authenticated user"
  attack_preconditions: "know/guess a numeric order id"
engineering_evidence:
  vulnerable_repository: "github.com/example/commerce"; vulnerable_commit: "abc123"
  fix_commit: "def456"
  patch_diff: "adds `authorize! :read, order` before render"        # ★ motif: missing object-level check
  changed_tests: "spec asserts 403 when order.user != current_user"  # ★ oracle
  maintainer_discussion: "triager asked: does the mobile client send a tenant header? reporter: no"  # ★
  root_cause_summary: "controller trusted the id param without an ownership check"
behavioral_model:
  attacker_controlled_input: "order id path param"; trust_boundary: "authn present, authz absent"
  missing_or_incorrect_control: "object-level authorization"; sensitive_operation: "read order+PII"
  exploit_oracle: "200 with another tenant's data"
  negative_control: "v2.3.4 returns 403 for the same request"       # ★
  neighboring_safe_behavior: "/api/v2/invoices/{id} already calls authorize!"
agent_guidance:
  applicability_signals: ["numeric/sequential resource ids", "authn-only routes"]
  hypotheses: ["ownership check missing on sibling endpoints too"]
  low_impact_probes: ["request own id (baseline), then id±1 with own session"]
  evidence_requirements: ["two accounts", "diff of responses", "no destructive action"]
  false_positive_conditions: ["ids are UUIDv4 + server-side ACL", "tenant enforced at gateway"]  # ★
  stop_conditions: ["403/404 on cross-tenant id", "data is user's own after re-check"]
  prohibited_actions: ["no writes/deletes on others' objects", "respect rate limits + ID header"]
triage: { technically_vulnerable: true, in_scope: true, reportable: true, severity: high,
          reviewer_reasoning: "cross-tenant PII, low precondition, in scope" }
provenance:
  sources: ["h1:EXAMPLE", "github:example/commerce@def456"]; source_versions: ["MoreFixes v4"]
  licenses: ["MIT (repo)", "H1 disclosure terms"]; retrieved_at: "2026-07-22"
  content_hashes: ["sha256:..."]; human_reviewer: "jose"
```
