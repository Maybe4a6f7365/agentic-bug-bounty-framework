# Phase 4 Plan — Controlled Bootstrap und reproduzierbare Applikationsbereitstellung

## Plan v5 correction

Plan v5 is 9 add / 0 change / 0 destroy. Its ninth address is the bucket-scoped
storage object-viewer binding for the dedicated WordPress lab service account.
`remove_after_bootstrap` is false and no READY transition re-applies Terraform.
Real verify must pass the documented GCP and IAP-SSH checks before lifecycle
state advances.

Status: Implemented in code/tests/schemas; EXECUTE gate pending.
Verfasser: Phase 4 Planning, delegiert an Claude Code Opus 5,
finalisiert durch Hermes nach 13 Punkten Architektur-Review.
Bezug: `notes/PHASE-3-PLAN.md`, `DIRECTIVE.md` (Sections 22–25),
`ACCEPTANCE-CRITERIA.md`, `ADR-0009-lab-lifecycle.md`,
`ADR-0010-phase-4-appliance-bootstrap.md`,
`ADR-0011-phase-4-network-isolation.md`.

Die geplanten Source-, Schema-, Terraform-, Manifest- und
CLI-Änderungen sind implementiert. Live-GCP-Ausführung bleibt
ausdrücklich außerhalb dieses Stands.

## 1. Status und Vorgeschichte

Phase 0–3 sind abgeschlossen. Phase 3 v4 Closeout ist
committed (HEAD `5f89a1f12a7583607f1ad3848bfb99401a6808f0`).
Der vollständige Lifecycle wurde erfolgreich durchlaufen:

```
Create → READY → Destroy → DESTROYED
```

Die v4-Closeout-Fixes (Credential-Preflight Exit 18,
Plan-Freshness-Check Exit 19, Destroy-Overwrite-Schutz
Exit 10, Verify-Firewall-Filter-Fix, Verify-Runtime-State-
Consistency Exit 13) sind verbindlich.

Die in `ADR-0009` dokumentierte WireGuard-Routing-Hypothese
ist **nicht** verifiziert und bleibt eine Arbeitshypothese.

Phase 4 ist die erste Phase, die den Phase-3-Vertikalschnitt
verlässt: kontrolliertes Bootstrap einer Anwendung
(konkret: WordPress) **ohne** Verlust der Phase-3-
Invarianten.

## 2. Scope (in)

- Architekturentwurf für **eine** neue Lab-Klasse:
  `wordpress-smoke` (Single-Node raw-vm, applikationsfähig,
  reproduzierbar).
- Bootstrap-Strategie-Entscheidung (ADR-0010):
  Offline gebautes Release-Artefakt in GCS, verifiziert
  über SHA-256 + Minisign.
- Netzwerk-Entscheidung (ADR-0011): kein Cloud NAT,
  kein Artifact Registry, Private Google Access.
- Runtime-State-Erweiterung um `artifact_*`,
  `bootstrap_*`, `install_*`, `health_status`,
  `bootstrap_duration_seconds` und Sub-State-Blöcke.
- Lifecycle-Refinement auf 12 Zustände mit definierten
  Ein-/Austritten.
- MariaDB **lokal** auf der Lab-VM (kein Cloud SQL).
- WordPress-Pack-Design-Skizze (generisch, ohne
  Produkt-Spezialcode im Plattformkern).
- Kostenabschätzung gegen das 245 EUR Budget.
- Risikoanalyse (akzeptiert / mitigiert / zukünftig).
- Migrationspfad Phase 4.0 → 4.1 → 4.x.
- Eindeutige Aussage zur Implementierungsreife.

## 3. Scope (out)

- Keine Implementierung. Keine Terraform-Module, keine
  Schema-Erweiterungen, keine CLI-Code-Änderungen, keine
  Pack-Manifest-Änderungen, keine Tests.
- Keine Cloud NAT, kein Artifact Registry, keine GCS-Buckets,
  keine Service Accounts, keine Firewall-Regeln werden in
  dieser Sitzung erzeugt.
- Keine `terraform init / plan / apply / validate`.
- Keine `gcloud create / apply / update / destroy`.
- Keine Image-Builds, keine Container-Builds.
- Kein Tarball-Build, kein Minisign-Schlüssel.
- Keine Commits, keine Pushes.
- Keine Änderungen an getrackten Dateien.
- Keine Multi-Node-Labs, keine Compose-Driver-Erweiterung,
  keine Snapshots, keine Scenarios.
- Keine neuen ADRs (ADR-0010 und ADR-0011 sind die
  abschließenden Architektur-Dokumente).

## 4. Vererbte Phase-3-Grundprinzipien

Die folgenden Invarianten aus Phase 3 sind in Phase 4
unverändert gültig. Jede Verletzung muss im ADR explizit
benannt und begründet werden.

1. **Foundation-Unantastbarkeit.**
2. **Lab-Isolation.**
3. **Keine externe IP auf Lab-VMs.**
4. **Default-Deny Egress** (Priorität 65000).
5. **Kein Cloud NAT** außer explizit geplant und reviewed.
6. **Image-Self-Link** (kein moving family).
7. **Plan-Determinismus.**
8. **Plan-als-Source-of-Truth.**
9. **Runtime-State als SSoT.**
10. **CLI-only Transitions.**
11. **Pattern-Guard** (keine privaten Keys in getrackten
    Dateien — Minisign-Private-Key bleibt analog zu
    WireGuard-Private-Key offline auf der Workstation).
12. **Cost-Guard** (`PHASE3_SMOKE_CYCLE_LIMIT_EUR = 1.00`).
13. **v4-Closeout-Fixes** (Exit 10, 13, 18, 19; Exit 22
    reserviert für `bbr destroy --from-failure`).
14. **TTL-Mechanik.**

## 5. Verbindliche Architekturentscheidungen

Diese Entscheidungen sind **Architektur**, nicht
Betreiber-Annahmen. Sie sind im ADR-0010 oder ADR-0011
vollständig dokumentiert; hier die Kurzform.

### A.1 Bootstrap-Quelle

**Offline gebautes Release-Artefakt in Google Cloud Storage**
(ADR-0010 D.1).

- `artifact.tar.zst` (komprimierte Payload)
- `artifact.tar.zst.sha256` (Hash)
- `artifact.tar.zst.minisig` (Ed25519-Signatur)
- `manifest.json` (Metadaten)

Lab-VM zieht via **Private Google Access** (kein NAT).

### A.2 Signaturverfahren

**Minisign mit Ed25519** (ADR-0010 D.2).

