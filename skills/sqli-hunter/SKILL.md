---
name: sqli-hunter
description: Hunt SQL injection in URL paths, form/JSON parameters, admin filters, and ORM-generated aliases using safe boolean, error, and bounded-time differentials. Load when input appears to shape a relational query or quote/error/timing behavior is reproducible. Triggers — SQL Injection, SQLi, time-based or boolean-based database behavior, ORM identifier injection.
---

# SQL-Injection Hunter

Use only authorized, preferably local/staging targets. Stop after a safe differential proves query control. Do not dump schemas/data, write files, invoke OS commands, or run automated exploitation against production.

## Recon signals: map inputs to query positions

Inventory more than query strings:

- numeric URL path segments (`/userId/<x>/customerId/<y>`);
- form and JSON fields such as `authors`, `years`, `invite_code`, `name`, and `keyword`;
- admin report/search filters and array/scalar ambiguity;
- sort, field, alias, relation, annotation, connector, and ORM identifier inputs;
- GraphQL arguments ultimately used by ORM/query builders.

Capture a stable baseline at least three times. Record status, body hash/length, selected semantic marker, and latency. Change one input only.

## Test recipes

### Quote/error/control triad

Send baseline, one quote, then balanced/double quote. A disclosed signup flow returned `500` for one quote and `200` for two; this is a lead, not proof.

```text
baseline: invite_code=CONTROL
probe:    invite_code=CONTROL'
control:  invite_code=CONTROL''
```

Positive only after a boolean or timing differential confirms database evaluation. Framework validation errors can show the same pattern.

### Boolean differential in a path segment

One report changed a numeric path value to URL-encoded predicates and observed a row for true and an empty result for false.

```text
/api/<RESOURCE>/1/999%20or%201=1--
/api/<RESOURCE>/1/999%20or%201=2--
```

Use a controlled/non-sensitive query and compare semantic output, not only length. Repeat true→false→true to exclude cache/load effects.

### Bounded time differential

Use short delays: 1 second, then 2 seconds; collect multiple samples and include a no-sleep syntactic control. Report patterns included MySQL conditional `sleep`, PostgreSQL `PG_SLEEP`, and admin-filter delays.

```text
MySQL-shaped:      value' XOR(if(1=1,sleep(2),0)) OR '
PostgreSQL-shaped: value');(SELECT 1 FROM PG_SLEEP(2))--
```

Do not use multiplicative 25-second sleeps or concurrent probes. Positive: median response shift tracks requested delay while controls do not.

### Authenticated admin/search filter

High-value sinks exist behind legitimate low admin/report-view permissions. A report used `coupon_codes` in a reporting page; another used `keyword` in an admin search.

```http
GET /admin/search?keyword=CONTROL%27)%20AND%20(SELECT%20SLEEP(2))--%20-&compact=t HTTP/1.1
Cookie: <CONTROLLED_LOW_PRIV_SESSION>
```

Use the minimum role and stop after timing proof. Never request database names.

### JSON body field

Preserve JSON type and mutate one string or numeric field. Compare valid control, quote, true predicate, false predicate. Do not assume WAF rejection disproves SQLi; classify only backend evidence.

### ORM identifier/alias injection

When reviewing code or a local library, test user-controlled annotation names, relation aliases, connectors, sort fields, or JSON keys. A Django report supplied a quote in a `FilteredRelation` annotation alias and inspected malformed generated SQL. Prove that untrusted application input can reach the identifier; developer-written constant strings are not remotely exploitable.

```python
alias = 'controlled_alias"'
qs = Model.objects.annotate(**{alias: FilteredRelation("relation")}).select_related(alias)
print(qs.query)  # local/staging inspection only
```

## Detection signals

Accept one of these with controls:

- boolean true and false produce stable, logically different database-backed results;
- requested 1s/2s delays cause proportional median latency while baseline/control remain stable;
- database-specific error text changes with quote balancing;
- local generated SQL visibly incorporates attacker-controlled syntax in an identifier or expression.

Record at least three timing samples per case. Prefer content markers/body hashes over screenshots. Confirm cache-busting does not explain differences.

After completing these checks, explore adjacent injection surface the checklist did not
cover — the skill is a floor, not a ceiling.

## Stop conditions (verified negatives)

Each stop condition below carries one of the 12 categories from [`skills/references/negative-control-taxonomy.md`](../references/negative-control-taxonomy.md). Apply ALL applicable labels. Never file a finding that triggers any category below.

**Decision split (apply separately, never collapse):**
- `technically_vulnerable`: does attacker input alter database query semantics?
- `in_scope`: does the program's bounty policy cover this asset?
- `program_reportable`: does the demonstrated safe impact meet its threshold?
A finding can be yes/yes/no, yes/no/yes, etc. Do not submit on `technically_vulnerable` alone.

- `[expected_product_behavior]` Quote-like input is rejected by documented validation and produces only an application error. `[technical_placeholder]`
- `[control_exists_elsewhere]` Parameterization/identifier allowlisting prevents query-shape change; WAF rejection alone does not establish this label. `[technical_placeholder]`
- `[missing_attacker_control]` Malformed SQL exists only in an ORM API called with trusted developer constants. `[technical_placeholder]`
- `[theoretical_without_oracle]` A lone `500`, length change, or slow response lacks true/false/error or proportional-time controls. Empirical: H1 `269347` (informative — "SQL Injection in parameter REPORT").
- `[real_but_below_program_impact_threshold]` A database-flavored error exposes no query control, data, or reliable oracle. `[technical_placeholder]`
- `[technically_not_vulnerable]` `sleep` text is handled by a template/application delay, or timing follows jitter/load rather than requested delay. `[technical_placeholder]`
- `[patched_version]` The target runs at/above the affected ORM/query-builder fix and target-level reproduction fails. `[technical_placeholder]`
- `[prohibited_test_method]` Evidence exists only from automated extraction/scanning or destructive/long-delay probes banned by policy. `[technical_placeholder]`

