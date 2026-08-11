---
source_type: version-boundaries
last_updated: 2026-07-22
priority: P0
reliability: medium-high
provenance: OSV.dev POST /v1/query (no-auth), GitHub Advisory Database (OSV format)
license: CC-BY-4.0 (GHSA/OSV upstream); attribution + retrieval date retained
---

# Version boundaries — GHSA/OSV back-fill (Block A)

Curated `introduced`/`fixed` boundaries for the five (six-file) version-bound
hunter skills. Every row below was returned by a live OSV.dev `POST /v1/query`
this session (2026-07-22); no CVE/GHSA ID here is hand-authored. Severity is the
`database_specific.severity` label from the OSV record (CVSS-derived).

**Reliability note.** *High* per row: the ID, package, ecosystem, and
`introduced`/`fixed` events come verbatim from the OSV JSON response. *Medium* at
the interpretation layer: OSV `fixed` semantics are ecosystem-dependent
(SEMVER `fixed` is exclusive — the first *safe* version), and CWE relevance was
filtered by summary-keyword match, so a row's presence means "OSV labels this
package vulnerable in this range," **not** that any given target's call site is
reachable. Rows marked `≤x (last_affected)` had no `fixed` event — OSV recorded a
`last_affected` bound instead (no clean patch version at record time).

This file is the full extracted dataset; each skill's `## Version boundaries`
block cites back here.

---

## sqli-hunter (CWE-89)

**Libraries queried (10):** sequelize (npm), knex (npm), typeorm (npm),
activerecord (RubyGems), sequel (RubyGems), sqlalchemy (PyPI), django (PyPI),
org.hibernate:hibernate-core (Maven), org.mybatis:mybatis (Maven), mysql2 (npm).

| package (ecosystem) | GHSA / CVE | severity | introduced | fixed | summary |
|---|---|---|---|---|---|
| sequelize (npm) | GHSA-wrh9-cjv3-2hpw / CVE-2023-25813 | critical | 0 | 6.19.1 | SQL injection via `replacements` |
| knex (npm) | GHSA-58v4-qwx5-7f59 / CVE-2019-10757 | critical | 0 | 0.19.5 | SQL injection in knex |
| typeorm (npm) | GHSA-fx4w-v43j-vc45 / CVE-2022-33171 | critical | 0 | 0.3.0 | SQL injection in TypeORM |
| sqlalchemy (PyPI) | GHSA-38fc-9xqv-7f7q / CVE-2019-7548 | critical | 0 | 1.2.19 | SQL injection via `group_by` parameter |
| django (PyPI) | GHSA-hmr4-m2h5-33qx / CVE-2020-7471 | critical | 0 | 1.11.28 | SQL injection (StringAgg delimiter) |
| hibernate-core (Maven) | GHSA-8grg-q944-cch5 / CVE-2019-14900 | moderate | 0 | 5.3.18 | SQL injection in Hibernate ORM literals |

---

## path-traversal-hunter (CWE-22)

**Libraries queried (10):** send (npm), serve-static (npm), st (npm),
express (npm), tar (npm), adm-zip (npm), decompress (npm), flask (PyPI),
werkzeug (PyPI), org.apache.commons:commons-compress (Maven).

| package (ecosystem) | GHSA / CVE | severity | introduced | fixed | summary |
|---|---|---|---|---|---|
| decompress (npm) | GHSA-qgfr-5hqp-vrw9 / CVE-2020-12265 | critical | 0 | 4.2.1 | Path traversal on archive extraction |
| tar (npm) | GHSA-3jfq-g458-7qm9 / CVE-2021-32804 | high | 0 | 3.2.2 | Arbitrary file write via absolute-path sanitization gap |
| adm-zip (npm) | GHSA-3v6h-hqm4-2rg6 / CVE-2018-1002204 | moderate | 0 | 0.4.11 | Zip-slip arbitrary file write |
| send (npm) | GHSA-xwg4-93c6-3h42 / CVE-2014-6394 | low | 0 | 0.8.4 | Directory traversal in static file send |
| werkzeug (PyPI) | GHSA-j544-7q9p-6xp8 / CVE-2019-14322 | high | 0 | 0.15.5 | Path traversal on Windows shared-data serving |