- Kleine TCB (~600 Zeilen C, statischer Binary).
- Offline-Verifikation, kein Keyserver, kein Trust-DB.
- Mehrere Public Keys im Trust-Store möglich
  (Rotation).
- **Kein** GPG.

### A.3 Bootstrap-Reihenfolge

Hart kodiert, mit definierten Exit-Codes
(ADR-0010 D.3):

```
Download
↓
Signaturprüfung (minisign -V) → Exit 31
↓
SHA-Prüfung (sha256sum -c) → Exit 32
↓
Manifestprüfung (jq -e) → Exit 33/34
↓
Entpacken (tar -xf) → Exit 35
↓
Installation (install.sh) → Exit 36
↓
Konfiguration (wp-config.php + shuffle-salts) → Exit 37
↓
Start (MariaDB + php-fpm) → Exit 38
↓
Healthcheck (HTTP 200 + wp core is-installed) → Exit 39
```

**Kein** automatischer Retry. Bei Fail → `FAILURE` →
`rollback.sh` → Operator entscheidet.

### A.4 Schlüsselmodell

Mehrere Public Keys im Trust-Store
`var.minisign_trust_store` (ADR-0010 D.4):

- Ed25519-Public-Key, 32 Byte, Base64.
- Im Plan, in `metadata_startup_script`, in
  Runtime-State (`minisign_public_key`) und auf VM
  (`/var/lib/bbr/keys/minisign.pub`, Mode 0644).
- **Kein** Private Key im Plan, in GCS, im Repo.
- Rotation: neuer Key zum Trust-Store, alter Key
  bleibt `n_min` Monate für alte Artefakte
  verifizierbar.
- Nach Trust-Store-Entfernung: alte Artefakte
  nicht mehr verifizierbar → `SIGNATURE_INVALID`.

### A.5 Versionierte Verzeichnisse

**Immutable, kein `latest`, kein Überschreiben**
(ADR-0010 D.5):

```
gs://bbr-bootstrap-<project>/
    artifacts/
        wordpress/
            6.8.2-r1/  ← bleibt für immer unter diesem Pfad
            6.8.2-r2/
```

### A.6 Rollback

**Destroy + Create, keine In-Place-Upgrades**
(ADR-0010 D.6):

```
ROLLBACK = bbr destroy(aktuelles Lab) +
            bbr create(neues Lab mit anderer Artefakt-Version)
```

### A.7 Lokale MariaDB

**MariaDB läuft auf der Lab-VM, kein Cloud SQL**
(ADR-0010, PHASE-4-PLAN 8).

- DB-Pfad `/var/lib/mysql/`, Bind-Adresse
  `127.0.0.1`.
- DB-Passwörter werden zur Laufzeit erzeugt
  (`openssl rand -base64 32`).
- Begründung: Isolation, Reproduzierbarkeit,
  Kosten, Einfachheit (kein Cloud-SQL-Connector,
  kein VPC-Peering).

### A.8 Runtime-Secrets statt Repository-Secrets

**Alle Geheimnisse zur Laufzeit auf der VM erzeugt**
(ADR-0010 D.8, PHASE-4-PLAN 7).

- DB-Passwörter: `openssl rand -base64 32`.
- WP-Salts: `wp config shuffle-salts`.
- WP-Auth-Keys: `wp config shuffle-salts`.

**Secrets erscheinen niemals in:**

- Terraform-State (keine Variablenwerte, keine Outputs)
- Runtime-State `state/<lab-id>.json` (nur Existenz,
  keine Werte)
- Git-Repository
- Logs (durch `set +x` + `unset PS4` + `wp-cli --quiet`)
- Bootstrap-Ausgaben
- Diagnose-Reports (`bbr diagnose` schreibt nur
  nicht-sensitive Subset)

### A.9 Egress-Modell

**Keine allgemeine Internetfreigabe; spezifizierte
Bootstrap-Egress-Allowlist** (ADR-0011 D.4):

| Eigenschaft | Wert |
|---|---|
| Richtung | EGRESS |
| Priorität | 1000 |
| Quelle | Lab-Tag `wordpress-smoke-001` |
| Ziel | `199.36.153.4/30` (restricted GCS VIPs) |
| Protokoll/Port | `tcp/443` |

Aktiv ab `CREATED` und persistent bis `bbr destroy`.

Phase-3-Default-Deny-Egress (Priorität 65000) bleibt
aktiv. Im READY-Zustand bleibt ausschließlich der GCS-Allowlist-Egress.

### A.10 GCS-Bucket-Topologie

**Architektur-Eigenschaften des Buckets** (PHASE-4-PLAN 6.1):

- **Uniform Bucket-Level Access:** aktiviert
  (kein Legacy-ACL-Modell)
- **Public Access Prevention:** `enforced`
- **Objektversionierung:** aktiviert (für
  Wiederherstellung bei versehentlichem Überschreiben)
- **Verschlüsselung:** Google-managed Standard
  (CMEK ist **kein** Architektur-Standard; nur mit
  begründeter Anforderung in Phase 4.x)
- **Region:** `europe-west3` (gleiche Region wie
  Foundation)
- **Lifecycle-Policy:** Betreiber-Verantwortung (siehe
  Sektion 14)
- **Retention:** Betreiber-Verantwortung

## 6. Architektur-Komponenten

### 6.1 GCS-Bucket-Detailarchitektur

```
gs://bbr-bootstrap-<project>/
├── artifacts/
│   └── <app>/
│       └── <version>-<revision>/
│           ├── artifact.tar.zst
│           ├── artifact.tar.zst.sha256
│           ├── artifact.tar.zst.minisig
│           └── manifest.json
├── _trust/
│   └── minisign-public-keys.json     (Trust-Store)
└── _audit/
    └── releases.log                  (Betreiber-Audit-Log)
```

**Bucket-Sicherheits-Architektur:**

- **Uniform Bucket-Level Access:** `iam.uniformBucketLevelAccess.enabled = true`.
  ACLs werden vollständig ignoriert; Berechtigungen
  werden ausschließlich über IAM verwaltet.
- **Public Access Prevention:** `iam.publicAccessPrevention = "enforced"`.
  Jeder Versuch, `allUsers` oder `allAuthenticatedUsers`
  als Principal zu setzen, wird abgelehnt.
- **Objektversionierung:** `versioning.enabled = true`.
  Alte Versionen werden nie überschrieben, sondern
  bleiben als Vorgängerversion erhalten.
- **Verschlüsselung:** `encryption.default_kms_key_name`
  ist **nicht** gesetzt (Google-managed Standard
  Encryption). CMEK ist **kein** Architektur-Standard
  für Phase 4.0; eine Einführung erfordert eine
  begründete Anforderung und ein eigenes ADR.
