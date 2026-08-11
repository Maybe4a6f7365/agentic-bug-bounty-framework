---
name: path-traversal-hunter
description: Hunt path traversal in file reads, uploads, generated filenames, deep links, storage keys, and sandbox permission models. Load when untrusted paths are joined, resolved, decoded, or transformed before filesystem access. Triggers — Path Traversal, directory traversal, arbitrary file read or write, path containment bypass, zip-slip.
---

# Path-Traversal Hunter

Test inside a disposable directory with canary files. Never read real secrets or write startup, cron, SSH, application, or system files.

## Map the path pipeline

For every file operation, record: attacker-controlled source → decoding/normalization → prefix/root join → canonicalization → filesystem call. Test reads, writes, deletes, existence checks, archive extraction, upload names, storage keys, deep-link filenames, and scanner-generated temp files separately.

Create `<TEST_ROOT>/allowed/inside.txt` and `<TEST_ROOT>/outside.txt` with distinct canaries. The only success target is `outside.txt` or a new file under a dedicated sibling directory.

## Recon signals

- Parameters `file`, `filename`, `path`, `key`, `download`, `template`, `asset`, `accept`, or deep-link query values.
- Routes such as `/assets/<path>`, download/preview handlers, JMX/Jolokia exec paths, or blob/storage services.
- Code patterns `join(root, input)`, `resolve(input)`, prefix string checks, `startsWith(root)`, or normalization performed before a later transform.
- File-upload automation that derives a local filename from HTML attributes (`accept`, `value`).
- Windows separators, drive/UNC paths, URL-decode layers, absolute paths, and nonstandard separators such as `!` mapped to `/`.
- Client or runtime permission models that accept buffers/typed arrays or call mutable language helpers after validation.

## Test recipes

### Read containment

Start with plain traversal against controlled canaries, then encode one layer only:

```text
../outside.txt
..%2foutside.txt
%2e%2e/outside.txt
..\outside.txt
```

For asset routes, request `/assets/../outside.txt` and compare with a nonexistent file. A real report used `/assets/../.git/config`; replace that with the canary.

### Nonstandard separator/adapter

If a management adapter maps delimiters, mirror its syntax. A disclosed Jolokia pattern used `!/etc!/passwd`; test only:

```text
/exec/<OPERATION>/!<TEST_ROOT>!outside.txt
```

Positive: exact outside canary, not a stack trace mentioning the path.

### Generated local filename

Inspect crawlers/importers that create temp uploads from page-controlled attributes. One report derived an extension from `<input type=file accept=...>` and passed it to `Path.resolve`.

```html
<form action="/upload" enctype="multipart/form-data">
  <input type="file" name="upload" value="CANARY"
         accept="./../../<DEDICATED_TEST_DIR>/written.txt">
</form>
```

Run only in a local disposable product instance. Confirm the written file contains `CANARY` and remains within the dedicated test area.

### Deep-link download filename

Use a controlled private report/file and a controlled Android emulator. A report pattern supplied `filename=/../../.../Download/disclosure.txt` to move a generated file into shared storage. Test a private canary and verify it appears outside the app-private intended directory; delete it afterward.

### Storage-key injection

Trace upload `key` or nested attachable hashes to disk-service path construction.

```json
{"filename":"probe.txt","content_type":"text/plain","key":"../../<TEST_SIBLING>/probe.txt"}
```

Test upload, download, and delete only against dedicated canaries. Canonicalize both root and result when evaluating.

### Post-validation mutation

If a sandbox validates a resolved string then converts it through mutable hooks/buffers, test whether a controlled hook changes the path after validation. Run locally. A reported Node permission bypass altered a Buffer write helper after `path.resolve()`. The key signal is validation of `/allowed/...` followed by actual access to the controlled sibling.

## Detection signals

- Response bytes equal the outside canary.
- A new canary file exists outside the intended root and inside the dedicated test sibling.
- Delete/existence operations affect only the outside canary.
- Logs show validated and actual canonical paths diverging.
- Behavior reproduces after a clean restart and with a nonexistent-path control.