---

## auth-bypass-hunter (CWE-287 / CWE-347)

**Libraries queried (10):** jsonwebtoken (npm), jose (npm), passport-saml (npm),
pyjwt (PyPI), python-jose (PyPI), jwt (RubyGems),
com.nimbusds:nimbus-jose-jwt (Maven), oauth2-server (npm), next-auth (npm),
node-saml (npm).

| package (ecosystem) | GHSA / CVE | severity | introduced | fixed | summary |
|---|---|---|---|---|---|
| jsonwebtoken (npm) | GHSA-qwph-4952-7xr6 / CVE-2022-23540 | moderate | 0 | 9.0.0 | Signature-validation bypass via insecure default algorithm in `jwt.verify()` |
| pyjwt (PyPI) | GHSA-r9jw-mwhq-wp62 / CVE-2017-11424 | high | 0 | 1.5.1 | Key-confusion (RS256↔HS256) attack |
| python-jose (PyPI) | GHSA-6c5p-j8vq-pqhj / CVE-2024-33663 | critical | 0 | 3.4.0 | Algorithm confusion with OpenSSH ECDSA keys |
| passport-saml (npm) | GHSA-m974-647v-whv7 / CVE-2022-39299 | high | 0 | 3.2.2 | SAML signature bypass via multiple root elements |
| nimbus-jose-jwt (Maven) | GHSA-f6vf-pq8c-69m4 / CVE-2019-17195 | critical | 0 | 7.9 | Improper check for unusual/exceptional conditions in JWT parsing |

---

## privesc-hunter (CWE-269 / CWE-285 authorization)

**Libraries queried (10):** casbin (npm), accesscontrol (npm),
org.springframework.security:spring-security-core (Maven), django (PyPI),
grafana (Go), github.com/casbin/casbin/v2 (Go), next-auth (npm), keystone (npm),
parse-server (npm), directus (npm).

| package (ecosystem) | GHSA / CVE | severity | introduced | fixed | summary |
|---|---|---|---|---|---|
| spring-security-core (Maven) | GHSA-hh32-7344-cg2f / CVE-2022-22978 | critical | 5.5.0 | 5.5.7 | Authorization bypass via RegexRequestMatcher |
| parse-server (npm) | GHSA-8xq9-g7ch-35hg / CVE-2024-47183 | high | 0 | 6.5.9 | Custom object ID lets a user acquire role privileges |
| django (PyPI) | GHSA-m6gj-h9gm-gw44 / CVE-2020-24583 | high | 2.2a1 | 2.2.16 | Incorrect default permissions (file cache) |
| django (PyPI) | GHSA-p99v-5w3c-jqq9 / CVE-2021-33571 | high | 2.2a1 | 2.2.24 | Access-control bypass (URL-path validation → SSRF/LFI) |
| directus (npm) | GHSA-pmf4-v838-29hg / CVE-2025-24353 | moderate | 0 | 11.2.0 | Privilege escalation via the Share feature |

---

## xss-reflected-hunter (CWE-79)

**Libraries queried (10):** dompurify (npm), sanitize-html (npm), marked (npm),
ejs (npm), handlebars (npm), jquery (npm), serialize-javascript (npm),
bleach (PyPI), markupsafe (PyPI), markdown-it (npm).

| package (ecosystem) | GHSA / CVE | severity | introduced | fixed | summary |
|---|---|---|---|---|---|
| dompurify (npm) | GHSA-gx9m-whjm-85jf / CVE-2024-47875 | high | 0 | 2.5.0 | Nesting-based mutation XSS (mXSS) |
| handlebars (npm) | GHSA-2w6w-674q-4c4q / CVE-2026-33937 | critical | 4.0.0 | 4.7.9 | JavaScript injection via AST type confusion |
| sanitize-html (npm) | GHSA-qhxp-v273-g94h / CVE-2019-25225 | moderate | 0 | 2.0.0-beta | XSS via incomprehensive sanitization |
| jquery (npm) | GHSA-gxr4-xjj5-5px2 / CVE-2020-11022 | moderate | 1.12.0 | 3.5.0 | XSS via `.html()`/DOM manipulation of untrusted markup |
| bleach (PyPI) | GHSA-m6xf-fq7q-8743 / CVE-2020-6816 | moderate | 0 | 3.1.2 | Mutation XSS via whitelisted math/svg + raw tag |