- **Bucket-Lock:** nicht gesetzt (Phase 4.0 erlaubt
  das Löschen alter Versionen durch den Betreiber).

**Least-Privilege-Zugriffsmodell:**

| Principal | Rolle | Zweck |
|---|---|---|
| `bbr-lab-<lab-id>-sa` | `roles/storage.objectViewer` (nur auf Bucket-Ebene, scoped via IAM-Condition `resource.name.startsWith('artifacts/')`) | Bootstrap-Pull vom Lab |
| Build-Service-Account (Operator-verwaltet) | `roles/storage.objectCreator` + `roles/storage.objectAdmin` (nur auf `artifacts/`-Pfad) | Artefakt-Upload vom Build-Prozess |
| Operator (manuell, gelegentlich) | `roles/storage.admin` (nur auf Bootstrap-Bucket, **nicht** project-weit) | Release-Inspektion, manuelles Rollback |

**Architektur-Verbot:** Keine `allUsers`- oder
`allAuthenticatedUsers`-Bindings. Keine `roles/owner`
oder `roles/editor` auf Bucket-Ebene.

### 6.2 Komponenten-Tabelle

| Komponente | Zweck | Phase-3-Erbgut | Phase-4-Neuheit |
|---|---|---|---|
| `terraform/lab/<lab-id>/` | Eigenständiger Lab-Root | existiert | unverändert |
| `modules/network` | Per-Lab-Netzisolation | existiert | unverändert |
| `modules/compute-node` | VM und Ingress-Firewalls | existiert | **erweitert** um Bootstrap-Egress-Firewall (Priorität 1000) und `terraform_data`-Trigger |
| Per-Lab Subnet | Isolation | `private_ip_google_access = true` | unverändert |
| Lab Runtime Service Account | GCP-API-Aufrufe | ohne Rollen | **erweitert** um `storage.objectViewer` scoped auf BBR-Bucket |
| `metadata_startup_script` | Bootstrap-Skript | schreibt nur Readiness-Marker | **erweitert**: rendert das vollständige Bootstrap-Skript |
| GCS Bucket `bbr-bootstrap-<project>/` | Release-Artefakte | nicht vorhanden | **neu**, mit A.10-Eigenschaften |
| Minisign Trust-Store | Public-Key-Verifikation | nicht vorhanden | **neu** im Plan als `var.minisign_trust_store` |
| MariaDB (lokal) | Datenbank | nicht vorhanden | **neu** auf der Lab-VM |
| Runtime-State | Lifecycle-SSoT | existiert | **erweitert** um neue Felder (siehe Sektion 7) |

## 7. Release-Manifest

### 7.1 Manifest-Datei

Jedes Release-Verzeichnis enthält zusätzlich zu den
drei Artefakt-Dateien eine `manifest.json` mit
folgenden **Pflichtfeldern**:

| Feld | Typ | Zweck |
|---|---|---|
| `manifest_version` | integer (z. B. `1`) | Schema-Version des Manifests selbst. Bootstrap prüft: `manifest_version >= 1`. |
| `artifact_version` | string (z. B. `"6.8.2-r1"`) | Version des Release-Artefakts (siehe Sektion 10.3 Versionierung). |
| `bootstrap_version` | string (z. B. `"4.0.0"`) | Version des Bootstrap-Skripts (für Kompatibilitäts-Check zwischen Plan und Tarball). |
| `wordpress_version` | string (z. B. `"6.8.2"`) | Exakte WordPress-Core-Version (semver). |
| `php_version` | string (z. B. `"8.3"`) | PHP-Version, gegen die WordPress gebaut wurde. |
| `mariadb_version` | string (z. B. `"10.11.6"`) | MariaDB-Version (für Kompatibilität mit PHP-Connector). |
| `git_commit` | string (40-stelliger Hex-SHA) | Commit-Hash des Operator-Build-Repos, aus dem das Artefakt gebaut wurde. |
| `build_id` | string (z. B. `"build-2026-07-26-001"`) | Eindeutiger Identifier des Build-Laufs (für Audit-Trail). |
| `build_timestamp` | ISO-8601 UTC | Zeitpunkt des Build-Abschlusses. |
| `artifact_size` | integer (Bytes) | Größe der `artifact.tar.zst`. |
| `artifact_sha256` | string (64-stelliger Hex) | SHA-256 der `artifact.tar.zst` (muss mit `artifact.tar.zst.sha256` übereinstimmen). |
| `artifact_signature` | string (Minisign-Format) | Base64-kodierte Minisign-Signatur der `artifact.tar.zst`. |
| `supported_platform` | string (z. B. `"debian-12-bookworm-v20260721"`) | Erwartete Base-Image-Self-Link (muss mit `var.base_image_self_link` im Plan übereinstimmen). |

### 7.2 Beispiel-Manifest

```json
{
  "manifest_version": 1,
  "artifact_version": "6.8.2-r1",
  "bootstrap_version": "4.0.0",
  "wordpress_version": "6.8.2",
  "php_version": "8.3",
  "mariadb_version": "10.11.6",
  "git_commit": "abc1234567890def...",
  "build_id": "build-2026-07-26-001",
  "build_timestamp": "2026-07-26T18:00:00Z",
  "artifact_size": 52428800,
  "artifact_sha256": "abc1234567890def...",
  "artifact_signature": "untrusted comment: ...\nRU...==",
  "supported_platform": "debian-12-bookworm-v20260721"
}
```

### 7.3 Manifest-Prüfung im Bootstrap

Bootstrap validiert **vor** dem Entpacken:

1. `jq -e '.manifest_version >= 1'` (Schema-Version)
2. `jq -e '.artifact_sha256 == computed_sha256'` (Hash-Konsistenz)
3. `jq -e '.supported_platform == var.base_image_self_link'`
   (Plattform-Kompatibilität)

Jede Verletzung → Exit 33 oder 34 → `FAILURE`.

## 8. Runtime-State (vollständig)

### 8.1 Felder mit Autorschaft und Lebenszyklus

