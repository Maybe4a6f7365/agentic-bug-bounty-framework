---
name: patch-review-hunter
description: Evaluate whether a security patch is complete by analyzing the diff, sibling code paths, and patch-bypass patterns. Load when reviewing a CVE fix commit, when a patch diff appears in the hunter's context, or when triaging whether already-patched means actually-fixed. Triggers — review this security patch, is this CVE fix complete, patch bypass, incomplete fix, verify the fix.
---

# Patch-Review Hunter

Reconstruct the original security invariant, then test whether the patch enforces it on every reachable equivalent path. Treat the diff as a lead, not proof: changed lines show maintainer intent but do not establish complete coverage. Keep verified facts, code-derived inferences, and untested hypotheses separate. Static review can rank bypasses; only controlled dynamic testing can validate exploitability.

## What you need from a patch

- Original advisory: CVE/GHSA identifier or bug report, affected behavior, impact, and stated affected range.
- Patch diff or a locally available fixed commit SHA, including renames and surrounding context.
- Commit message and parent revision so removed behavior can be reconstructed accurately.
- Optional original vulnerable-code path, entry point, sink, and known proof of concept.
- Optional maintainer discussion in the issue/PR explaining the intended invariant and rejected alternatives.
- Optional sibling endpoint, versioned route, platform adapter, decoder, renderer, or call-site list.

If a required artifact is absent, say so. Do not invent an advisory, commit, endpoint, or deployment claim. Never fetch a private or embargoed patch without authorization.

## Review workflow

1. State the original bug as `attacker input → transforms → missing/broken control → sink → impact`.
2. Build a file-by-file change ledger: removed vulnerable code, introduced guard, ordering change, tests, and unchanged dependencies.
3. Name the security invariant independently of the implementation, such as `canonical(result) remains under canonical(root)`.
4. Search the repository for the old sink, old guard, route aliases, copied handlers, shared helpers, and equivalent transforms.
5. Compare patched and sibling paths from input through every decode/normalize step to the final sink.
6. Run safe negative and adversarial controls where authorized; record exact oracle and environment.
7. Return `Complete`, `Incomplete`, or `Suspicious—but needs deeper investigation`, with confidence and missing evidence.

## Recon signals

- One handler or file changes although the vulnerable helper, sink, or route pattern has multiple callers.
- A denylist adds one spelling, delimiter, tag, scheme, host, or header instead of enforcing a positive invariant.
- Validation is added before decoding, normalization, path joining, redirect following, template rendering, or type coercion.
- A check and its use remain separate operations over mutable filesystem, database, cache, authorization, or process state.
- Only `/v1/`, one HTTP method, one serializer, one platform branch, or one privilege role receives the new control.
- The patch changes visible output but not the dangerous sink, browser execution context, authorization decision, or side effect.
- New tests cover the reported payload only; encoded, alternate-separator, sibling-route, concurrency, and negative controls are absent.
- Tests assert status alone rather than owner identity, canonical destination, response body, security header, or read-after-write.
- A shared helper changes, but callers override, bypass, re-decode, or mutate its supposedly safe result afterward.
- Comments and commit message claim broader protection than the changed call graph supports.
- The patch catches an exception or returns a generic response while the protected action still occurs asynchronously.
- Platform-sensitive code handles POSIX `/` but not Windows `\`, drive-relative paths, UNC paths, or case folding.

## Test recipes

Run dynamic examples only against a local instance or an explicitly authorized target. Replace all placeholders with disposable canaries.

### Incomplete blocklist — alternate path separator

Check whether a traversal fix rejects the reported `../` spelling but misses Windows or mixed separators.

```python
import requests

for value in ("../outside.txt", r"..\outside.txt", r"..%5coutside.txt"):
    r = requests.get("<BASE>/download", params={"file": value}, timeout=10)
    print(value, r.status_code, r.text[:80])
```

**What to look for:** a literal `"../" in value`, regex over `/` only, or `replace("../", "")` without canonical containment.

**Bypass hypothesis:** `..\` or `%5c` reaches the same filesystem sink on a Windows-aware layer while avoiding the new string match.

### Sibling endpoint left unpatched

Compare the fixed handler with every route that loads or mutates the same object type.

```bash
curl -i -H 'Authorization: Bearer <A_TOKEN>' \
  '<BASE>/api/users/<B_CONTROLLED_ID>'
curl -i -H 'Authorization: Bearer <A_TOKEN>' \
  '<BASE>/api/admin/users/<B_CONTROLLED_ID>'
