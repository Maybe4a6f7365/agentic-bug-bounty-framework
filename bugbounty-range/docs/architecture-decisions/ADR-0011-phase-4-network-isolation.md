# ADR-0011 — Phase 4 Netzwerk-Isolation und Cloud NAT

> Phase-4A correction: bootstrap egress is a persistent priority-1000 EGRESS
> exception limited to `199.36.153.4/30`, TCP/443, and the
> lab tag. Only `bbr destroy` removes it. There is no NAT, external IP, or
> general-egress allow rule.

Implementation: Phase-4.0 complete in code, Terraform module and tests;
EXECUTE pending.
Validation: all five requested Terraform roots validate; the new module is
formatted and covered by acceptance tests.

Pre-Execute-Korrektur (2026-07-27):
- Blocker A (Backend): terraform-konform. Backend-Block in HCL
  darf keine Variablen enthalten. Phase-3-Mechanismus
  (`terraform init -backend-config=...`) bleibt unverändert.
- Blocker B (Bootstrap-Egress): instanziiert. Plan-Ressourcen
  7 → 8.

Status: Accepted and implemented for Phase 4A.

Phase-4A-Korrektur (2026-07-27): Die VM verwendet für den
authentifizierten Release-Pull den GCE Default Service Account. Dieser
hat ausschließlich ein explizites bucket-scoped
`roles/storage.objectViewer`-Binding am Bootstrap-Bucket. Die
Lab-Runtime-SA bleibt planmäßig vorhanden, wird von der Phase-4-VM
aber nicht attached. Das IAM-Binding ist einmalige Release-
neunte Ressource des 9-Ressourcen-Lab-Plans.

Bezug: `notes/PHASE-4-PLAN.md` (Abschnitte 5, 9, 11, 14,
15), `ADR-0009-lab-lifecycle.md`,
`ADR-0010-phase-4-appliance-bootstrap.md`,
`DIRECTIVE.md` Section 23/27, `ACCEPTANCE-CRITERIA.md`,
`ADR-0003-network.md`.

## Context

Phase 3 hat eine **bewusste** Netzwerk-Entscheidung
getroffen: kein Cloud NAT, kein externer Internetzugang
aus Lab-VMs. Diese Entscheidung steht in
`ADR-0009-lab-lifecycle.md` Decision 6 (kein
`access_config`, kein externes IPv4) und Decision 7
(Default-Deny-Egress). Sie ist Teil der "Lab ist
vollständig isoliert"-Invariante und wird im
`EGRESS_FORBIDDEN_KEYWORDS`-Set in `src/bbr/cli.py`
durchgesetzt.

Die Entscheidung wurde getroffen, **bevor** klar war,
**wie** Phase 4 das Bootstrap-Problem lösen wird. Phase 4
löst es über Google Cloud Storage (siehe ADR-0010): ein
**offline gebautes Release-Artefakt** (`artifact.tar.zst`)
wird in einem privaten GCS-Bucket unter
`artifacts/<app>/<version>-<revision>/` abgelegt. Der
Lab-VM-Bootstrap zieht das Artefakt über Private Google
Access.

Drei weitere Kontext-Faktoren:

a) **WireGuard-MASQUERADE-Hypothese (ADR-0009).** Die
in `ADR-0009-lab-lifecycle.md` und `DIRECTIVE.md`
Section 25.6 dokumentierte Hypothese (bastion-seitige
MASQUERADE-Regel schreibt WG-Overlay-Source auf
bastion-interne IP um) ist **nicht** verifiziert. Sie
betrifft den WireGuard-Pfad, nicht den Bootstrap-Pfad.
Sie wird in diesem ADR **nicht** aufgelöst.

b) **245 EUR Budget bis 2026-09-27.** Cloud NAT
kostet in europe-west3 ~32 USD/Monat Fixkosten plus
~0,045 USD/GB verarbeiteter Traffic. Bei einer
Restlaufzeit von ~30 Tagen sind das ~32 USD ≈ ~30 EUR
Fixkosten allein für die NAT-Existenz, ~12 % des
Restbudgets.

c) **Default-Deny-Egress Priorität 65000.** Die
bestehende Egress-Firewall (compute-node Modul,
Ressource `egress_deny`) hat Priorität 65000 und
verbietet `0.0.0.0/0` für `protocol = all`. Jede
andere Egress-Firewall, die das Lab während
`BOOTSTRAPPING` lockert, muss **höhere** Priorität
haben (numerisch kleiner). Die Phase-3-Default-Firewall
bleibt aktiv als belt-and-suspenders Backup.