| Feld | Geschrieben von | Wann | Unveränderlich nach |
|---|---|---|---|
| `lab_id`, `pack_id` | `bbr plan` | bei Plan-Erstellung | nach `DEFINED`-Transition |
| `state` | `bbr verify`, `bbr destroy` | bei jeder Lifecycle-Transition | bis zur nächsten Transition |
| `plan_file`, `plan_sha256`, `source_commit`, `backend_prefix` | `bbr create` | bei Plan-Anwendung | nie (Versionswechsel erfordert neuen Plan) |
| `artifact_version` | `bbr create` | bei Plan-Anwendung | nie (Artefakt ist im Plan eingefroren) |
| `artifact_uri` | `bbr create` | bei Plan-Anwendung | nie |
| `artifact_sha256` | `bbr create` | bei Plan-Anwendung | nie |
| `artifact_signature` | `bbr create` | bei Plan-Anwendung | nie |
| `minisign_public_key` | `bbr create` | bei Plan-Anwendung | nie |
| `bootstrap_started_at` | `bbr verify` | beim Übergang `CREATED → BOOTSTRAPPING` | nach `READY`-Transition |
| `bootstrap_finished_at` | `bbr verify` | beim Übergang `VERIFYING_ARTIFACT → INSTALLING` | nie |
| `install_started_at` | `bbr verify` | beim Übergang `INSTALLING → CONFIGURING` | nie |
| `install_finished_at` | `bbr verify` | beim Übergang `CONFIGURING → STARTING` | nie |
| `health_status` | `bbr verify` | bei jedem Healthcheck | nie (wird aktualisiert) |
| `bootstrap_duration_seconds` | `bbr verify` | bei `bootstrap_finished_at` | nach `READY`-Transition |
| `transition_history[]` | `bbr verify`, `bbr destroy` | bei jeder Transition | **append-only**, nie überschrieben |
| `bootstrap_state.*` | `bbr verify` | während BOOTSTRAPPING-Phase | nach `READY`-Transition (Observability-Wert) |
| `install_state.*` | `bbr verify` | während INSTALLING-Phase | nach `READY`-Transition |
| `configuring_state.*` | `bbr verify` | während CONFIGURING-Phase | nach `READY`-Transition |
| `health_state.*` | `bbr verify` | bei jedem Healthcheck | **nie** (wird aktualisiert) |
| `failure_state.*` | `bbr verify` (Failure-Pfad) | bei Fail | nie |
| `rollback_state.*` | `bbr destroy --from-failure` | bei Destroy mit `--from-failure` | nach `DESTROYED`-Transition |

### 8.2 Unveränderliche Felder

`transition_history` ist **append-only**: jede Transition
wird angehängt, kein bestehender Eintrag wird überschrieben.
Dies ist die Phase-3-Invariante "vollständige
`transition_history` erforderlich".

`artifact_*` und `minisign_public_key` werden bei
`bbr create` einmal geschrieben und danach nie mehr
geändert. Sie sind durch die `plan_sha256` kryptografisch
gebunden (jede Änderung würde Plan-Re-Generation
erfordern).

### 8.3 Aktualisierbare Felder

`health_status` und `health_state.*` werden bei jedem
Healthcheck aktualisiert. Sie sind observabel und
dokumentieren den aktuellen Zustand.

### 8.4 Beispiel-Inhalt (vollständig)

```json
{
  "lab_id": "wordpress-smoke-001",
  "pack_id": "wordpress-smoke",
  "state": "HEALTHY",
  "plan_file": "/tmp/bbr-phase4-wordpress-smoke-create-v1.tfplan",
  "plan_sha256": "...",
  "source_commit": "...",
  "backend_prefix": "labs/wordpress-smoke-001",
  "artifact_version": "6.8.2-r1",
  "artifact_uri": "gs://bbr-bootstrap-<project>/artifacts/wordpress/6.8.2-r1/artifact.tar.zst",
  "artifact_sha256": "abc123...",
  "artifact_signature": "untrusted comment: ...\nRU...==",
  "minisign_public_key": "RW...==",
  "bootstrap_started_at": "2026-07-26T20:00:00Z",
  "bootstrap_finished_at": "2026-07-26T20:01:30Z",
  "install_started_at": "2026-07-26T20:01:31Z",
  "install_finished_at": "2026-07-26T20:03:00Z",
  "health_status": "HEALTHY",
  "bootstrap_duration_seconds": 90,
  "transition_history": [
    {"to": "DEFINED", "at": "...", "by": "operator"},
    {"to": "VALIDATED", "at": "...", "by": "bbr plan"},
    {"to": "PLANNED", "at": "...", "by": "bbr plan"},
    {"to": "CREATED", "at": "...", "by": "bbr create"},
    {"to": "BOOTSTRAPPING", "at": "...", "by": "bbr verify"},
    {"to": "VERIFYING_ARTIFACT", "at": "...", "by": "bbr verify"},
    {"to": "INSTALLING", "at": "...", "by": "bbr verify"},
    {"to": "CONFIGURING", "at": "...", "by": "bbr verify"},
    {"to": "STARTING", "at": "...", "by": "bbr verify"},
    {"to": "READY", "at": "...", "by": "bbr verify"},
    {"to": "HEALTHY", "at": "...", "by": "bbr verify"}
  ],
  "bootstrap_state": {
    "phase": "COMPLETED",
    "artifact_pulled": true,
    "minisign_verified": true,
    "sha256_verified": true,
    "manifest_verified": true,
    "extracted_to": "/var/www/html",
    "retry_count": 0,
    "egress_allow": {
      "enabled": true,
      "purpose": "GCS-Pull für artifact.tar.zst",
      "scope": "tcp/443 → 199.36.153.4/30",
      "active_during_phases": [
        "CREATED", "BOOTSTRAPPING", "VERIFYING_ARTIFACT",
        "INSTALLING", "CONFIGURING", "STARTING"
      ],
      "removal_state": "until_destroy"
    }
  },
  "install_state": {
    "phase": "COMPLETED",
    "wp_version": "6.8.2",
    "checksum_verified": true,
    "db_initialized": true,
    "started_at": "...",
    "finished_at": "..."
  },
  "configuring_state": {
    "phase": "COMPLETED",
    "salts_source": "runtime_generated",
    "wp_config_rendered": true
  },
  "health_state": {
    "phase": "HTTP_200",
    "last_check_at": "...",
    "consecutive_passes": 3,
    "wp_is_installed": true
  },
  "failure_state": {
    "phase": null,
    "error_class": null,
    "error_message": null,
    "occurred_at": null,
    "last_successful_phase": null
  },
  "rollback_state": {
    "phase": null,
    "actions_taken": [],
    "started_at": null,
    "finished_at": null
  }
}
```

## 9. Lifecycle (12 Zustände)

### 9.1 Zustandsdefinitionen mit Bedeutung, Eintritt, Abbruch