## Anti-patterns

- Do not run `sqlmap --dbs`, dump tables, enumerate users, or extract DB versions on production.
- Do not use `UNION` data extraction, stacked writes, file operations, or OS-command features.
- Do not issue long sleeps or parallel load.
- Do not mutate cookies, headers, and parameters together.
- Do not recommend a WAF as the primary fix; parameterize values and strictly allowlist identifiers.

## Minimal reproducer

```python
import os, statistics, time, requests

url = os.environ["TARGET_URL"]
cases = {"control":"CONTROL", "true":"999 or 1=1--", "false":"999 or 1=2--"}
for name, value in cases.items():
    samples=[]
    for _ in range(3):
        t=time.monotonic(); r=requests.get(url.format(value=value), timeout=10)
        samples.append(time.monotonic()-t)
    print(name, r.status_code, len(r.content), round(statistics.median(samples),3))
# Stop at a stable safe differential; do not extract data.
```

## Evidence basis and limits

Derived from eight full reports: H1 `2051931`, `2958619`, `2633959`, `3198980`, `2312334`, `2209130`, `3292573`, and `3395221`. Patterns cover path-segment boolean SQLi, quote errors, authenticated filters, MySQL/PostgreSQL time delays, and ORM alias injection. Historical reports often proceeded to automated extraction; this skill deliberately stops earlier.

Negatives in this skill are partly empirical (1 disclosed non-accepted SQL Injection report in the local corpus) and partly structural from arXiv 2511.18608 / ESEM 2021 — see `skills/references/negative-control-taxonomy.md` for provenance.

## Web-Verification Augment (2026-07-22)

- Local negative: H1 `269347` (informative, Medium, Tor Project, "SQL Injection in parameter REPORT"); ID, title, severity, program, and substate verified in JSONL.
- Study-only taxonomy: every other stop category above is `[technical_placeholder]`; local full detail confirms H1 `269347` reported only a quote-triggered SQL error, so no stronger oracle is attributed to it.

## AI-assisted augment (NahamSec seed)

Transferable techniques from Ben Sadeghipour (NahamSec), public PlexTrac "Homework for
Hackers" webinar (`Ue-OIJoM0bA`). Guardrail: model output is a hypothesis, not evidence —
confirm every candidate against a live target oracle and the shared
[negative-control taxonomy](../references/negative-control-taxonomy.md); never paste
unsanitized target source or data into an unapproved model
(`nahamsec-ai-sanitize-before-sharing`, CWE-200).

- **Model-assisted source→sink triage (`nahamsec-ai-unfamiliar-code-triage`).** When source
  is available on an unfamiliar ORM/driver, ask an approved model which inputs reach query
  construction (raw fragments, `ORDER BY`/alias positions, `LIKE`/filter builders) and where
  parameterization is bypassed; trace each candidate yourself and confirm with a safe
  boolean/error/bounded-time differential, not the model's assertion.
- **Second-look on unfamiliar DB output (`nahamsec-ai-context-second-look`).** Use a model to
  hypothesize the engine/driver behind an unfamiliar error string, then verify with a
  matched benign control — the model may name the wrong DBMS, and a plausible guess without a
  target-side oracle is not a finding.

## Version boundaries

Each row is a real, machine-readable OSV/GHSA entry bounding the ORM/query-builder attack surface for this class. Use it as a "what's already been fixed" filter — a target on or above the `fixed` boundary is not a bug candidate without independent reproduction.

| package (ecosystem) | GHSA / CVE | severity | introduced | fixed | summary |
|---|---|---|---|---|---|
| sequelize (npm) | GHSA-wrh9-cjv3-2hpw / CVE-2023-25813 | critical | 0 | 6.19.1 | SQLi via `replacements` |
| knex (npm) | GHSA-58v4-qwx5-7f59 / CVE-2019-10757 | critical | 0 | 0.19.5 | SQLi in knex |
| typeorm (npm) | GHSA-fx4w-v43j-vc45 / CVE-2022-33171 | critical | 0 | 0.3.0 | SQLi in TypeORM |
| sqlalchemy (PyPI) | GHSA-38fc-9xqv-7f7q / CVE-2019-7548 | critical | 0 | 1.2.19 | SQLi via `group_by` |
| django (PyPI) | GHSA-hmr4-m2h5-33qx / CVE-2020-7471 | critical | 0 | 1.11.28 | SQLi (StringAgg delimiter) |
| hibernate-core (Maven) | GHSA-8grg-q944-cch5 / CVE-2019-14900 | moderate | 0 | 5.3.18 | SQLi in ORM literals |

**Usage:** when a target pulls in one of these at version `x`, check `x` against `introduced`/`fixed`. If `x >= fixed`, the package is no longer the source — look at target-level query construction instead. SEMVER `fixed` is exclusive (first safe version). Data from OSV.dev (`api.osv.dev/v1/query`) + GitHub Advisory DB, fetched 2026-07-22; full dataset in `knowledge-sources/engineering-sources/version-boundaries.md`.

**Caveat:** the table proves the package's *known* vulnerable range, not that the *target's* call site reaches it — many targets wrap the ORM behind parameterized helpers that never touch the vulnerable path. Treat it as a **filter**, not a finding.