```

**What to look for:** authorization middleware added to one router, while an admin, export, preview, bulk, or alternate-method handler calls the same lookup without it.

**Bypass hypothesis:** the fixed route denies A, but the sibling returns B's controlled canary or performs a reversible action under A's session.

### Race window remains after the patch

Determine whether the patch narrows a time-of-check/time-of-use window without making the operation atomic.

```python
from concurrent.futures import ThreadPoolExecutor
import requests

def attempt(_):
    return requests.post("<BASE>/claim", json={"id": "<CANARY_ID>"}, timeout=10).status_code

with ThreadPoolExecutor(max_workers=8) as pool:
    print(list(pool.map(attempt, range(24))))
```

**What to look for:** `exists()` then `open()`, balance read then write, authorization check then queued use, or locks that do not span the transaction/sink.

**Bypass hypothesis:** concurrent requests alter state between the strengthened check and use, producing duplicate effects or use of a substituted controlled resource.

### Normalization gap — canonicalize after check

Trace the exact order of validation, joining, normalization, and sink invocation.

```python
import requests

for value in ("safe/file.txt", "safe/../outside.txt", "safe%2f..%2foutside.txt"):
    r = requests.get("<BASE>/asset/" + value, timeout=10)
    print(value, r.status_code, r.text[:80])
```

**What to look for:** prefix/extension/host checks on raw input followed by `resolve`, `normpath`, URL parsing, redirect following, Unicode folding, or archive extraction.

**Bypass hypothesis:** a raw value satisfies the guard, then canonicalizes into a forbidden destination before the sink uses it.

### Decoder bypass — single versus double encoding

Count decode boundaries across proxy, framework, router, application, and downstream service.

```bash
curl --path-as-is -i '<BASE>/asset/%2e%2e%2foutside.txt'
curl --path-as-is -i '<BASE>/asset/%252e%252e%252foutside.txt'
```

**What to look for:** one explicit decode before validation plus an implicit decode later, or a test that exercises only the advisory's single-encoded payload.

**Bypass hypothesis:** the guard sees `%2e%2e%2f` after one decode as harmless text; a later layer decodes it to `../` before the sink.

### Same root sink on an alternate path or version

Search all callers of the vulnerable sink/helper and compare `/v1/`, `/v2/`, legacy, mobile, GraphQL, batch, and internal adapters.

```bash
for route in v1/files v2/files legacy/files; do
  curl -sS -o /tmp/patch-review-body -w "$route %{http_code}\n" \
    "<BASE>/$route?name=<CONTROLLED_PROBE>"
done
```

**What to look for:** the new filter is local to a controller while another controller reaches the same query, renderer, deserializer, or filesystem call.

**Bypass hypothesis:** the alternate route accepts the same safe canary payload and reaches the unchanged root sink without the patch guard.

### Missing browser defense after an XSS/content patch

Separate correct contextual output handling from defense-in-depth response headers.

```bash
curl -sSI '<BASE>/controlled-preview' | \
  awk 'BEGIN{IGNORECASE=1}/content-security-policy|x-frame-options|content-type/'
```

**What to look for:** HTML replacement/escaping in one renderer, unsafe adjacent sinks, missing or report-only CSP, absent framing policy where clickjacking matters, or content sniffing ambiguity.

**Bypass hypothesis:** a sibling renderer or execution context still interprets controlled content; a missing CSP alone is usually hardening debt, not proof the XSS patch failed.

### Regression-test coverage audit

Map every changed security branch and proposed bypass to a test assertion; run the narrow suite if available.

```bash
git diff --name-only <PARENT> <FIX> | rg '(^|/)(test|tests|spec|specs)(/|_)'
rg -n 'outside|double|encoded|admin|v2|concurrent|Content-Security-Policy' \
  test tests spec specs 2>/dev/null
