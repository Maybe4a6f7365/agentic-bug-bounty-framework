---
name: audit-invariants
description: Reusable trust-boundary and design invariants extracted from disclosed third-party security audits (Trail of Bits, Cure53, OSTIF/Ada Logics). Feeds business-logic-hunter and access-control-hunter with the workflow/authorization invariant classes that scanners miss.
metadata:
  type: reference
---

# Design invariants from disclosed audits

Audit reports are the best public source for two invariant classes that scanners
and disclosed-H1 corpora underrepresent: **workflow/state-machine invariants**
(business logic) and **trust-boundary / authorization-matrix invariants** (access
control). Firms publish client-cleared reports with threat models, trust-zone
tables, and low/medium design weaknesses that rarely surface in H1 disclosure.

Each invariant below is anchored to a real, published finding. Use them as
hypothesis generators, not proof of coverage — verify against the live target.

## Source table

| Report | Firm | Year | Type | Verified via |
|---|---|---|---|---|
| Cedar, Rego & OpenFGA Policy Languages — Comparative Language Security Assessment | Trail of Bits | 2024 | AuthZ policy engines | pdftotext of `publications/reports/Policy_Language_Security_Comparison_and_TM.pdf` |
| Validating Vanta's multi-tenant isolation architecture | Trail of Bits | 2025 | Multi-tenant SaaS | pdftotext of `publications/case-studies/vanta-casestudy.pdf` |
| PyPI: Warehouse and Cabotage Security Assessment | Trail of Bits (org. OTF) | 2023 | Web app / API | pdftotext of `publications/reviews/2023-09-pypi-warehouse-securityreview.pdf` |
| Istio Ztunnel Security Assessment | Trail of Bits (org. OSTIF) | 2025 | Cloud-native / mTLS | pdftotext of `publications/reviews/2024-12-istio-ztunnel-securityreview.pdf` |
| Pentest-Report authentik IdP (Web, API & SSO) | Cure53 | 2023 | SSO / identity | pdftotext of `cure53/Publications/pentest-report_authentik.pdf` |
| Pentest-Report Globaleaks | Cure53 | 2013 | Whistleblower web app | pdftotext of `cure53/Publications/pentest-report_globaleaks.pdf` |
| Express.js Security Audit 2024 | Ada Logics (org. OSTIF) | 2024 | Web framework | pdftotext of `ostif.org/.../expressjs-2024-security-audit-report.pdf` |

Report repositories: `github.com/trailofbits/publications`,
`github.com/cure53/Publications`, `ostif.org/audits/`. Do not commit the PDFs.

## Access-control / trust-boundary invariants

- **Looked-up object re-binds to the acting subject.** A credential/device/record
  selected by an attacker-supplied ID must be verified to belong to the pending
  subject, not trusted because the row exists. [Cure53 authentik ATH-01-010, 2023:
  a WebAuthn assertion was validated against *any* device whose `credential_id`
  matched, without checking `device.user == pending_user` — login as `akadmin`.]
- **Tenant scoping holds at every tier.** Cross-tenant isolation must be enforced
  in GraphQL/REST resolvers, async job handlers, and internal service calls alike,
  not only at the front API. [Trail of Bits Vanta, 2025: scope spanned GraphQL,
  REST, async job handlers, and internal services.]
- **Every route carries an explicit permission guard.** Enumerate routes; assert
  each names its ACL/permission rather than inheriting one by convention. [Trail of
  Bits PyPI TOB-PYPI-26 "Routes missing access controls", 2023.]
- **Service-to-service identity binds to the transport, not a claim.** L4
  authorization keys on the mTLS peer identity (SPIFFE `trust_domain`), never an
  application-layer header. [Trail of Bits/OSTIF Istio Ztunnel, 2025.]
- **PEP calls the PDP for every access; a shared PDP isolates tenants.** In a
  multi-tenant policy engine one tenant's policies must not influence another's
  decision. [Trail of Bits Cedar/Rego/OpenFGA, 2024: PDP/PEP/PIP model, multiple
  mutually distrustful tenants on one policy engine.]
- **Each role tier proves its own identity.** Distinct roles each require
  independent authentication; no tier inherits access from another. [Cure53
  GlobaLeaks GL01-001, 2013: receiver login allowed password-less authentication.]

## Business-logic / workflow invariants

- **No cross-flow state replay.** Per-flow challenges/tokens must not live in a
  session slot a sibling or earlier flow can supply; each step re-derives its
  prerequisites. [Cure53 authentik ATH-01-014, 2023: dropping an auto-sent GET let
  an earlier flow's TOTP challenge satisfy a later POST, lifting the device-class
  restriction.]
- **Canonicalize before deciding.** Normalize the path/URL once, then validate; a
  mitigation applied *before* a later normalization step is bypassable. [Ada
  Logics/OSTIF Express.js ADA-EXPJS-2024-1 (CVE-2024-43796), 2024: an appended
  trailing `/` was re-crafted around, yielding XSS in `res.redirect`.]
- **Deferred/async continuation re-checks authorization at execution.** An
  enqueue-time permission check does not carry to dequeue-time; the async handler
  must re-verify tenant/permission when it runs. [Trail of Bits Vanta, 2025 —
  async job handlers in scope.]
- **Auth fallbacks fail closed.** When the primary credential mismatches, reject —
  never silently downgrade to a weaker trusted-header path. [Trail of Bits
  PyPI TOB-PYPI-12 "HTTP header is silently trusted if token mismatches", 2023.]
- **Authorization decisions fail closed.** An evaluation error, timeout, or missing
  policy yields deny, not allow. [Trail of Bits Cedar/Rego/OpenFGA, 2024:
  default-deny semantics across engines.]
- **Pre-auth submission endpoints enforce per-source size AND count quotas.** A
  size cap without a count/rate cap is a durable invariant break. [Cure53 GlobaLeaks
  GL01-006, 2013: API validated upload size but not the number of uploads → disk
  flood by unauthenticated users.]