After completing these checks, explore adjacent path-handling surface the checklist did not
cover — the skill is a floor, not a ceiling.

## Stop conditions (verified negatives)

Each stop condition below carries one of the 12 categories from [`skills/references/negative-control-taxonomy.md`](../references/negative-control-taxonomy.md). Apply ALL applicable labels. Never file a finding that triggers any category below.

**Decision split (apply separately, never collapse):**
- `technically_vulnerable`: is the code actually exploitable?
- `in_scope`: does the program's bounty policy cover this asset?
- `program_reportable`: does the demonstrated impact meet the program's threshold?
A finding can be yes/yes/no, yes/no/yes, etc. Do not submit on `technically_vulnerable` alone.

- `[expected_product_behavior]` A user-directed `file://` URL or `--output` accesses the local path the user selected; curl is not a filesystem sandbox. Empirical: H1 `3293884` (N/A — "Vulnerability Report: Local File Disclosure via file:// Protocol in cURL") and `3120987` (N/A — "[High] Arbitrary File Write via Path Traversal in cURL CLI (`-o`, `--output`) (CWE-22: Improper Limitation of a Pathname to a Restricted Directory)").
- `[control_exists_elsewhere]` Canonicalization keeps encoded dot segments beneath the configured root. `[technical_placeholder]`
- `[missing_attacker_control]` Escape requires the victim to set `IPFS_PATH`, `--path-as-is`, or a local destination. Empirical: H1 `3100073` (N/A — "Path Traversal Vulnerability in curl via Unsanitized IPFS_PATH Environment Variable") and `3226502` (N/A — "arbitrary file read via `file://` path traversal with `--path-as-is`").
- `[theoretical_without_oracle]` `../` is parsed, but no outside-root canary is read/written. Empirical: H1 `3494098` (N/A — "inconsistently Rejection Logic in file:// URLs with Authority").
- `[missing_security_boundary]` A general-purpose client follows operator-supplied FTP/file paths; no lower-privilege root was promised. Empirical: H1 `3418861` (N/A — "libcurl FTP path normalization flaw allows decoded %2e%2e → CWD .. and directory escape (Path Traversal, CWE-22)") and `3408126` (N/A — "Directory Traversal Vulnerability in cURL via Content-Disposition Header Processing").
- `[real_but_below_program_impact_threshold]` Only public/default or attacker-owned content is reached. `[technical_placeholder]`
- `[out_of_scope_asset]` Traversal exists only on an excluded host/component. Empirical: H1 `273377` (N/A — "Multiple Path Transversal Vulnerabilites"; reporter marks the webserver out of scope).
- `[technically_not_vulnerable]` Extraction rejects/rewrites escaping archive entries or symlinks never resolve outside root. `[technical_placeholder]`

## Anti-patterns

- Do not read `/etc/passwd`, `.git/config`, cloud credentials, user files, or source when canaries suffice.
- Do not write executables, startup files, cron entries, authorized keys, or application configs.
- Do not test destructive purge/delete on non-canary paths.
- Do not assume `../` is the only form; reason about decoding order, separators, absolute paths, and post-check transformation.
- Do not report library behavior unless untrusted application input can reach it.

## Minimal reproducer

```python
import os, requests
from urllib.parse import quote

base = os.environ["TARGET_BASE"].rstrip("/")
path = os.environ.get("FILE_ROUTE", "/assets/{value}")
for value in ["inside.txt", "../outside.txt", "..%2foutside.txt"]:
    url = base + path.format(value=value if "%" in value else quote(value, safe="/"))
    r = requests.get(url, timeout=15)
    print(value, r.status_code, r.text[:100])
# Use unique controlled canaries; never request real system files.
```

## Evidence basis and limits

Derived from seven full reports: H1 `2995025`, `3712279`, `3181066`, `2778380`, `2434811`, `2553411`, and `3580511`. Patterns cover URL-to-local writes, HTML-derived temp filenames, asset reads, delimiter mapping, post-validation buffer mutation, mobile deep links, and storage-key injection.

