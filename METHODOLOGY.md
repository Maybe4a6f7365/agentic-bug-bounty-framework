# Our Bug Bounty Methodology — A Retrospective

## Purpose

This document records how we currently conduct bug bounty research, where the process has failed, and the controls we will use going forward.

The central lesson from our first seven targets is straightforward:

> Interesting behavior is not automatically a vulnerability. A report becomes viable only when we can demonstrate an unauthorized security outcome, reproduce it dynamically, explain the violated trust boundary, and rule out the most likely disqualifiers.

Our primary bottleneck is not discovery. It is converting observations into defensible, exploitable impact before submission.

## What we've built

| Metric | Count |
|--------|-------|
| **Targets researched** | 7 (Anthropic, Grindr, Yelp, Whatnot, Plaid, GitLab, CLEAR) |
| **Findings identified** | 16 (including walked/closed) |
| **Reported to H1** | 3 |
| **Bounties collected** | **0** |
| **Pipeline throughput** | ~8 days from target selection to first report |

These numbers show high reconnaissance throughput but no demonstrated bounty conversion. "Findings identified" must therefore be treated as a research activity metric, not a success metric. A healthy pipeline shows a **high self-kill rate and low submission count** — we close weak candidates before they become bad reports.

## The 3 reports we actually submitted

| Finding | Program | Result | Why it failed |
|---------|---------|--------|---------------|
| CCA-F1+F4 | Anthropic | **Informative** | Primary control = write-access gate. Sanitizer is best-effort. |
| YELP-F01 | Yelp | **Duplicate** | Program already knew about the WebView deep-link behavior. |
| PL-F01 | Plaid | **Submitted, pending** | Qualification review revealed self-test artifact; forged token rejected server-side. |

**Zero bounties from 3 submissions.** That's the honest score.

The failure modes differ:
- Anthropic failed on **security-boundary analysis**: the observed sanitizer behavior was not the primary authorization control.
- Yelp failed on **novelty**: the behavior was real and dynamically reproduced, but already known.
- Plaid exposed a **qualification problem**: the client-side behavior existed, but the proposed unauthorized outcome did not survive server-side validation.

These are not evidence-quality failures. They are failures to resolve exploitability, novelty, and control effectiveness before submission.

## The methodology pattern: what we actually do

Our historical workflow has been:

```
Session starts
  → Pick target (often from H1 program list)
  → Static recon (bundle inspection, API probing, subdomain enum)
  → Find something interesting (code path, endpoint, behavior)
  → Build evidence chain (file:line citations, request IDs)
  → Dispatch sub-agent(s) for independent validation (Codex + Claude)
  → Draft report
  → [Sometimes] Submit to H1
  → Result: Informative / Duplicate / Qualified
```

The problem is structural: exploitability, dynamic reproduction, duplicate checking, and policy qualification occur too late. By the time a disqualifier is found, substantial effort and confidence have already accumulated around the observation.

## The methodology pattern: what we will do

The revised workflow moves novelty, policy, dynamic validation, and impact ahead of report writing:

```
Session starts
  → Select one target using explicit target-selection criteria
  → Re-read scope, exclusions, safe-harbor terms, and testing constraints
  → Establish test accounts, roles, devices, traffic capture, and baselines
  → Perform dynamic surface mapping and request mutation
  → Use static analysis to explain or expand observed runtime behavior
  → Record an observation, not yet a vulnerability
  → Run a fast duplicate preflight
  → Define the exact unauthorized outcome and affected security principal
  → Identify the primary server-side or trust-boundary control
  → Attempt the exploit dynamically under realistic conditions
  → Test alternative explanations, downstream controls, and negative cases
  → Pass the Dynamic PoC Readiness Gate
  → Independently validate the evidence and impact claim
  → Calibrate severity from demonstrated impact
  → Run policy, duplicate, grading, and report-quality gates
  → Draft the report around impact and reproduction
  → Submit only if every mandatory gate passes
  → Record outcome, triage feedback, time spent, and lessons learned
  → Continue deep research on the same target
```

A candidate that fails a gate is not automatically discarded. It is classified accurately:

- **Observation:** interesting behavior without a demonstrated security consequence.
- **Hypothesis:** a plausible exploit path that still has unresolved assumptions.
- **Qualified finding:** dynamically reproduced unauthorized impact with major disqualifiers tested.
- **Report-ready finding:** a qualified finding that also passes novelty, policy, severity, evidence, and report-quality gates.
- **Closed:** impact disproved, intended behavior confirmed, duplicate strongly indicated, out of scope, or blocked by an effective control.
- **Parked:** potentially valid, but dynamic validation requires unavailable infrastructure or authorization.

This vocabulary prevents research notes from silently becoming "findings."

## Operating principles