## Decision (verbindliche Architektur)

### D.1 Cloud NAT: nicht erzeugt

**Architekturentscheidung:** Phase 4.0 erzeugt **kein**
Cloud NAT. Die Phase-3-Invariante "kein Cloud NAT"
bleibt erhalten.

Begründung:
- GCS-Endpunkte in europe-west3 sind über Private
  Google Access ohne NAT erreichbar.
- Cloud NAT würde ~32 EUR/Monat Fixkosten verursachen
  und damit 12 % des Restbudgets verbrauchen.
- Cloud NAT erweitert die Angriffsfläche auf das
  gesamte öffentliche Internet.
- Die Architektur braucht keinen Egress außerhalb von
  GCS — alle benötigten Komponenten sind im
  Release-Artefakt.

### D.2 Artifact Registry: nicht erforderlich für Phase 4.0

**Architekturentscheidung:** Die Bootstrap-Quelle ist
GCS-Tarball, nicht AR-Container. Phase 4.0 kommt ohne
Artifact Registry aus. AR wird für Phase 4.x reserviert,
falls ein zukünftiger Stack zwingend Container-basiert
sein sollte.

### D.3 Private Google Access: bereits aktiv

**Architekturentscheidung:** Das Phase-3-Network-Modul
hat bereits `private_ip_google_access = true` auf
`google_compute_subnetwork.lab`. Diese Einstellung
bleibt unverändert und ermöglicht den GCS-Zugriff
ohne NAT.

Mechanismus: GCS-Endpunkte in der gleichen Region
(`storage.googleapis.com`, `*.googleapis.com`) sind
über Private Google Access erreichbar. DNS-Auflösung
erfolgt über `169.254.169.254` (GCP-Metadaten-DNS)
oder internen Google-DNS — beides ist ohne
Public-Internet erreichbar.

### D.4 Bootstrap-Egress: präzisierte Spezifikation

Die einzige temporäre Egress-Lockerung ist eine
**Bootstrap-Firewall** mit folgenden Eigenschaften:

| Eigenschaft | Wert |
|---|---|
| **Ressource** | `google_compute_firewall.bootstrap_egress` (compute-node Modul) |
| **Richtung** | EGRESS |
| **Priorität** | 1000 (numerisch kleiner als Phase-3-Deny-Egress Priorität 65000) |
| **Quell-Tag** | `wordpress-smoke-001` (Lab-Tag, identisch zu Phase-3-Firewalls) |
| **Ziel-Bereich** | `199.36.153.4/30` |
| **Protokoll/Port** | `tcp/443` |
| **Aktion** | allow |

**Welche Verbindung wird erlaubt?**

- **TCP/443** (HTTPS) vom Lab-Tag `wordpress-smoke-001`.

**Wohin?**

- `199.36.153.4/30` — restricted Google APIs VIPs. Der Downloader
  bindet `storage.googleapis.com` deterministisch mit `curl --resolve`
  an `.4`, `.5`, `.6` und `.7`.

**Warum?**

- Der GCS-Pull des `artifact.tar.zst` +
  `artifact.tar.zst.sha256` + `artifact.tar.zst.minisig`
  + `manifest.json` erfolgt über HTTPS an diese
  Endpunkte.
- Andere Public-Internet-Ziele sind **nicht**
  zulässig (insbesondere wordpress.org, Plugin-Server,
  apt-Repos).
- Diese Egress-Allowlist wird **explizit als Ausnahme**
  in der Runtime-State-Sub-State `bootstrap_state.egress_allow`
  dokumentiert.

**Wann?**

- Aktiv während der Lifecycle-Phasen:
  `CREATED → BOOTSTRAPPING → VERIFYING_ARTIFACT → INSTALLING
  → CONFIGURING → STARTING → READY`.
- Genauer: vom ersten Boot der VM bis zum Eintritt in
  den `READY`-Zustand.

**Wodurch endet sie?**

- Die Bootstrap-Firewall wird durch eine
  `terraform_data`-Ressource (oder `null_resource`)
  mit `triggers = { ready = local_file.ready.id }`
  gesteuert.