Negatives in this skill are partly empirical (14 disclosed non-accepted Path Traversal reports in the local corpus) and partly structural from arXiv 2511.18608 / ESEM 2021 — see `skills/references/negative-control-taxonomy.md` for provenance.

## Web-Verification Augment (2026-07-22)

- Local negatives: 14 total (12 not-applicable, 2 informative); IDs verified: H1 `2334455`, `273377`, `3494098`, `3408593`, `3465094`, `3445174`, `3418861`, `3408126`, `3293884`, `3255707`, `3242087`, `3226502`, `3120987`, `3100073`.
- Study-only taxonomy: canonicalization, below-threshold content, and safe extraction/symlink cases remain `[technical_placeholder]`; local full detail was consulted for the out-of-scope statement in H1 `273377`.

## AI-assisted augment (NahamSec seed)

Transferable techniques from Ben Sadeghipour (NahamSec), public PlexTrac "Homework for
Hackers" webinar (`Ue-OIJoM0bA`), applied to CWE-22. Guardrail: model output is a
hypothesis, not evidence — confirm every candidate against a live target oracle and the
shared [negative-control taxonomy](../references/negative-control-taxonomy.md), and never
paste unsanitized target source, paths, or secrets into an unapproved model
(`nahamsec-ai-sanitize-before-sharing`, CWE-200).

- **Model-assisted source→sink triage (`nahamsec-ai-unfamiliar-code-triage`).** On an
  unfamiliar stack, give an approved model the smallest slice around the file API
  (`open`/`readFile`/`sendFile`, storage-key builders) plus its call sites and ask for
  attacker-controlled inputs, the decode/normalize/join order, and the containment check.
  Trace each candidate through the real call graph yourself; confirm only when the path is
  reachable and a `../` or absolute payload escapes the intended root while a patched or
  sibling path does not. CWE-22 is the seed's own worked example for this technique.
- **Neighbor storage-key / path ideas (`nahamsec-ai-neighbor-path-ideas`).** From one
  observed download route or storage key, ask for likely siblings (tenant-prefixed keys,
  archive members, `{id}` → `{id}/..` shapes) to seed the path pipeline; probe slowly
  against nonexistent controls, never a bulk wordlist dump.

## Version boundaries

Each row is a real, machine-readable OSV/GHSA entry bounding the `../`-normalization / archive-extraction surface for this class. Use it as a "what's already been fixed" filter — a target on or above the `fixed` boundary is not a bug candidate without independent reproduction.

| package (ecosystem) | GHSA / CVE | severity | introduced | fixed | summary |
|---|---|---|---|---|---|
| decompress (npm) | GHSA-qgfr-5hqp-vrw9 / CVE-2020-12265 | critical | 0 | 4.2.1 | Path traversal on archive extraction |
| tar (npm) | GHSA-3jfq-g458-7qm9 / CVE-2021-32804 | high | 0 | 3.2.2 | Arbitrary file write, absolute-path gap |
| adm-zip (npm) | GHSA-3v6h-hqm4-2rg6 / CVE-2018-1002204 | moderate | 0 | 0.4.11 | Zip-slip arbitrary file write |
| send (npm) | GHSA-xwg4-93c6-3h42 / CVE-2014-6394 | low | 0 | 0.8.4 | Directory traversal in static send |
| werkzeug (PyPI) | GHSA-j544-7q9p-6xp8 / CVE-2019-14322 | high | 0 | 0.15.5 | Path traversal serving shared data on Windows |

**Usage:** when a target pulls in one of these at version `x`, check `x` against `introduced`/`fixed`. If `x >= fixed`, the library's normalizer already blocks the escape — look at target-level path joins/decoders instead. SEMVER `fixed` is exclusive (first safe version). Data from OSV.dev (`api.osv.dev/v1/query`) + GitHub Advisory DB, fetched 2026-07-22; full dataset in `knowledge-sources/engineering-sources/version-boundaries.md`.

**Caveat:** the table proves the package's *known* vulnerable range, not that the *target's* call site reaches it — a target may never pass attacker-controlled names into the vulnerable extract/serve path. Treat it as a **filter**, not a finding.