| Zustand | Bedeutung | Eintrittsbedingung | Abbruchbedingung |
|---|---|---|---|
| `DEFINED` | Pack-Manifest geladen, Lab-ID vergeben | `bbr plan` mit gültigem Manifest | Pack-Validation fail → CLI-Exit |
| `VALIDATED` | Schema-Validation, Cost-Guard, Image-Self-Link OK | `DEFINED → VALIDATED` | Validation fail → CLI-Exit |
| `PLANNED` | terraform plan erzeugt, SHA-256 berechnet, Runtime-State geschrieben | `VALIDATED → PLANNED` | Plan-Fehler, Image-Validation fail → CLI-Exit |
| `CREATED` | terraform apply ausgeführt, GCP-Ressourcen vorhanden | `bbr create` mit allen Gates grün | Apply-Fehler → CLI-Exit mit Cleanup-Hinweis |
| `BOOTSTRAPPING` | VM bootet, `metadata_startup_script` läuft an | `bbr verify` beginnt Progress | GCP-VM nicht erreichbar → `FAILURE` |
| `VERIFYING_ARTIFACT` | GCS-Pull + Minisign + SHA-256 + Manifest | BOOTSTRAPPING abgeschlossen | minisign exit ≠ 0 (Exit 31), sha256 mismatch (32), manifest fail (33/34), GCS-Pull fail (30) → `FAILURE` |
| `INSTALLING` | Tarball entpackt, MariaDB init, `wp core install` | VERIFYING_ARTIFACT grün | WP-CLI exit ≠ 0 (36), MariaDB init fail → `FAILURE` |
| `CONFIGURING` | `wp-config.php` gerendert, Salts erzeugt | INSTALLING abgeschlossen | Template-Render fail (37), Salts-Generation fail → `FAILURE` |
| `STARTING` | MariaDB + php-fpm/nginx gestartet | CONFIGURING abgeschlossen | Service-Start fail (38) → `FAILURE` |
| `READY` | HTTP-Server lauscht auf 127.0.0.1:80, `/var/lib/bbr/wordpress-ready` geschrieben | STARTING grün + initialer Healthcheck grün | Healthcheck fail (39) → zurück zu STARTING, max 3 retries → `FAILURE` |
| `HEALTHY` | 3 konsekutive Healthchecks bestanden (HTTP 200, `wp core is-installed`) | READY + 3× consecutive passes | Healthcheck fail → HEALTHY → UNHEALTHY |
| `VERIFIED` | Manueller Operator-Check bestätigt (optional) | `bbr verify --confirm-verified` durch Operator | optional, nicht erzwungen |

### 9.2 Lifecycle-Pfade

```
Plan-Pfad:    DEFINED → VALIDATED → PLANNED (bbr plan)

Create-Pfad:  PLANNED → CREATED → BOOTSTRAPPING
              → VERIFYING_ARTIFACT → INSTALLING
              → CONFIGURING → STARTING → READY
              → HEALTHY → VERIFIED
              (bbr create, dann bbr verify)

Failure-Pfad: BOOTSTRAPPING|VERIFYING_ARTIFACT|INSTALLING
              |CONFIGURING|STARTING → FAILURE
              → ROLLBACK → DESTROYED
              (interner Recorder, by="system"; dann
              bbr destroy --from-failure)

Teardown:     READY|HEALTHY|VERIFIED → STOPPED → DESTROYED
              (bbr destroy)
```

### 9.3 Health-Modell (READY / HEALTHY / VERIFIED)

| Zustand | Bedeutung | Eintrittsbedingung | Prüfkriterien |
|---|---|---|---|
| `READY` | HTTP-Server läuft, initiale Probe bestanden | STARTING grün + `curl -fs http://127.0.0.1/` exit 0 | Genau **eine** erfolgreiche Probe |
| `HEALTHY` | 3 konsekutive Probes bestanden | READY + 3× `curl -fs` exit 0 + `wp core is-installed` exit 0 | 3 Probes in einem 30s-Intervall; jede Probe = HTTP 200 + WP installed |
| `VERIFIED` | Manueller Operator-Check | `bbr verify --confirm-verified` durch Operator nach manueller Inspektion | Operator-bestätigt; nicht automatisch |

**Abbruchbedingungen:**

- `READY` → `STARTING`: Healthcheck fail. Max 3
  Retries. Nach 3 Fails → `FAILURE`.
- `HEALTHY` → `UNHEALTHY`: Healthcheck fail. State
  bleibt observabel, aber Transition zu `UNHEALTHY`
  triggert keine automatische Aktion. Operator
  entscheidet.
- `VERIFIED` ist terminal bis `bbr destroy`.

## 10. Persistenzmodell

**Architektur-Entscheidung:** Phase 4 speichert **keine**
Daten zwischen zwei Lab-Lebenszyklen.

| Daten | Persistenz | Begründung |
|---|---|---|
| **WordPress-Core** | reproduzierbar | Im Tarball; SHA-256 verifiziert; jeder Lab-Start baut auf demselben Core auf |
| **WordPress-Uploads** | **flüchtig** | Auf Lab-VM-Boot-Disk; mit VM zerstört |
| **MariaDB-Daten** | **flüchtig** | Auf Lab-VM-Boot-Disk; mit VM zerstört |
| **MariaDB-Schema** | reproduzierbar | Im Tarball (Initial-Schema + optional Fixtures) |
| **WP-Salts** | **flüchtig** (lebensdauer = Lab) | Zur Laufzeit erzeugt; mit VM zerstört |
| **DB-Passwörter** | **flüchtig** | Zur Laufzeit erzeugt; mit VM zerstört |
| **Minisign Public Key** | im Plan + Runtime-State | Plan-Determinismus; reproduzierbar |
| **Minisign Private Key** | offline (Workstation) | Betreiber-Verantwortung; Backup-Strategie |
| **Bootstrap-Artefakte** | GCS, versioniert, persistent | Immutable, versioniert; **nicht** im Lab-Lebenszyklus enthalten |
| **Runtime-State** | lokal (Repo `/state/`) | Lebenszyklus = Lab-Lebensdauer; bei `bbr destroy` aktualisiert auf `DESTROYED` |
| **Logs** | lokal (`/var/log/bbr/*.log`) | Lebensdauer = Lab; mit VM zerstört |

**Destroy-Verhalten:**

- `bbr destroy wordpress-smoke-001` ruft die
  GCP-Teardown-Routine auf, die alle
  GCP-Ressourcen löscht (VM, Subnet, SA, IAM,
  Firewalls, Bootstrap-Firewall).
- Mit der VM werden alle Runtime-Daten zerstört:
  Uploads, DB-Inhalt, Salts, DB-Passwörter,
  Logs, wp-config.php.
- GCS-Artefakte bleiben erhalten
  (siehe A.5 — immutable).
- Runtime-State wird auf `DESTROYED` aktualisiert.

**Persistenz-Layer zwischen Lab-Zyklen: nicht vorhanden.**

Wer eine persistente WordPress-Installation für
CVE-Reproduktion braucht, nutzt **Phase 4.1**
(Snapshot-Persistenz als eigene ADR, derzeit nicht
definiert).