1. **Impact precedes severity.** We first demonstrate what an attacker can cause or obtain. Only then do we assign a severity.
2. **Dynamic evidence precedes report prose.** Report writing cannot substitute for exploitation.
3. **Server-side outcomes outrank client-side behavior.** Client-side trust, validation, or routing behavior matters only if it changes an authoritative security outcome.
4. **Primary controls matter more than defense-in-depth controls.** A bypass of a secondary sanitizer is not exploitable if the actual authorization boundary still holds.
5. **Negative evidence is part of qualification.** Rejections, non-events, and failed variants help define the real boundary.
6. **Novelty is a gate, not an afterthought.** A valid vulnerability can still produce no bounty if it is already known.
7. **Depth compounds.** Knowledge of one target's roles, APIs, trust boundaries, and business logic is an asset that should be reused.
8. **Documentation volume does not increase impact.** A long evidence chain can establish confidence, but it cannot turn a configuration observation into a vulnerability.
9. **The strongest claim must match the strongest reproduced result.** Reports must not depend on untested escalation language.
10. **A clean decision to close a weak candidate is productive output.** Avoiding a bad submission protects time, credibility, and signal quality.

## What works

### 1. Multi-agent validation

We run Codex (GPT-5.6-sol, xhigh) and Claude Opus in parallel on the same evidence. They caught Max's fabricated RSA-2048 factoring claim. They independently verified F01's qualification issue. This is real value.

Independent validation is most useful when validators are given adversarial assignments rather than being asked only to confirm the original theory. At least one validator should attempt to disprove the finding by checking:

- Whether the behavior is intentional or documented.
- Whether the attacker already requires equivalent privilege.
- Whether a downstream control blocks the claimed outcome.
- Whether the result depends on a self-test artifact.
- Whether the affected data belongs to the attacker.
- Whether the proof demonstrates execution or merely reachability.
- Whether the claim exceeds the observed result.
- Whether the issue is likely known or excluded by policy.

Agreement between agents is not sufficient if both agents reason from the same unverified assumption. Independent validation should include independent reproduction whenever possible. **Assign one reviewer the explicit role of disproof.** Withhold the proposed severity during independent review. Prefer reproduction over textual agreement.

### 2. Evidence discipline

Every finding has request IDs, file:line citations, SHA-256 bundle hashes. When the Plaid triager asks "which bundle version?", we have the answer. When the Yelp triager says "duplicate", we have the exact request chain.

We should retain this discipline while distinguishing evidence types:

- **Existence evidence:** proves that code, an endpoint, or a behavior exists.
- **Reachability evidence:** proves that an attacker-controlled path can reach it.
- **Execution evidence:** proves that the target performs the relevant action.
- **Authorization evidence:** proves that the action crosses a security boundary.
- **Impact evidence:** proves harm to another user, tenant, system, or protected asset.
- **Novelty evidence:** supports that the issue is not obviously known.
- **Control evidence:** shows which defenses were tested and whether they held.

A report-ready finding needs more than existence and reachability evidence.

### 3. Repo infrastructure