- Beim Übergang zu `READY` wird die Firewall durch
  ein Re-Apply entfernt.
- Die Phase-3-Default-Deny-Egress-Firewall
  (Priorität 65000) bleibt **unverändert aktiv**.
  Im READY-Zustand bleibt ausschließlich der eingeschränkte Bootstrap-Egress aktiv.

**Was passiert wenn eine Verbindung nicht im Ziel-Bereich
liegt?**

- Die Bootstrap-Firewall erlaubt nur die oben
  spezifizierten Bereiche.
- Jede andere Verbindung wird durch die
  Default-Deny-Firewall (Priorität 65000) geblockt.
- Es gibt **keine** "Default-Allow für 0.0.0.0/0"
  zu **irgendeinem** Zeitpunkt.

### D.5 Ingress-Firewalls (unverändert, Phase 3)

- `wireguard_admin`: source `10.254.0.0/24`,
  tcp/22 + icmp, Priorität 1000.
- `iap_ssh`: source `35.235.240.0/20`,
  tcp/22, Priorität 1000.

### D.6 Service-Account-Scope (Phase 4.0)

**Architekturentscheidung:** Phase 4.0 benötigt
**keine** zusätzlichen Rollen für die Lab-SA.

- GCS-Zugriff erfolgt über Bucket-IAM, gebunden auf
  den BBR-Bucket und die Lab-SA, **nicht** über eine
  project-weite Rolle.
- Falls Phase 4.x AR einführt:
  `roles/artifactregistry.reader` wird auf der Lab-SA
  via
  `google_artifact_registry_repository_iam_member`
  gebunden (kein project-weiter Grant).

### D.7 Allgemeine Internetfreigabe: nicht vorgesehen

**Architekturentscheidung (Negativ-Aussage):**

Es ist **keine** allgemeine Internetfreigabe vorgesehen.
Die oben genannten Bereiche sind die **einzigen**
zulässigen Egress-Ziele während der Bootstrap-Phase.
Insbesondere:

- **Keine** Verbindung zu wordpress.org
- **Keine** Verbindung zu Plugin-Servern
- **Keine** Verbindung zu apt-Repos
- **Keine** Verbindung zu GitHub (außer über Private
  Google Access, falls eine zukünftige Phase das
  einführt — aktuell nicht der Fall)
- **Keine** Verbindung zu Cloud Logging, Cloud
  Monitoring (Lab-Services loggen lokal, nicht extern)

Falls eine zukünftige Phase eine zusätzliche
Egress-Ausnahme benötigt, muss:

1. Ein neues Sub-State-Feld unter
   `bootstrap_state.additional_egress_allow[]`
   eingeführt werden.
2. Das neue Ziel **vor** der Implementierung in diesem
   ADR ergänzt und begründet werden.
3. Ein neuer Review-Cycle für die Erweiterung erfolgen.

## Consequences

### Kosten

- Cloud NAT Fixkosten: 0 EUR (kein NAT).
- GCS-Storage-Kosten: <0,01 EUR/Monat für einen
  ~50 MB Tarball.
- GCS-Operations-Kosten: vernachlässigbar
  (1 GET pro Bootstrap).
- Egress-Kosten: 0 EUR (kein Public-Internet-Egress;
  GCS-Internal-Egress ist kostenlos in der gleichen
  Region).
- **Phase-4.0-Mehrkosten vs. Phase 3: ≤ 0,01 EUR
  pro Zyklus**.

### Komplexität

- Keine neuen Terraform-Ressourcen, die nicht bereits
  Phase-3-konform wären: die Bootstrap-Egress-Firewall
  ist eine Adjunkt-Ressource zum compute-node-Modul.
- Kein neues VPC Peering, keine VPC Service Controls,
  kein Cloud DNS, kein Cloud Load Balancer, kein
  Artifact Registry, kein Cloud NAT.
- Eine zusätzliche `terraform_data` (oder
  `null_resource`) für die Bootstrap-Complete-Trigger.

### Angriffsfläche

- **Reduziert gegenüber Cloud-NAT-Variante.** Kein
  egress-fähiger Pfad ins öffentliche Internet
  während READY. Während `BOOTSTRAPPING` ist Egress
  auf `tcp/443` zu den spezifizierten GCS-Bereichen
  beschränkt.