## 11. Supply-Chain-Modell

### 11.1 Vertrauenskette

```
Operator (Owner des Minisign-Private-Key)
    ↓ signiert
artifact.tar.zst + .sha256 + .minisig + manifest.json
    ↓ uploaded via gsutil
GCS (immutable, versioniert)
    ↓ pulled über Private Google Access
Lab VM
    ↓ verifiziert mit Minisign-Public-Key (im Plan)
    ↓ entpackt
Application (WordPress + MariaDB)
```

**Drei Vertrauens-Anker:**

1. **GCP-signiertes Base-Image** (Self-Link,
   kein moving family).
2. **Minisign-Public-Key** (im Plan eingefroren,
   vom Operator verifiziert).
3. **Operator's Build-Workstation** (offline,
   reproduzierbarer Build-Prozess).

### 11.2 Build-System

**Architektur-Eigenschaft:** Offline Build auf der
Operator-Workstation. Keine CI-Pipeline in Phase 4.0.

```
Operator-Workstation (kein Netzwerk-Zwang)
  ↓
tools/build_bootstrap_tarball.sh:
  1. WordPress-Core-Tarball (sha256-verifiziert)
  2. wp-cli.phar (sha256-verifiziert)
  3. Plugin-Tarballs (sha256-verifiziert)
  4. Theme-Tarballs (sha256-verifiziert)
  5. Composer-Deps (offline aufgelöst)
  6. Packen in artifact.tar.zst (zstd -19)
  7. sha256sum → artifact.tar.zst.sha256
  8. minisign -S -s ~/.bbr-keys/minisign.key
              -m artifact.tar.zst
              -c "BBR WordPress 6.8.2-r1 <datum>"
              → artifact.tar.zst.minisig
  9. manifest.json (13 Felder, siehe Sektion 7)
 10. gsutil cp nach gs://bbr-bootstrap-<project>/
                       artifacts/wordpress/6.8.2-r1/
```

### 11.3 Release-Erzeugung

**Reproduzierbarkeit:** SHA-256 + Minisign garantieren,
dass ein heruntergeladenes Artefakt bit-identisch mit
dem offline gebauten Artefakt ist. Drift ist
ausgeschlossen.

**Versionierung (Sektion 7.1):** `manifest_version`,
`artifact_version`, `bootstrap_version`,
`wordpress_version`, `php_version`, `mariadb_version`
sind alle im Manifest dokumentiert.

### 11.4 Artefakt-Signierung

**Minisign mit Ed25519** (Sektion A.2 + A.4).

- `minisign -S -s <key>` auf der Workstation
- Signatur enthält: `untrusted comment`, dann
  `trusted comment` (vom Signierer gesetzt), dann
  Base64-Blob.
- Public Key wird **gleichzeitig** generiert:
  `minisign -G -p minisign.pub -s minisign.key`.

### 11.5 Integritätsprüfung

**Hart kodierte Reihenfolge im Bootstrap**
(Sektion A.3):

1. `minisign -V` (Signatur)
2. `sha256sum -c` (Hash)
3. `jq -e` (Manifest-Schema)
4. `jq -e` (Manifest-Hash-Konsistenz)
5. `jq -e` (Plattform-Kompatibilität)
6. Erst dann `tar -xf`

Jede Stufe hat einen eindeutigen Exit-Code (30-39).

### 11.6 Release-Freigabe

**Architektur-Mechanismus:**

- `tools/sign_artifact.sh` muss vom Operator
  manuell aufgerufen werden (kein automatischer
  Build, keine CI).
- Vor Signatur: visuelle Inspektion des Manifests
  durch den Operator.
- Nach Signatur: `gsutil cp` mit Workload-Identity
  oder kurzlebigem Service-Account-Key (Empfehlung
  Workload-Identity, **kein** langlebiger Key im
  Repository).

### 11.7 Reproduzierbarkeit

- SHA-256 + Minisign garantieren bit-Identität.
- Image-Self-Link garantiert deterministische
  Compute-Umgebung.
- WP-CLI-Idempotenz garantiert deterministische
  Installationsschritte.
- Tar-Idempotenz garantiert deterministisches
  Entpacken.

### 11.8 Update-Prozess

**Keine In-Place-Upgrades.** Updates bedeuten:

1. Neues Release-Artefakt builden (`6.8.2-r2` oder
   `6.8.3-r1`).
2. GCS-Upload unter neuem versionierten Pfad.
3. Neuen Plan mit neuem `artifact_uri` + neuem
   `artifact_sha256` + neuer Signatur.
4. `APPROVE PHASE 4 EXECUTE` für den neuen Plan.
5. `bbr destroy wordpress-smoke-001`.
6. `bbr create wordpress-smoke-001` (neues Lab).

## 12. Risikoanalyse

Sortierung: nach **Wahrscheinlichkeit × Auswirkung**.
Markierung: **akzeptiert**, **mitigiert**, **zukünftig
(Phase 4.x)**.

### 12.1 Risikomatrix