contract.yaml, findings-manifest.json, handoffs/*_to_H1.yaml, OUTCOMES.md, standing_knowns.yaml — this structure makes findings reproducible and auditable. Max could pick up F02's runtime work because the playbook was exact.

The repository should also record the state of every qualification gate. Recommended fields include:

```yaml
finding_state: observation | hypothesis | qualified | report_ready | parked | closed
unauthorized_outcome:
attacker_prerequisites:
victim_requirements:
affected_principal:
primary_security_control:
control_test_result:
dynamic_poc_completed: false
dynamic_poc_reproductions: 0
negative_controls_completed: false
duplicate_preflight_completed: false
policy_re_reviewed: false
severity_calibrated_from_impact: false
independent_reproduction_completed: false
strongest_proven_claim:
unproven_claims: []
closure_reason:
```

### 4. Honest negative evidence

We record what DIDN'T work: the 400 rejection on F02's iframe URL, the 404s on CLEAR's endpoint discovery, the "Shape C never ran" admission. This prevents others from retracing bad paths.

Negative evidence should not be buried in notes. It should be used to narrow or disprove the claim. For each candidate, explicitly answer:

- Which payloads failed?
- Which roles or accounts were unaffected?
- Which downstream controls rejected the request?
- Which expected side effects did not occur?
- Does the failure invalidate the exploit, reduce its scope, or merely identify a constraint?
- Can the successful and unsuccessful cases be explained by the same security model?

## What doesn't work

### 1. We find code behavior, not vulnerabilities

The fundamental pattern: find something non-ideal → call it a finding → discover too late it's not exploitable.

The Anthropic sanitizer bypass was real but intentional. The Yelp WebView deep-link was real but already known. The Plaid postMessage was real but impact-limited (server blocks forged tokens). Max's RSA-2048 is real code but NIST says it's fine.

**The gap: We're excellent at finding interesting behavior and weak at proving exploitable impact.**

Every new candidate must begin with a falsifiable impact statement:

> As an attacker with **[minimum prerequisites]**, I can cause or obtain **[specific unauthorized outcome]** affecting **[another principal or protected asset]**, because **[primary security boundary]** can be crossed.

If we cannot fill in each field without vague language such as "could potentially," "may lead to," or "might allow," the item remains a hypothesis.

### 2. Static-before-dynamic bias

16 findings, and how many had live dynamic validation before report?
- YELP-F01: yes (live device)
- PL-F03: yes (sandbox SSRF confirmed)
- Everything else: static-only, static chain, or "dynamic pending"

The CLAUDE.md rule says "Dynamic PoC before submission" but we rarely follow it. Most findings are researched, drafted, and sometimes submitted with only static evidence.

Static analysis is valuable for discovering hidden paths, understanding client behavior, locating undocumented parameters, and explaining why a dynamic result occurs. It is not proof that:
- The deployed backend accepts the input.
- The code path is reachable in production.
- The attacker controls the relevant value.
- A victim can be affected.
- An authorization boundary is crossed.
- The behavior survives server-side validation.
- The vulnerable version is currently deployed.

The revised default is dynamic-first. Exceptions must be explicit, rare, and based on a program's willingness to accept source-only findings. "Dynamic pending" is a research status, not a submission status.

### 3. Duplicate-preflight is never done

A duplicate preflight must be completed and evidenced before submission. F02's pre-flight shows `duplicate_preflight_completed: false`. YELP-F01 was a duplicate. We don't check Hacktivity before submitting.

Duplicate preflight must occur twice:
1. **Fast preflight after discovery:** before significant qualification or writing effort.
2. **Final preflight before submission:** to catch newly disclosed reports and adjacent known issues.

Search terms should include: program and endpoint name, route/feature/product name, vulnerability class and close synonyms, error messages and distinctive response fields, mobile activity/intent/deep-link names, historical disclosures and changelogs, and similar reports affecting adjacent endpoints.

A duplicate search cannot guarantee novelty, but failing to perform one guarantees avoidable risk.

### 4. Severity inflates as the report grows

Initial assessment: "Interesting behavior, maybe Low." After 300 lines of evidence: "This is Medium-High." The report grows, the severity grows with it, but the actual impact hasn't changed. Max's RSA-2048 went from "config observation" to "Low-Medium vulnerability" through sheer documentation volume.

Severity must be assigned last and supported by the shortest accurate impact statement. If the impact statement is unchanged, additional citations do not justify a higher tier. **Record the first-pass severity in metadata. Upward drift requires new evidence, not more citations.**

Warning signs of severity inflation:
- Counting theoretical follow-on attacks that were not reproduced.
- Treating control bypass as impact without showing the protected action.
- Using "arbitrary" when only a constrained value is controlled.
- Treating attacker-owned data as victim data.
- Ignoring required victim interaction or privileged access.
- Assuming access to internal infrastructure from a sandbox-only result.
- Converting defense-in-depth weakness into authentication bypass.
- Using cryptographic concern without a realistic attack under the deployed parameters.
- Scoring confidentiality, integrity, or availability impact that was not observed.

### 5. We open too many targets

7 targets in ~8 days. That's a new target every day. Each target gets recon but rarely gets the deep dynamic work that produces real bounties. We're a mile wide and an inch deep.

New targets carry repeated setup costs: scope review, account creation, traffic baselining, role discovery, client acquisition, endpoint mapping, and business-logic learning. Switching targets before those costs compound into expertise suppresses the probability of discovering subtle authorization and workflow flaws.

A target should normally remain active for a defined research cycle — such as two weeks or a minimum of five focused sessions — unless an explicit exit condition is met.

## Additional failure modes to detect

### 1. The self-test artifact
**Pattern:** The apparent exploit works only because the attacker is also the sender, recipient, tenant owner, webhook owner, or data subject.
**Detection:** Repeat with separate attacker and victim accounts. Label every token, object, and session by owner. Confirm victim-side state independently. Ask: "Whose authorization produced the successful result?"

### 2. The downstream-control blind spot
**Pattern:** A client accepts attacker-controlled data, but the authoritative server rejects it before any protected action occurs.
**Detection:** Trace the input through every downstream request. Capture the final server response and resulting state. Identify whether the client, gateway, backend, or third party makes the final decision.

### 3. The defense-in-depth confusion
**Pattern:** A sanitizer, warning, client check, or secondary validator is bypassed, but the primary authorization control remains effective.
**Detection:** Name the primary security control explicitly. Test whether the protected action succeeds without legitimate authority. Close or downgrade the candidate if the bypass produces no additional capability.

### 4. The reachability-to-impact leap
**Pattern:** A code path is reachable, so the report assumes its most dangerous possible branch can be triggered.
**Detection:** Demonstrate the dangerous branch at runtime. Capture the side effect, not only the entry into the handler. Mark unexecuted branches as hypotheses.

### 5. The version mismatch
**Pattern:** The analyzed bundle or source contains a behavior not present in the deployed version.
**Detection:** Record bundle hashes and retrieval timestamps. Link static artifacts to live requests. Re-test immediately before submission.

### 6. The privilege-equivalence problem
**Pattern:** Exploitation requires a privilege that already grants the claimed outcome through intended functionality.
**Detection:** List the minimum attacker role and all permissions it already has. Compare the exploit outcome with documented capabilities. Reject claims where the exploit only offers an alternate route to an already authorized action.

### 7. The victimless impact claim
**Pattern:** The PoC affects only attacker-controlled accounts, data, hosts, or callbacks.
**Detection:** Identify the affected principal. Demonstrate cross-account, cross-tenant, or protected-system impact where safely permitted. If only attacker-owned assets are affected, explain why the program still suffers a security consequence.

### 8. The environmental overgeneralization
**Pattern:** Behavior reproduced in a sandbox, test tenant, rooted device, debug build, or local harness is generalized to production.
**Detection:** Record the environment beside every result. Identify which security controls differ across environments. Narrow the report if production equivalence cannot be established.

### 9. The report-first commitment trap (sunk-cost escalation)
**Pattern:** Once a long report exists, the team becomes reluctant to close the finding — even when new evidence undermines it.
**Detection:** Limit pre-qualification notes to a one-page evidence brief. Do not create the final report file until all mandatory gates pass. Have an independent reviewer decide whether the impact survives without reading the proposed severity. Track time spent after the first disconfirming result. If you've spent more time defending a finding than proving it, close it.

### 10. The chain-of-assumptions problem
**Pattern:** The impact requires several individually plausible but untested steps.
**Detection:** Create an assumption ledger:

| Step | Required condition | Dynamically proven? | Evidence | Result if false |
|------|--------------------|---------------------|----------|-----------------|
| 1 | Attacker controls input | Yes/No | Request ID | Chain fails/narrows |
| 2 | Victim processes input | Yes/No | Runtime trace | Chain fails/narrows |
| 3 | Backend accepts output | Yes/No | Response/state | Chain fails |
| 4 | Protected asset changes | Yes/No | Independent fetch | Impact proven/not proven |

Any critical "No" prevents report-ready status.

### 11. The AI consensus illusion
**Pattern:** Multiple agents agree because they inherited the same framing, incomplete evidence, or erroneous premise.
**Detection:** Assign one reviewer the explicit role of disproof. Withhold the proposed severity during independent review. Require reviewers to state assumptions separately. Prefer independent reproduction over textual agreement. Resolve disagreements through new evidence rather than majority vote.

### 12. The policy-boundary failure
**Pattern:** The technical issue may be valid, but the tested asset, technique, or impact is excluded.
**Detection:** Re-read policy immediately before testing and submission. Record the exact scope entry covering the asset. Record exclusions relevant to the vulnerability class. Do not expand testing beyond program authorization to strengthen impact.

## Target selection criteria

A good target is not merely recognizable or technically interesting. It should offer a realistic path to safe, dynamic, differentiated research.

### Good-target indicators

Score each item from 0 to 2:

| Criterion | 0 | 1 | 2 |
|----------|---|---|---|
| **Scope clarity** | Ambiguous or narrow | Mostly clear | Clear assets and rules |
| **Dynamic accessibility** | No usable access | Partial access | Accounts/devices/API readily testable |
| **Role diversity** | One self-only role | Limited role variation | Multiple users, tenants, or privilege levels |
| **Stateful workflows** | Mostly static/public | Some protected actions | Rich auth, sharing, payment, admin, or integration flows |
| **Traffic observability** | Opaque/pinned without path | Partial capture | Requests and state changes can be observed |
| **Impact verifiability** | Effects hard to prove | Indirectly observable | Independent before/after verification |
| **Program responsiveness** | Poor or unknown | Mixed | Consistent triage and clear bounty history |
| **Duplicate density** | Heavily researched | Moderate | Newer or less saturated surface |
| **Research leverage** | Little reusable knowledge | Some reuse | Existing tooling/domain expertise applies |
| **Safe testing feasibility** | High collateral risk | Manageable constraints | Isolated accounts and safe PoCs possible |

Interpretation: **16–20:** strong primary target. **11–15:** viable if it matches existing expertise. **6–10:** secondary target; time-box initial reconnaissance. **0–5:** poor target unless new access or scope changes.

### Good targets tend to have
- At least two controllable accounts or principals.
- Observable server-side state transitions.
- Multiple roles, tenants, integrations, or object-ownership boundaries.
- Accessible APIs and reproducible workflows.
- Features involving invitations, sharing, webhooks, imports, exports, identity, payments, moderation, or administrative actions.
- A program history showing that the relevant vulnerability classes are rewarded.

### Bad targets tend to have
- Static-only surfaces with no meaningful state.
- No way to create accounts or compare principals.
- Heavy dependence on unavailable hardware, geography, credentials, or third-party approval.
- Extremely narrow scope combined with broad exclusions.
- A mature, heavily disclosed surface with no differentiated research angle.
- Client-only behavior whose server-side consequence cannot be observed.

### Target entry checklist
- [ ] Scope and exclusions have been read and recorded.
- [ ] At least one promising trust boundary has been identified.
- [ ] Required accounts, roles, applications, and devices are available.
- [ ] Safe dynamic testing is possible.
- [ ] Public disclosures and duplicate density have been sampled.
- [ ] A minimum research cycle has been allocated.
- [ ] An exit condition has been defined.
- [ ] Opening this target does not violate the active-target limit.

### Target exit conditions
Pause or close a target when:
- Required access cannot be obtained within the time box.
- Dynamic validation is structurally impossible.
- The accessible surface lacks meaningful trust boundaries.
- Duplicate density is too high for the available research angle.
- Policy exclusions cover the most promising classes.
- The target produces no qualified hypotheses after the agreed number of focused sessions.

Do not exit merely because the first hypotheses fail. Failed hypotheses often improve the mental model that enables later business-logic findings.

## Research focus model

Maintain no more than:
- **One primary target:** receives most research time.
- **One secondary target:** used when the primary target is blocked.
- **One maintenance target:** only for pending triage, regression checks, or previously qualified findings.

All other targets should be marked paused. A pending report does not justify continuously opening new programs.

Suggested time allocation: 70% primary target dynamic research, 20% qualification and report work, 10% secondary target or tooling.

## The "should I report this?" decision tree

```
START: I observed interesting behavior
  |
  v
Is the asset and testing method in scope?
  |-- No  → Stop testing; document and close as policy-ineligible.
  |-- Unclear → Resolve policy ambiguity before continuing.
  |-- Yes
  v
Can I state a specific unauthorized outcome?
  |-- No  → Keep as an observation; do not draft a report.
  |-- Yes
  v
Does the attacker gain a net-new capability?
  |-- No  → Close as intended/privilege-equivalent behavior.
  |-- Yes
  v
Is another principal, protected asset, or platform control affected?
  |-- No  → Test whether any program-level impact exists.
  |          |-- None → Close or downgrade.
  |-- Yes
  v
Did I perform a fast duplicate preflight?
  |-- No  → Search before spending more time.
  |-- Strong duplicate evidence → Close or seek a distinct root cause/impact.
  |-- No strong match
  v
Can the exploit be reproduced dynamically?
  |-- No, access/tooling missing → Park with exact unblock requirements.
  |-- No, behavior fails → Record negative evidence; revise or close.
  |-- Yes
  v
Did the authoritative system accept the action or expose the data?
  |-- No  → A downstream control holds; revise or close.
  |-- Yes
  v
Was the result reproduced with separated attacker/victim principals?
  |-- No  → Treat as possible self-test artifact; repeat correctly.
  |-- Not applicable, with justification
  |-- Yes
  v
Does the impact survive negative controls and alternative explanations?
  |-- No  → Narrow the claim or close.
  |-- Yes
  v
Can a second reviewer reproduce or validate the impact independently?
  |-- No  → Resolve the disagreement or reproducibility failure.
  |-- Yes
  v
Does the claimed severity follow only from demonstrated impact?
  |-- No  → Recalibrate and remove speculative escalation.
  |-- Yes
  v
Did final policy and duplicate checks pass?
  |-- No  → Do not submit.
  |-- Yes
  v
Does the report-quality score meet the submission threshold?
  |-- No  → Repair the identified deficiencies.
  |-- Yes
  v
SUBMIT
```

## Dynamic PoC Readiness Gate

No report is written or submitted until this gate passes, except where a program explicitly accepts source-only findings and the exception is documented.

### Mandatory readiness criteria

- [ ] **In-scope environment:** Tested against an in-scope asset or demonstrably equivalent environment.
- [ ] **Minimum attacker model:** PoC uses the lowest verified privilege required.
- [ ] **Principal separation:** Attacker and victim accounts, tenants, sessions, tokens, and objects are clearly separated.
- [ ] **Attacker control:** The exact attacker-controlled input is shown.
- [ ] **Runtime execution:** The target actually processes the input through the claimed path.
- [ ] **Authoritative outcome:** The server or other authoritative component accepts the action, discloses the data, or changes protected state.
- [ ] **Independent verification:** The outcome is verified through a separate fetch, session, account, log, or state check — not only through the initiating response.
- [ ] **Reproducibility:** The successful result occurs at least twice, unless repetition would be unsafe. **Run the clean-state re-run to catch self-test artifacts like PL-F01.**
- [ ] **Negative control:** A nearby non-exploit case fails as expected, showing that the success is meaningful.
- [ ] **Primary control tested:** The actual authorization or trust-boundary control is identified and shown to fail.
- [ ] **Downstream controls tested:** Relevant server-side validation, token checks, sanitizers, allowlists, and final consumers have been evaluated.
- [ ] **No self-test artifact:** The result does not depend solely on attacker-owned data or authority.
- [ ] **Impact bounded:** The report distinguishes proven scope from theoretical maximum scope.
- [ ] **Safe reproduction:** The PoC avoids unnecessary access, persistence, disruption, or third-party harm.
- [ ] **Evidence preserved:** Requests, responses, timestamps, versions, hashes, and cleanup steps are recorded.

### Gate result

- **Pass:** Dynamic exploitation and impact are demonstrated.
- **Conditional pass:** One non-critical criterion is inapplicable and the reason is documented.
- **Fail—continue research:** The hypothesis remains plausible, but critical runtime evidence is missing.
- **Fail—close:** An effective control or incorrect assumption defeats the claimed outcome.
- **Parked:** Validation requires access, hardware, authorization, or environment not currently available.

"Client accepted the value," "handler was invoked," "endpoint returned 200," and "callback received a request" do not independently prove impact. The protected outcome must be verified.

## Severity calibration checklist

Severity is assigned only after the Dynamic PoC Readiness Gate passes.

### Step 1: State the proven impact in one sentence
> With **[attacker prerequisites]**, an attacker can **[proven action]** against **[affected principal or asset]**, resulting in **[observed confidentiality, integrity, or availability impact]**.

If the sentence relies on "could," split proven impact from potential escalation.

### Step 2: Calibrate prerequisites
- [ ] Does the attacker need authentication?
- [ ] Does the attacker need a paid, verified, employee, partner, or administrative account?
- [ ] Does the required role already possess equivalent authority?
- [ ] Is access to a victim identifier, token, link, device, network, or tenant required?
- [ ] Is social engineering or victim interaction necessary?
- [ ] Does exploitation depend on a race, rare state, legacy version, or non-default configuration?

### Step 3: Calibrate affected scope
- [ ] Is the impact self-only, single-victim, cross-account, cross-tenant, or platform-wide?
- [ ] Is the affected data sensitive, regulated, secret, or already public?
- [ ] Are rate limits, object entropy, or workflow constraints material?
- [ ] Has the claimed scale been demonstrated or only inferred?

### Step 4: Calibrate control bypass
- [ ] Which primary security boundary failed?
- [ ] Is the issue authentication, authorization, isolation, origin trust, cryptographic verification, or business logic?
- [ ] Did only a secondary defense fail?
- [ ] Does a downstream control limit or eliminate the result?

### Step 5: Remove speculative impact
- [ ] Do not claim account takeover unless account control was demonstrated.
- [ ] Do not claim remote code execution from injection without execution.
- [ ] Do not claim internal network access from a single controlled callback.
- [ ] Do not claim arbitrary file/data access from one fixed resource.
- [ ] Do not claim authentication bypass if a valid authenticated session is still required.
- [ ] Do not claim cryptographic compromise without a feasible attack against deployed parameters.
- [ ] Do not claim broad cross-tenant impact from attacker-owned tenant behavior.
- [ ] Do not count chained impact unless every critical link is proven.

### Step 6: Sanity-check the tier
- Would the same severity remain if the report were only one page long?
- What is the strongest claim directly demonstrated by the PoC?
- What is the weakest assumption required for the proposed severity?
- Would removing theoretical escalation reduce the tier?
- Does the program's published severity taxonomy support this classification?
- How have comparable accepted reports been rated?

Record both:
```yaml
proven_severity:
maximum_theoretical_severity:
severity_limiter:
```

The submitted severity should follow the proven result, not the maximum theoretical chain.

## Duplicate-preflight procedure

### Fast preflight (before >30–60 min invested)
- Search Hacktivity and public disclosures.
- Search endpoint, feature, class, handler, and error names.
- Search the vulnerability class plus the program name.
- Search related mobile activities, intents, schemes, or integration names.
- Review program changelogs and known limitations where relevant.
- Record queries and the closest matches.

### Final preflight (immediately before submission)
- Repeat searches using the final root-cause and impact wording.
- Review recent disclosures since the fast preflight.
- Compare the candidate against adjacent known issues.
- Explain why the finding is distinct from the closest match.
- Set `duplicate_preflight_completed: true` only after recording evidence.

A finding should not be abandoned solely because a similar class exists. Determine whether the root cause, affected asset, exploit path, or impact is materially distinct.

## Report quality self-assessment

Score each category from 0 to 2 (0 = missing, 1 = incomplete, 2 = clear and reproducible):

| Category | 0–2 | Question |
|----------|-----|----------|
| **Scope and policy** | | Is the asset in scope and the testing method permitted? |
| **Impact statement** | | Is the unauthorized outcome specific and proven? |
| **Attacker model** | | Are minimum prerequisites and existing privileges clear? |
| **Principal separation** | | Are attacker, victim, tenant, token, and object ownership unambiguous? |
| **Dynamic reproduction** | | Does the PoC execute against the relevant live environment? |
| **Authoritative result** | | Is the final server-side or protected-state outcome verified? |
| **Primary control failure** | | Does the report identify the actual failed security boundary? |
| **Negative controls** | | Are failed variants and limiting controls documented? |
| **Reproducibility** | | Can a triager follow concise steps and obtain the same result? |
| **Evidence quality** | | Are requests, responses, versions, timestamps, and artifacts sufficient? |
| **Novelty preflight** | | Was a documented duplicate search completed? |
| **Severity calibration** | | Does severity follow from demonstrated impact without speculation? |
| **Policy re-review** | | Was scope and policy checked again before submission? |
| **Independent validation** | | Did another reviewer attempt reproduction or disproof? |
| **Report clarity** | | Does the report lead with impact and avoid irrelevant evidence? |

Maximum score: **30**

### Submission thresholds
- **27–30:** report-ready, assuming all mandatory gates pass.
- **23–26:** revise before submission.
- **18–22:** incomplete qualification; return to testing.
- **0–17:** observation or hypothesis, not a report.

A high total cannot compensate for a zero in any mandatory category: Scope and policy, Impact statement, Dynamic reproduction, Authoritative result, Novelty preflight, Policy re-review.

### Final adversarial questions
Before submitting, a reviewer who did not author the report should answer:

1. What exact action is unauthorized?
2. Who is harmed?
3. What proof shows the result is not self-inflicted?
4. Which authoritative control failed?
5. Which control could still make the claim false?
6. What is the strongest result reproduced — not inferred?
7. What attacker privilege is required?
8. Is that privilege equivalent to the claimed capability?
9. Why is this not intended behavior?
10. Why is this not an obvious duplicate?
11. Which sentence in the report overstates the evidence?
12. What would a skeptical triager classify as Informative, and why?

Any unanswered question returns the candidate to qualification.

## Metrics to track

The objective is not merely to increase submissions. It is to increase the proportion of research time that produces qualified, novel, dynamically proven impact. **A healthy pipeline shows a high self-kill rate.** Closing weak candidates early is a success metric, not a failure.

### Funnel metrics

| Metric | Definition |
|--------|------------|
| **Observations created** | Interesting behaviors recorded before qualification |
| **Hypotheses formed** | Observations with a concrete unauthorized-outcome theory |
| **Dynamic PoCs attempted** | Hypotheses tested at runtime |
| **Dynamic PoCs successful** | Attempts producing the expected security outcome |
| **Qualified findings** | Candidates passing the Dynamic PoC Readiness Gate |
| **Report-ready findings** | Qualified findings passing all remaining gates |
| **Reports submitted** | Actual external submissions |
| **Valid reports** | Reports accepted as valid |
| **Unique accepted reports** | Valid, non-duplicate reports |
| **Bounties awarded** | Reports receiving monetary reward |
| **Self-killed candidates** | Hypotheses closed before submission (positive metric) |

### Conversion rates

```
Hypothesis rate = hypotheses / observations
Dynamic attempt rate = dynamic PoCs attempted / hypotheses
Dynamic success rate = successful dynamic PoCs / dynamic PoCs attempted
Qualification rate = qualified findings / hypotheses
Submission precision = valid reports / reports submitted
Novelty precision = unique accepted reports / reports submitted
Bounty conversion = bounties awarded / reports submitted
Self-kill rate = candidates closed before submission / hypotheses (target: high)
Qualification-to-writing ratio = hours proving/disproving / hours drafting (target: >1)
```

### Time metrics
Track median and total hours for: target setup, dynamic surface mapping, static analysis, hypothesis formation, dynamic qualification, duplicate preflight, independent validation, report writing, triage response, time spent on candidates ultimately closed, time from observation to first dynamic test, time from qualified finding to submission.

### Operating targets (until baseline data exists)

- **100%** of submissions pass the Dynamic PoC Readiness Gate.
- **100%** complete final duplicate and policy preflight.
- **100%** include a specific unauthorized-outcome statement.
- **100%** identify the primary security control.
- **100%** include negative evidence or an explicit reason it is inapplicable.
- **90%+** receive independent adversarial review.
- **80%+** of hypotheses receive a dynamic test or documented access blocker.
- **≤3** active targets at once.
- **≥5** focused sessions on the primary target before voluntary switching.
- **≥27/30** report-quality score for every submission.
- **0** submissions labeled "dynamic pending."
- **0** severity claims based solely on theoretical chaining.
- **0** reports written before the mandatory dynamic gate passes.

These targets should be revisited after 10 additional qualified findings or 5 additional submissions.

## Session-level operating checklist

### Start of session
- [ ] Confirm the primary target.
- [ ] Review scope changes and recent disclosures.
- [ ] Select one trust boundary or workflow to test.
- [ ] Define the session's dynamic objective.
- [ ] Confirm accounts, roles, proxying, logging, and cleanup.
- [ ] Review unresolved hypotheses and negative evidence.

### During research
- [ ] Label observations separately from findings.
- [ ] Move quickly from observation to falsifiable impact hypothesis.
- [ ] Test with separated principals.
- [ ] Capture the authoritative outcome.
- [ ] Record failed payloads and effective controls.
- [ ] Use static analysis to explain runtime results.
- [ ] Stop writing report prose until qualification passes.

### End of session
- [ ] Update each candidate's state.
- [ ] Record time by activity.
- [ ] Record the strongest proven claim.
- [ ] Record unresolved assumptions and the next falsifying test.
- [ ] Close disproven hypotheses explicitly.
- [ ] Preserve requests, responses, hashes, versions, and cleanup evidence.
- [ ] Decide whether the next session deepens the same target.

## What the winners do differently

Top H1 researchers who actually collect bounties share these patterns:

1. **One target, deep.** They pick one program and stay for weeks. They know the auth flows, the API surface, the codebase. They find the 10th bug in the same endpoint, not the 1st bug in 10 endpoints.

2. **Dynamic first.** They set up a test account, capture all traffic, and start manipulating requests immediately. Static analysis comes after, to explain what they found dynamically.

3. **Impact-first framing.** They don't write "the code at line X does Y." They write "I can access another user's verification data without their credentials." Impact → evidence, not evidence → impact.

4. **Duplicate check before writing.** They search Hacktivity for the endpoint name, the vulnerability class, the error message. If it's been reported, they move on immediately instead of spending 4 hours on a report.

5. **One submission per session.** Quality over quantity. A single well-documented Critical with dynamic PoC beats 5 static-only Mediums.

We should treat these not as stylistic preferences but as operational constraints. Depth reduces setup costs, dynamic testing resolves assumptions, impact-first framing prevents evidence inflation, duplicate checks protect time, and submission restraint preserves signal quality.

## Recommendations for going forward

### Immediate (next session)
- [ ] Do a Hacktivity duplicate check on EVERY finding BEFORE writing the report.
- [ ] For PL-F03: retain as a validated SSRF primitive/hypothesis. Qualify the internal-resource effect or keep as a limited reachability finding.
- [ ] Stop opening new targets. Close CLEAR/Epic for now. Focus on the 3 we have live.
- [ ] Reclassify every current item as observation, hypothesis, qualified, report-ready, parked, or closed.
- [ ] Record the strongest proven claim and remaining critical assumption for each active item.

### Short-term (this week)
- [ ] Get dynamic validation for at least 1 finding (GR-F2/F3 need ADB device; PL-F01 needs qualification resolution).
- [ ] Max: refactor GitLab F-D2 into "validator has no minimum bit-length" (the honest finding).
- [ ] Run the pre-flight checklist (grading_complete, policy_re_reviewed, duplicate_preflight) on EVERY draft.
- [ ] Establish attacker/victim account pairs for each active program where policy permits.
- [ ] Calculate baseline funnel and time metrics from the existing 16 findings.
- [ ] Assign an independent reviewer to disprove, not merely confirm, every qualified finding.

### Process change
- [ ] New rule: **No report written until dynamic PoC exists.** (Enforce the CLAUDE.md rule we already have.)
- [ ] New rule: **Severity assigned LAST, not first.** Impact is demonstrated → then we ask "what tier does this hit?"
- [ ] New rule: **Hacktivity check is step 1 of every finding.** Not step 9.
- [ ] New rule: **Every finding begins as an observation.** It earns promotion through explicit gates.
- [ ] New rule: **Every impact claim names the affected principal and primary failed control.**
- [ ] New rule: **Every successful PoC includes an authoritative state check and a negative control.**
- [ ] New rule: **No more than three targets may be active, with only one primary target.**
- [ ] New rule: **Independent review must attempt disproof and identify shared assumptions.**
- [ ] New rule: **A self-assessment score below 27/30 blocks submission.**
- [ ] New rule: **A mandatory-category score of zero blocks submission regardless of total score.**
- [ ] New rule: **Unproven escalation is labeled as future research, not submitted as impact.**

## Definition of success

The next phase should not be judged by how many endpoints, bundles, or interesting behaviors we discover. It should be judged by whether we improve these outcomes:

- More hypotheses are tested dynamically.
- Weak candidates are closed earlier.
- Qualified findings survive adversarial review.
- Fewer submissions are Informative, out of scope, or non-reproducible.
- Duplicate risk is reduced before report-writing time is spent.
- Severity matches the proven result.
- Research compounds on a small number of targets.
- Accepted, unique reports and collected bounties increase.

The immediate goal is not to maximize submission count. It is to make every submission the final step of qualification rather than the mechanism by which qualification occurs.

## Final submission contract

A report may be submitted only when all of the following are true:

```yaml
scope_confirmed: true
testing_method_permitted: true
unauthorized_outcome_specific: true
affected_principal_identified: true
minimum_attacker_prerequisites_recorded: true
net_new_capability_demonstrated: true
primary_security_control_identified: true
dynamic_poc_completed: true
authoritative_outcome_verified: true
principal_separation_verified: true
negative_controls_completed: true
downstream_controls_tested: true
reproduced_or_safety_exception_documented: true
independent_adversarial_review_completed: true
severity_calibrated_from_proven_impact: true
policy_re_reviewed: true
duplicate_preflight_completed: true
grading_complete: true
report_quality_score_gte_27: true
speculative_claims_removed_or_labeled: true
```

If any mandatory value is false, the candidate remains in research. Submission is not a substitute for answering the unresolved question.