```

**What to look for:** no regression test, tests only for the original literal payload, skipped/platform-gated tests, snapshots without security assertions, or mocks that bypass the real transform/sink.

**Bypass hypothesis:** an untested equivalent representation or call path regresses silently; absence of tests raises suspicion but does not itself prove exploitability.

## Detection signals

- The patched payload is denied, while an equivalent alternate encoding/separator reaches the same controlled outside-root canary.
- `/api/users/<id>` denies A, but `/api/admin/users/<id>` returns B's controlled private marker or permits a reversible B-side change.
- Logs or tracing show the checked value/destination differs from the value/destination consumed by the sink.
- Concurrent controlled attempts violate a uniqueness, balance, ownership, or single-use invariant after the patch.
- An alternate version, method, renderer, serializer, platform branch, or worker reaches the same root sink without the new guard.
- The response still executes controlled script in the relevant browser context; missing CSP without execution is not a successful bypass.
- A new regression test fails on the fixed revision and passes after applying the proposed invariant-level correction.
- Results survive clean restart and include patched-payload, invalid-input, unauthenticated, and non-existent-object controls.

## Verdict

Return exactly one primary verdict:

- `Complete`: the invariant is enforced before the sink across all identified equivalent paths, adversarial controls fail safely, and regression tests cover the root cause.
- `Incomplete`: at least one authorized, reproducible equivalent path violates the same invariant after the patch.
- `Suspicious—but needs deeper investigation`: static evidence exposes a credible gap, but reachability, target deployment, or an impact oracle is not yet proven.

Include: original bug, file-by-file change ledger, unchanged attack surface, test-coverage matrix, bypass hypothesis, minimal reproducer, observed/expected result, three-label split, confidence, and missing evidence. Never upgrade `Suspicious` to `Incomplete` from code resemblance alone.

After completing the review, explore adjacent patch surface the checklist did not cover — the
skill is a floor, not a ceiling.

## Stop conditions (verified negatives)

See [`skills/references/negative-control-taxonomy.md`](../references/negative-control-taxonomy.md) for the full 12-category taxonomy. Apply ALL applicable labels. These conditions stop submission, not analysis.

**Decision split (apply separately, never collapse):**
- `technically_vulnerable`: does a post-patch reachable path actually violate the security invariant?
- `in_scope`: does the program policy cover the tested asset and method?
- `program_reportable`: does demonstrated impact meet the program threshold?

A result may be `yes/yes/no`, `yes/no/yes`, or `no/yes/yes`; do not submit on code suspicion or `technically_vulnerable` alone.

- `[expected_product_behavior]` The patch is intentionally narrow because the allegedly omitted path is public, trusted-only, or designed to accept the behavior; document the contract.
- `[control_exists_elsewhere]` A gateway, shared middleware, canonical sink wrapper, transaction, or browser policy enforces the same invariant on the sibling path; verify it with a negative control.
- `[vulnerable_third_party_but_target_not_affected]` The patch fixes a library function, but the target never calls the affected function with attacker-controlled data or wraps it with an effective control.
- `[theoretical_without_oracle]` The bypass is only a plausible code path; no controlled read, write, execution, race invariant, or other impact oracle reproduces.
- `[real_but_below_program_impact_threshold]` The bypass reaches only public/attacker-owned content or harmless hardening debt without the program's required security impact.
- `[duplicate_root_cause]` The same omitted path/root cause is already fixed or tracked elsewhere; correlate history and do not repackage it as a new bypass.
- `[out_of_scope_asset]` The incomplete patch exists only on an explicitly excluded asset, version, fork, deployment, or test method.
- `[patched_version]` The tested target includes a follow-up fix not present in the reviewed commit; verify deployed code/behavior rather than assuming the first patch is current.
- `[missing_attacker_control]` All values reaching the suspected gap are server-derived or restricted to a trusted principal in the actual target.
- `[missing_security_boundary]` The alternate path intentionally exposes the resource/action and no distinct principal, tenant, origin, or containment boundary was promised.
- `[technically_not_vulnerable]` The sibling path, decode chain, or race candidate preserves the invariant under controlled testing despite suspicious static similarity.
- `[prohibited_test_method]` Validation would require banned scanning, brute force, destructive racing, real-user access, or non-consensual exploitation; stop and propose a safe canary test.

## Anti-patterns

- Do not accept a patch as complete because a maintainer authored, reviewed, or released it.
- Do not equate a small diff with either safety or incompleteness; inspect the invariant and call graph.
- Do not submit a bypass hypothesis without a controlled reproducer and impact oracle.
- Do not treat scanner output, grep hits, status codes, crashes, or missing headers alone as bypass evidence.
- Do not test real user data, destructive races, production filesystem escapes, or prohibited automation.
- Do not mutate several variables at once; preserve causal comparison with one delta per probe.
- Do not confuse a distinct bug class near the patch with bypass of the patched root cause.
- Do not assume absence of a test proves vulnerability or presence of a test proves completeness.

## Minimal reproducer

This static triage helper accepts a unified diff and an optional original source file. It emits review hypotheses, not findings.

```python
#!/usr/bin/env python3
import argparse
import pathlib
import re

RULES = {
    "literal traversal blocklist may miss alternate separators":
        r'\+.*(?:\.\./|replace\([^\n]*\.\./|startswith\([^\n]*\.\./)',
    "validation may precede decoding or normalization":
        r'\+.*(?:decode|unquote|normalize|normpath|resolve|realpath)',
    "security-sensitive check/use sequence needs atomicity review":
        r'\+.*(?:exists|access|authorize|permission|balance|used_at)',
    "route-local fix may leave sibling endpoints":
        r'\+.*(?:route|router|endpoint|/v1/|/v2/|admin)',
    "XSS fix may lack contextual/browser-policy coverage":
        r'\+.*(?:escape|sanitize|innerHTML|Content-Security-Policy|X-Frame-Options)',
}