| # | Risiko | W'keit | Auswirkung | Status | Gegenmaßnahme |
|---|---|---|---|---|---|
| R1 | Supply-Chain Tarball kompromittiert | Niedrig | Hoch | **mitigiert** | SHA-256 + Minisign, offline Build, Trust-Store |
| R2 | Supply-Chain Base-Image kompromittiert | Sehr niedrig | Hoch | **mitigiert** | Image-Self-Link, GCP-signiert, kein moving family |
| R3 | Bootstrap-Idempotenz verletzt | Niedrig | Mittel | **mitigiert** | `allocate_cidr` blockiert Reuse, Lab-Limit = 1 (Hard Cap 2) |
| R4 | Bootstrap-Failure-Modus | Mittel | Niedrig | **mitigiert** | Klare Failure-Klassen, strukturierte `FAILURE`-Phase, `bbr destroy --from-failure` |
| R5 | Secret-Leak | Niedrig | Hoch | **mitigiert** | Laufzeit-Erzeugung, `set +x`, `unset PS4`, `wp-cli --quiet` |
| R6 | Minisign-Private-Key-Verlust | Niedrig | Mittel | **akzeptiert** | Backup-Strategie ist Betreiber-Verantwortung (siehe Sektion 14) |
| R7 | WP-Core CVE während Lifecycle | Mittel | Mittel | **akzeptiert** | Kein Live-Patch; Destroy + neuer Tarball + Create |
| R8 | Image-Veraltung (Debian deprecated) | Niedrig | Mittel | **mitigiert** | Self-Link + Datumsstring; Update = neuer Plan |
| R9 | Rollback-Komplexität | Niedrig | Niedrig | **akzeptiert** | Destroy + Create ist explizit dokumentiert |
| R10 | Idempotenz create→destroy→create verletzt | Niedrig | Hoch | **zukünftig (Phase 4.1)** | Acceptance-Test in Phase 4.1 |
| R11 | Cloud-NAT versehentlich erzeugt | Sehr niedrig | Hoch | **mitigiert** | ADR-0011 D.1 + Plan-Review |
| R12 | Bootstrap-Egress-Firewall bleibt aktiv | Niedrig | Mittel | **mitigiert** | `terraform_data`-Trigger; Phase-3-Default-Deny bleibt aktiv |
| R13 | Lab-Limit-Konflikt | Niedrig | Niedrig | **akzeptiert** | ADR-0009 Limit bleibt unverändert |
| R14 | Pattern-Guard-Verletzung im Tarball | Sehr niedrig | Mittel | **mitigiert** | Offline Build, `wp core verify-checksums`, Pattern-Guard aktiv |
| R15 | Offline-Fähigkeit verloren | Niedrig | Mittel | **akzeptiert** | Architektur-Design; Updates erfordern Destroy + Create |
| R16 | Integritätsprüfung umgangen | Sehr niedrig | Hoch | **mitigiert** | Hart kodierte Reihenfolge, separate Exit-Stufen |
| R17 | GCS-Bucket falsch konfiguriert (public access) | Niedrig | Hoch | **mitigiert** | Public-Access-Prevention `enforced` (Sektion 6.1) |
| R18 | GCS-Lifecycle-Rule löscht aktives Artefakt | Sehr niedrig | Hoch | **mitigiert** | Object Versioning (Sektion 6.1); Betreiber-Verantwortung für Lifecycle-Rules |
| R19 | Operator-Backup des Private-Keys existiert nicht | Mittel | Hoch | **akzeptiert** | Backup-Strategie ist Betreiber-Verantwortung |
| R20 | FQDN-basierter Egress-Filter fehlt (Phase 4.0 nutzt IP-Bereiche) | Mittel | Niedrig | **akzeptiert** | IP-Bereiche sind dokumentiert; FQDN-Filter ist Phase 4.1 |
| R21 | Multi-Node / DB-Persistenz | Niedrig | Mittel | **zukünftig (Phase 4.1)** | Eigene ADR |
| R22 | Cloud SQL Migration | Niedrig | Mittel | **zukünftig (Phase 4.x)** | Eigene ADR bei Bedarf |

### 12.2 Akzeptierte Risiken (Begründung)

| Risiko | Begründung der Akzeptanz |
|---|---|
| R6 (Minisign-Private-Key-Verlust) | Backup-Strategie ist Betreiber-Verantwortung; Architektur verlangt einen sicheren Aufbewahrungsort |
| R7 (WP-Core CVE während Lifecycle) | Reproduzierbarkeit > Live-Patch; geplante Antwort = Destroy + Create mit neuem Artefakt |
| R9 (Rollback-Komplexität) | Destroy + Create ist explizit dokumentiert; Komplexität ist akzeptiert für Determinismus |
| R13 (Lab-Limit-Konflikt) | Phase-3-Limit (1, Hard Cap 2) bleibt aus Sicherheitsgründen |
| R15 (Offline-Fähigkeit verloren) | Architektur-Design-Feature; keine Mitigations möglich |
| R19 (Operator-Backup fehlt) | Backup-Strategie ist Betreiber-Verantwortung |
| R20 (FQDN-Filter fehlt in 4.0) | IP-Bereiche sind eng genug für Phase 4.0; FQDN-Filter ist Phase 4.1 |

### 12.3 Zukünftige Risiken (Phase 4.x)

| Risiko | Phase |
|---|---|
| R10 (Idempotenz create→destroy→create) | Phase 4.1 (Acceptance-Test) |
| R21 (Multi-Node / DB-Persistenz) | Phase 4.1 (eigene ADR) |
| R22 (Cloud SQL Migration) | Phase 4.x (eigene ADR bei Bedarf) |

## 13. Kostenabschätzung

**Budget-Stand:** 245 EUR Restguthaben, gültig bis 2026-09-27.

**Pro-Zyklus-Schätzung (8h):**

| Komponente | Kosten (USD) | Kosten (EUR) |
|---|---|---|
| `e2-small` Compute (8 h) | 0,134 | 0,124 |
| 20 GB `pd-standard` (anteilig 8h von Monat) | 0,0088 | 0,008 |
| GCS Storage (50 MB × 0,020 USD/GB/Monat) | vernachlässigbar | <0,01 |
| GCS Operations (1 GET pro Bootstrap) | <0,001 | <0,001 |
| Minisign-Verify (lokal, keine Kosten) | 0 | 0 |
| **Cloud NAT** | **0 (nicht erzeugt)** | **0** |
| **Artifact Registry** | **0 (nicht erzeugt)** | **0** |
| **Summe pro Zyklus** | **~0,143** | **~0,13** |

**Zusätzliche Speicherkosten:**

- GCS-Storage für Release-Artefakte:
  ~50 MB × 0,020 USD/GB/Monat = ~0,001 USD/Monat
  ≈ <0,01 EUR/Monat.
- Bei 10 Versionen: ~500 MB ≈ 0,01 USD/Monat.

**Bootstrap-Kosten:**

- 1× GET pro Bootstrap (50 MB, internal egress kostenlos).
- GCS-Preise für GET: 0,05 USD / 10k Operations.
- Bei 30 Zyklen/Monat: 0,00015 USD. Vernachlässigbar.

**Gesamt-Phase-4-Budget-Impact:**

- 10 volle Zyklen à 8h: ~1,30 EUR
- Plus GCS-Storage (1 Monat): ~0,01 EUR
- **Gesamt: ≤ 1,35 EUR** (0,55 % des 245 EUR).

**Hard cap:**

- `PHASE3_SMOKE_CYCLE_LIMIT_EUR = 1.00` bleibt
  unverändert. Der WordPress-Pack deklariert
  `per_cycle_eur_limit = 0.20`.

## 14. Verbleibende Betreiber-Annahmen

Diese sind **keine** Architekturentscheidungen. Sie sind
**Betreiber-Verantwortung** und müssen vom Operator
konkret entschieden werden, **bevor** `APPROVE PHASE 4`
erteilt wird.