---

## xss-stored-hunter (CWE-79, persisted contexts)

**Libraries queried (10):** dompurify (npm), sanitize-html (npm),
ckeditor4 (npm), quill (npm), showdown (npm), markdown-it (npm), bleach (PyPI),
prismjs (npm), react-markdown (npm), froala-editor (npm).

| package (ecosystem) | GHSA / CVE | severity | introduced | fixed | summary |
|---|---|---|---|---|---|
| dompurify (npm) | GHSA-gx9m-whjm-85jf / CVE-2024-47875 | high | 0 | 2.5.0 | Nesting-based mXSS (persisted rich-text) |
| ckeditor4 (npm) | GHSA-4fc4-4p5g-6w89 / CVE-2022-24728 | moderate | 0 | 4.18.0 | Stored XSS in CKEditor4 WYSIWYG content |
| prismjs (npm) | GHSA-3949-f494-cm99 / CVE-2022-23647 | high | 1.14.0 | 1.27.0 | XSS via rendered highlighted content |
| quill (npm) | GHSA-4943-9vgg-gr5r / CVE-2021-3163 | moderate | 0 | ≤1.3.7 (last_affected) | Stored XSS in Quill editor |
| froala-editor (npm) | GHSA-97x5-cc53-cv4v / CVE-2020-22864 | moderate | 0 | 4.0.11 | Stored XSS in Froala WYSIWYG |
| bleach (PyPI) | GHSA-vv2x-vrpj-qqpq / CVE-2021-23980 | moderate | 0 | 3.3.0 | Stored XSS via sanitizer bypass |

---

## Honest ledger

**Method.** One `POST https://api.osv.dev/v1/query` per (package, ecosystem)
with a probe version inside a plausibly-vulnerable range, 0.7 s spacing. No
rate-limit (HTTP 429) was hit across 60 lookups. Results filtered by
CWE-keyword match on the OSV `summary`, then the highest-severity / clearest-
boundary rows selected per skill.

**Successful lookups (returned ≥1 relevant vuln):** sequelize, knex, typeorm,
activerecord, sqlalchemy, django, hibernate-core, mybatis, mysql2; send,
serve-static, st, express, tar, adm-zip, decompress, flask, werkzeug,
commons-compress; jsonwebtoken, jose, passport-saml, pyjwt, python-jose, jwt,
nimbus-jose-jwt, oauth2-server, next-auth; spring-security-core, django,
parse-server, directus; dompurify, sanitize-html, marked, ejs, handlebars,
jquery, serialize-javascript, bleach, markdown-it; ckeditor4, quill, showdown,
prismjs, froala-editor.

**Empty lookups (0 vulns — documented, not fabricated):**
- `sequel` (RubyGems) — no OSV advisory returned for the probed version.
- `node-saml` (npm) — 0; its signature-bypass advisory is carried under
  `passport-saml` (used instead).
- `casbin` (npm) `accesscontrol` (npm) `keystone` (npm) — 0; likely no reviewed
  advisory under that exact package name.
- `grafana` (Go) `github.com/casbin/casbin/v2` (Go) — 0; Go ecosystem entries key
  on the full module path (`github.com/grafana/grafana`), so the short name and
  the probed version both missed. Not retried (privesc already has 5 rows).
- `markupsafe` (PyPI) `react-markdown` (npm) — 0 relevant.

**Selected-but-not-tabled:** django had 31–65 vulns, parse-server 106, directus
44, dompurify 21 — only the highest-signal boundary rows were promoted; the rest
stay in `/tmp/osv_results.json` (not committed) and can be re-derived by re-running
the query.

**Verification status:** every tabled row = verified via live OSV JSON response
(id + package + range events copied from the response). Severity labels = OSV
`database_specific.severity` (CVSS-derived, not independently recomputed). CWE
relevance = keyword-filtered (interpretation, medium confidence).