- **Versorgungskette reduziert:** Zwei Quellen:
  GCP-signiertes Debian-Image (Self-Link) und
  Operator-kontrolliertes Artefakt (SHA-256 + Minisign).
- **Pattern-Guard-Konformität:** Salts und
  DB-Passwörter werden zur Laufzeit erzeugt,
  niemals im Plan, niemals im Startup-Script,
  niemals in Logs.

### Phase-3-Invarianten

- **Erhalten:** Lab-Isolation, Default-Deny-Egress
  (bleibt aktiv, Bootstrap-Firewall ist additiv),
  keine externe IP, keine Foundation-Mutation,
  Image-Self-Link, Plan-Determinismus,
  Plan-als-Source-of-Truth, Runtime-State als SSoT,
  CLI-only Transitions, Pattern-Guard, Cost-Guard,
  v4-Closeout-Fixes, TTL-Mechanik.
- **Relaxiert:** keine dauerhafte Relaxation.
  Die Bootstrap-Firewall ist eine **temporäre,
  plan-kontrollierte** Lockerung des Egress.
  Sie wird im selben Plan-Lifecycle entfernt.

### Phase-3-Closeout-Konflikte

Keine. Die v4-Closeout-Fixes (Credential-Preflight
Exit 18, Plan-Freshness Exit 19, Destroy-Overwrite-
Schutz Exit 10, Verify-Hardening Exit 13) bleiben
unverändert. Ein zusätzlicher Exit 22 ist für
`bbr destroy --from-failure` reserviert.

## Alternatives

### Cloud NAT: ja

Verworfen weil: ~30 EUR Fixkosten bis 2026-09-27
(~12 % des Restbudgets), erweiterte Angriffsfläche,
bricht das Phase-3-Default-Deny-Pattern.

### Artifact Registry ohne Cloud NAT: ja (in Phase 4.x möglich)

Funktioniert ohne Cloud NAT über Private Google Access.
Nicht in Phase 4.0 erforderlich.

### VPC Service Controls (VPC-SC)

Verworfen weil: BBR-Projekt ist Single-Project-
Single-Operator. VPC-SC würde Komplexität hinzufügen
ohne wesentlichen Sicherheitsgewinn.

### Cloud NAT nur für Bootstrap (zeitlich befristet)

Verworfen weil: GCS-Tarball-Pfad ist bereits
Cloud-NAT-frei. Kein Anwendungsfall für Live-Bootstrap.

### Allgemeine Internetfreigabe während Bootstrap

Verworfen weil: Bricht die Phase-3-Default-Deny-
Invariante. Widerspricht dem Reproduzierbarkeits-
Prinzip (Live-Downloads können je nach Tageszeit
unterschiedliche Versionen liefern).

## Verbleibende Betreiber-Annahmen

Diese sind **keine** Architekturentscheidungen mehr.
Sie sind **Betreiber-Verantwortung** und werden in
`notes/PHASE-4-PLAN.md` Sektion 14 vollständig
aufgelistet. Kurzform:

1. **GCS-Lifecycle-Rules** (Aufbewahrungsdauer alter
   Artefakte)
2. **Bucket-Location** (welche Region — Vorschlag
   `europe-west3`, identisch zum Foundation-Bucket)
3. **Project-Struktur** (gleiches GCP-Projekt wie
   Foundation, oder separates Bootstrap-Projekt)
4. **Logging-Aufbewahrung** (wie lange werden
   `/var/log/bbr/*.log` lokal aufbewahrt, werden sie
   exportiert?)

## Referenzen

- `notes/PHASE-3-PLAN.md` (Phase-3-Architektur, Vorlage)
- `ADR-0009-lab-lifecycle.md` (Phase-3-Lifecycle,
  WireGuard-Hypothese)
- `ADR-0010-phase-4-appliance-bootstrap.md`
  (Strategie A: GCS-Tarball + Minisign)
- `DIRECTIVE.md` Sections 22, 23, 25
- `ACCEPTANCE-CRITERIA.md`
- `ADR-0003-network.md`
- `terraform/modules/compute-node/main.tf`
- `terraform/modules/network/main.tf`
- `src/bbr/cli.py` (`EGRESS_FORBIDDEN_KEYWORDS`,
  v4-Closeout-Fixes)
- https://cloud.google.com/vpc/docs/configure-private-google-access
  (GCP-Doku zu Private Google Access)
