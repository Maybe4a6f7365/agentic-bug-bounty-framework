---
source_type: audit-report
last_updated: 2026-07-22
priority: P0
reliability: high
---

# Public Security Audit / Pentest Reports

## What it is

Full engagement reports from professional audit firms — Trail of Bits, Cure53, OSTIF-sponsored audits
— published with the client's consent. Unlike a single-bug H1 report, an audit gives **architecture,
threat model, systematic coverage, trust boundaries, low/medium findings, design weaknesses,
limitations, and remediation**. This is the raw material for **business-logic and design skills** that
no single-vuln corpus can teach.

## Concrete endpoints / URLs

- **Trail of Bits publications:** `https://github.com/trailofbits/publications` (canonical index of
  public audit reports + papers); blog `https://blog.trailofbits.com/categories/audits/`.
- **Cure53 publications:** `https://github.com/cure53/Publications` and `https://cure53.de/` (recent
  reports listed on-site; PDFs linked).
- **OSTIF:** `https://ostif.org/` — sponsors and links independent audits (frequently Cure53 / X41 /
  7ASecurity), e.g. Thunderbird, curl, recent PDFs under `ostif.org/wp-content/uploads/...`.
- **Aggregators:** `https://github.com/juliocesarfort/public-pentesting-reports` (large curated
  index, incl. a `Cure53/` folder), `https://7asecurity.com/publications`,
  `https://www.pentestreports.com/reports`.

## What it adds beyond HackerOne

- **Attack-surface enumeration** — how a pro decomposes a system into components and trust zones.
- **Business-logic invariants** — the assumptions the code *must* preserve (state machines, auth
  boundaries, replay/idempotency), stated explicitly.
- **Cross-component trust checks** — where component A wrongly trusts B's output.
- **Protocol/state-machine tests** — sequences that break invariants (great hypotheses).
- **Low/medium & design findings** — the "not a bug today but fragile" observations H1 rarely shows.
- **Remediation + limitations** — what was *not* tested (assumptions worth challenging = new leads).

Maps to case-bundle fields `behavioral_model.trust_boundary`, `missing_or_incorrect_control`,
`agent_guidance.applicability_signals`, and `hypotheses`.

## Filter criteria for our use-case

- Prefer **web/app/API and protocol** audits over pure crypto/hardware (unless building those skills).
- Extract **invariants and threat-model tables**, not individual payloads.
- Prioritize reports that include a **methodology/coverage** section and a **design-weakness** class.
- Cross-reference findings that later became CVEs (join to GHSA/OSV).

## License notes

- Audit reports are **copyright the firm/client**; published for reference. **Do not redistribute the
  PDFs**; ingest as *reference* (extract invariants/threat-model patterns with attribution to firm +
  report title + date). Trail of Bits/Cure53 publication repos are public but retain their copyright.

## Risks / caveats

- **Consent-gated & sparse** — only a fraction of engagements are public; selection bias toward
  security-conscious clients (well-audited code → fewer easy bugs).
- **Not reproducible** — narrative findings, rarely a runnable PoC; pair with Wave-3 benchmarks.
- **Copyright** — reference-only; never republish verbatim.
- **Staleness** — architecture may have changed since the report; treat as historical design signal.

## Concrete next steps

- **First skill to benefit:** the **business-logic / broken-access-control (CWE-862/639)** skill and a
  new **"design-weakness / trust-boundary" recon** capability — audit reports are its best teacher.
- **Wave point:** Wave 2 (engagement knowledge).

## Honest ledger

- **Verified (web):** `trailofbits/publications`, `cure53/Publications`, `ostif.org`,
  `juliocesarfort/public-pentesting-reports` (Cure53 folder), 7asecurity/pentestreports aggregators
  all exist and host public reports.
- **Training knowledge (high):** copyright/reference-only handling — standard for audit PDFs; confirm
  each report's stated redistribution terms before any reuse beyond internal reference.