def added_text(diff):
    return "\n".join(line for line in diff.splitlines()
                     if line.startswith("+") and not line.startswith("+++"))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("diff", type=pathlib.Path)
    parser.add_argument("--original", type=pathlib.Path)
    args = parser.parse_args()
    diff = args.diff.read_text(errors="replace")
    corpus = diff
    if args.original:
        corpus += "\n" + args.original.read_text(errors="replace")
    added = added_text(diff)
    changed_files = re.findall(r'^\+\+\+ b/(.+)$', diff, re.MULTILINE)
    test_files = [p for p in changed_files if re.search(r'(^|/)(test|tests|spec)', p, re.I)]
    print(f"changed_files={len(changed_files)} test_files={len(test_files)}")
    if not test_files:
        print("HYPOTHESIS: no changed regression-test file; map tests manually")
    for hypothesis, pattern in RULES.items():
        if re.search(pattern, added, re.I):
            print("HYPOTHESIS:", hypothesis)
    sinks = sorted(set(re.findall(
        r'\b(?:open|send_file|execute|query|render|deserialize|eval)\s*\(', corpus)))
    if sinks:
        print("REVIEW_SINKS:", ", ".join(sinks))
    print("NEXT: verify reachability, sibling callers, controls, and a safe impact oracle")

if __name__ == "__main__":
    main()
```

Example: `python3 review_patch.py fix.diff --original vulnerable_handler.py`. Manually inspect every emitted candidate; regex cannot reconstruct data flow, platform semantics, or exploitability.

## Evidence basis and limits

This skill is a static-analysis-first review method derived from recurring patch-failure motifs: incomplete enumeration, missed call sites, transform-order errors, TOCTOU, and inadequate regression coverage. The patterns are structural and illustrative; they are not a claim that any named target or patch is vulnerable. Static similarity cannot prove reachability, attacker control, deployment state, or impact. Validate web/API hypotheses with authorized dynamic testing and mobile hypotheses on the cloud AVD rig (`setup/gcp-avd/`); use the applicable Web-Dynamic-Testing procedure for HTTP behavior. This is a first line of defense and prioritization aid, not proof of a bypass.

## Web-Verification Augment (2026-07-22)

- No dedicated local corpus category for incomplete-fix/patch-bypass reports was established for this skill; empirical frequency and acceptance rates are therefore unknown.
- The shared 12-category stop vocabulary and three-label split come from [`skills/references/negative-control-taxonomy.md`](../references/negative-control-taxonomy.md); its study sources support the invalid-report taxonomy structure, not these patch motifs or their prevalence.
- Treat advisories, maintainer discussions, repository history, tests, and live behavior as distinct evidence. Verify current deployment/version claims on the authorized target before using `[patched_version]` or declaring a bypass.
- Record verification date and URLs when web evidence is actually consulted; do not convert search snippets, mirrors, or an unverified commit association into facts.

## AI-assisted augment (NahamSec seed)

Transferable techniques from Ben Sadeghipour (NahamSec), public PlexTrac "Homework for
Hackers" webinar (`Ue-OIJoM0bA`). Guardrail: model output is a hypothesis, not evidence —
confirm every candidate against a reachable-path oracle and the shared
[negative-control taxonomy](../references/negative-control-taxonomy.md); never paste
unsanitized proprietary source into an unapproved model
(`nahamsec-ai-sanitize-before-sharing`, CWE-200).

- **Model-assisted sibling-path triage (`nahamsec-ai-unfamiliar-code-triage`).** Give an
  approved model the diff plus surrounding call sites and ask which other call sites reach
  the same sink, what inputs the fix does *not* normalize, and which alternative encodings or
  entry points survive it. Trace each candidate through the real call graph yourself and
  build a bypass PoC; confirm the patched path blocks the original payload while the sibling
  path does not.
- **Variant matrix of the fixed root cause (`nahamsec-deep-one-weakness-family`).** Extract
  the invariant the patch is meant to enforce and enumerate every place the codebase should
  enforce it; a genuinely fixed location must stay negative under the same probe.

## Version boundaries

null — Patch-bypass review is pattern and invariant analysis, not a version-bound vulnerability class. The reviewed patch defines a candidate boundary for that specific product, but no generic `introduced`/`fixed` range applies across targets; establish deployment state from the target's own history and behavior.