| # | Annahme | Betreiber-Entscheidung |
|---|---|---|
| B1 | **Speicherort des privaten Minisign-Schlüssels** | z. B. `~/.bbr-keys/minisign.key` (Mode 0600) |
| B2 | **Backup-Strategie für den privaten Minisign-Schlüssel** | z. B. verschlüsseltes Offline-Backup (Paper, USB-Stick) |
| B3 | **Aufbewahrungsdauer alter Artefakte** | GCS-Lifecycle-Policy oder manuelle Operator-Aktion |
| B4 | **GCS-Lifecycle-Rules** | z. B. nicht-löschend (Versionierung allein reicht) |
| B5 | **Operator-Workstation-Setup** | OS, Minisign-Version, `gsutil`-Version |
| B6 | **Release-Freigabeprozess** | wer darf ein neues Artefakt signieren; Review-Checkliste |
| B7 | **Bucket-Location** | Region `europe-west3` (Vorschlag); Betreiber bestätigt |
| B8 | **Bucket-Project-Struktur** | gleiches GCP-Projekt wie Foundation, oder separates Bootstrap-Projekt |
| B9 | **Logging-Aufbewahrung** | Lebensdauer der `/var/log/bbr/*.log` auf der VM (= Lab-Lebensdauer) |
| B10 | **Erstes Release** | WordPress-Version `6.8.2-r1` als Vorschlag |
| B11 | **Minisign-Key-Rotation-Intervall** | z. B. jährlich oder nie |
| B12 | **Trust-Store-Aufbewahrungsfrist für alte Public Keys** | z. B. 12 Monate nach Rotation |

**Was nicht zu den Betreiber-Annahmen gehört (das ist
Architektur):**

- Signaturverfahren (Minisign)
- Offline-Build des Artefakts
- Immutable Verzeichnisse
- Destroy + Create für Rollback
- Lokale MariaDB
- Runtime-Secrets

Diese 6 Punkte sind in den Architektur-Entscheidungen
(A.1–A.10) festgelegt.

## 15. Implementierungsreife

**Eindeutige Aussage: Diese Planung ist implementierungsreif
unter den folgenden 12 Bedingungen.**

### 15.1 Implementierungs-Voraussetzungen

1. **Phase-3-v4-Closeout-Akzeptanz erfüllt.**
   80 Tests grün, kein Regress, vier Closeout-Fixes
   implementiert. (Status: erfüllt per HEAD
   `5f89a1f12a7583607f1ad3848bfb99401a6808f0`.)

2. **12 Betreiber-Annahmen aus Sektion 14 sind
   beantwortet** (B1–B12).

3. **`APPROVE PHASE 4`** wird separat erteilt.

4. **Phase 4 EXECUTE folgt in einer eigenen Planungs-/
   Review-Sitzung** mit Credential-Preflight (Exit 18),
   Plan-Freshness-Check (Exit 19), Destroy-Overwrite-
   Schutz (Exit 10).

5. **Phase 4 DESTROY EXECUTE folgt nach dem Lab-Lifecycle**
   analog Phase 3 DESTROY EXECUTE.

### 15.2 Was die Planung NICHT garantiert

- Dass WordPress 6.8.2 zum EXECUTE-Zeitpunkt frei
  von CVEs ist (operatives Risiko).
- Dass die vier restricted GCS VIPs außerhalb
  `199.36.153.4/30` liegen; der Downloader verwendet genau
  `.4`, `.5`, `.6` und `.7` mit `curl --resolve`.
- Dass das Operator-Backup des Minisign-Private-Key
  existiert (Betreiber-Verantwortung).
- Dass die Labor-Workstation die richtige Minisign-Version
  hat (Betreiber-Verantwortung).

### 15.3 Implementierungs-Out-of-Scope für Phase 4.0

- Phase 4.1 (Multi-Node, DB-Persistenz, FQDN-Filter)
- Phase 4.x (weitere Apps, Cloud SQL bei Bedarf)
- Phase 5 (Compose-Driver)

Diese sind separate Phasen mit eigenen ADRs.

## 16. Was nicht in dieser Planungs-Sitzung passiert

- Kein neuer Code.
- Kein neuer Planfile.
- Kein Terraform-Init, -Plan, -Apply.
- Kein GCS-Bucket, kein Artifact Registry, kein Cloud
  NAT, keine Service-Account-Bindung.
- Kein Image-Build, kein Container-Build, kein Tarball.
- Kein Minisign-Schlüssel.
- Kein Commit, kein Push.
- Keine Anpassung an getrackten Dateien
  (Phase 1+2+3 bleiben bit-identisch).
- Keine Anwendung der Hypothese aus ADR-0009
  (WireGuard-MASQUERADE).

## Build Reproduzierbarkeit

Der implementierte Offline-Build fixiert GNU tar 1.34, zstd 1.5.2,
sha256sum 8.32, minisign 0.9 und jq 1.6. Tar-Einträge werden mit
`--sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner` erzeugt
und mit `zstd -19 --no-progress` komprimiert. Eingaben werden vorab
per SHA-256 geprüft; `verify_bootstrap_tarball.sh` vergleicht optional
einen Rebuild bitgenau. Details stehen in
`packs/wordpress-smoke/BUILD-ENVIRONMENT.md`.

## Phase 4A Release-Implementierung (2026-07-27)

Phase 4A liefert den vollständigen Offline-Runtime-Stack als signiertes
Release: nginx 1.22.1, PHP-FPM 8.2.32 mit WordPress-Erweiterungen,
MariaDB 10.11.18, WordPress 6.8.2, WP-CLI 2.12.0 und Minisign 0.12.
Die 160 Debian-Pakete werden beim Build heruntergeladen und mit
`dpkg-deb -x` in den Bundle-Root extrahiert; der VM-Bootstrap führt
kein `apt-get` aus.

Das feste Custom Image
`projects/your-lab-name-your-researcher-handle/global/images/bbr-debian-12-bootstrap-tools-20260727-v2`
enthält Minisign vor der Artefakt-Verifikation. Der GCE-Default-SA-Pfad
wird ausschließlich für den authentifizierten, bucket-scoped GCS-Pull
verwendet; die Lab-Runtime-SA bleibt als eine der sieben Phase-3-
Ressourcen bestehen. Bucket-IAM ist ein außerhalb des Lab-Plans
dokumentierter einmaliger Release-Infrastruktur-Schritt. Der Lab-Plan
bleibt deshalb **9 add / 0 change / 0 destroy**.

Upload und Create-Plan sind Phase-4A-EXECUTE-Artefakte; ein
`terraform apply` bleibt ausdrücklich außerhalb dieses Standes.

Finaler Create-Plan:
`/tmp/bbr-phase4-wordpress-create-v4.tfplan`,
**9 add / 0 change / 0 destroy**, SHA-256
`f5995993db29c7e8286c0a419d54f72a32d0c637cc0bf4c73a81e1057759aecd`.
