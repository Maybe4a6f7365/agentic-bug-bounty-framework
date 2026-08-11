# ADR-0010 — Phase 4 Appliance-Bootstrap-Strategie

> Phase-4A correction: plan v5 contains 9 resources, including a bucket-scoped
> object-viewer member for the dedicated lab service account. Real GCP and
> IAP-SSH verification is the default. Bootstrap egress persists until destroy.

Implementation: Phase-4.0 complete in code, schemas and tests; EXECUTE pending.
Validation: 134 collected tests (132 passed, 2 privileged ownership checks
skipped on the unprivileged runner).

Pre-Execute-Korrektur (2026-07-27):
- Blocker A (Backend): terraform-konform. Backend-Block in HCL
  darf keine Variablen enthalten. Phase-3-Mechanismus
  (`terraform init -backend-config=...`) bleibt unverändert.
- Blocker B (Bootstrap-Egress): instanziiert. Plan-Ressourcen
  7 → 8.

Status: Accepted and implemented for Phase 4A.

Phase-4A-Korrektur (2026-07-27): Die Standard-Debian-Laufzeit reicht
nicht aus. Der Release enthält daher den vollständigen offline
extrahierten nginx/PHP-FPM/MariaDB-Stack. Ein festes, aus
`debian-12-bookworm-v20260721` gebackenes Custom Image enthält
Minisign 0.12 als vorgelagerten Trust-Anker. Damit wird vor Ausführung
von Artefaktinhalt signaturgeprüft; die frühere Ablehnung jeglichen
Image-Bakings gilt für den Applikationsstack, nicht für diesen kleinen
Verifier-Trust-Bootstrap.

Bezug: `notes/PHASE-4-PLAN.md` (Abschnitte 5, 6, 7, 8, 9,
10, 11, 12, 13, 14, 15), `ADR-0009-lab-lifecycle.md`,
`ADR-0011-phase-4-network-isolation.md`,
`DIRECTIVE.md` Section 23/27, `ACCEPTANCE-CRITERIA.md`.

## Context

Phase 3 liefert einen vollständig generischen, egress-freien
Single-Lab Raw-VM-Vertikalschnitt. Die VM bootet mit einem
Plan-gerenderten `metadata_startup_script`, das ausschließlich
lokale Betriebssystem-Utilities benutzt und einen statischen
Readiness-Marker schreibt. Es gibt keine Anwendungsinstallation,
kein Herunterladen von Artefakten und keinerlei Egress.

Phase 4 soll erstmals **kontrolliertes Bootstrap** und
**reproduzierbare Applikationsbereitstellung** ermöglichen,
konkret für ein WordPress-Smoke-Pack. Die Strategie muss
verbindlich klären:

1. **Woher kommt das Anwendungs-Binärpaket** (WordPress-Core,
   WP-CLI, Plugins, Themes, Composer-Abhängigkeiten)?
2. **Wie wird die Herkunft verifiziert** (sha256 + Signatur)?
3. **Braucht die VM Internetzugang während des Bootstraps**,
   und falls ja, wie wird der Default-Deny-Egress gelockert
   und wiederhergestellt?
4. **Wie ist der Update-Pfad** ohne In-Place-Upgrades?
5. **Wie bleibt das Lab-Budget (245 EUR, gültig bis
   2026-09-27) im Rahmen**, ohne neue monatliche Fixkosten
   einzuführen?
6. **Wie bleibt der Plan deterministisch** (gleicher Input,
   gleicher Plan, gleicher SHA-256)?

Phase 3 selbst hat das Bootstrap-Problem **bewusst
ausgeklammert**. Phase 4 muss es lösen, ohne die
Phase-3-Invariante "Plan-als-Source-of-Truth",
"Default-Deny-Egress", "keine privaten Keys / keine
Token-Dateipfade in getrackten Dateien", "Cost-Guard
1,00 EUR pro Zyklus" zu unterlaufen.

## Decision (verbindliche Architektur)

### D.1 Bootstrap-Quelle: Offline gebautes Release-Artefakt
in GCS

Das Anwendungs-Binärpaket (`artifact.tar.zst` +
`artifact.tar.zst.sha256` + `artifact.tar.zst.minisig` +
`manifest.json`) wird **offline** in einem privaten GCS-Bucket
abgelegt und vom Lab über **Private Google Access** (kein
Cloud NAT, siehe ADR-0011) gezogen.

Diese Entscheidung ist **Architektur**, keine Annahme:
die Versorgungskette besteht aus genau zwei Quellen
(GCP-signiertes Base-Image + Operator-kontrolliertes
Artefakt), und das Artefakt entsteht offline.

### D.2 Signaturverfahren: Minisign (Ed25519)

Das Integritätsmodell ist ein **Triplet**:

| Datei | Zweck | Erzeugung |
|---|---|---|
| `artifact.tar.zst` | Anwendungs-Payload | offline Build, `zstd -19` |
| `artifact.tar.zst.sha256` | SHA-256-Hash | offline Build (im selben Schritt) |
| `artifact.tar.zst.minisig` | Minisign-Signatur (Ed25519) | offline Build, `minisign -S -s ~/.bbr-keys/minisign.key` |

Minisign ist die **Architekturentscheidung**, nicht eine
Annahme. Die Begründung:

- **Kleine Trusted Computing Base:** Minisign ist ein
  ~600-zeiliges C-Tool, ein einziger statischer Binary,
  auditierbar. Keine GPG-Infrastruktur (Keyring, Trust-DB,
  Web-of-Trust) im Lab.
- **Einfache Offline-Verifikation:** Der Befehl
  `minisign -V -P <pub> -x <sig> -m <msg>` hat keine
  Netzwerkabhängigkeit, keine externe Konfiguration,
  keinen Keyserver.
- **Reproduzierbar:** Minisign erzeugt deterministische
  Signaturen (Ed25519).
- **Keine GPG-Komplexität:** GPG würde einen Keyring,
  eine Trust-DB, ein Agent-Setup und eine
  Versionsabhängigkeit mitbringen, die in einem
  ephemeren, reproduzierbaren Lab nichts zu suchen
  haben.

### D.3 Bootstrap-Reihenfolge (hart kodiert)

```
Download
↓
Signaturprüfung (minisign -V)
↓
SHA-Prüfung (sha256sum -c)
↓
Manifestprüfung (jq -e .schema_version, jq -e .artifact_sha256)
↓
Entpacken (tar --use-compress-program=unzstd -xf)
↓
Installation (install.sh: wp core install, db init)
↓
Konfiguration (wp-config.php rendern, shuffle-salts)
↓
Start (MariaDB + php-fpm/nginx starten)
↓
Healthcheck (HTTP 200 + wp core is-installed)
```

**Abbruchbedingungen (jeder Fail ist fatal, kein Skip):**

| Stufe | Prüfung | Exit-Code | Aktion |
|---|---|---|---|
| Download | GCS-Get HTTP-Status ≠ 200 | 30 | Bootstrap-Fail, `bootstrap_state.error_class = "GCS_PULL_FAILED"` |
| Signatur | `minisign -V` exit ≠ 0 | 31 | Bootstrap-Fail, `error_class = "SIGNATURE_INVALID"`, **keine** SHA-Prüfung (kein Info-Leak) |
| SHA | `sha256sum -c` exit ≠ 0 | 32 | Bootstrap-Fail, `error_class = "SHA256_MISMATCH"` |
| Manifest | `jq -e` Validierung exit ≠ 0 | 33 | Bootstrap-Fail, `error_class = "MANIFEST_INVALID"` |
| Manifest | `manifest.artifact_sha256 != computed_sha256` | 34 | Bootstrap-Fail, `error_class = "MANIFEST_HASH_MISMATCH"` |
| Entpacken | `tar` exit ≠ 0 | 35 | Bootstrap-Fail, `error_class = "EXTRACT_FAILED"` |
| Installation | `install.sh` exit ≠ 0 | 36 | Bootstrap-Fail, `error_class = "INSTALL_FAILED"` |
| Konfiguration | `wp-config.php` render exit ≠ 0 | 37 | Bootstrap-Fail, `error_class = "CONFIG_FAILED"` |
| Start | Service-Start exit ≠ 0 | 38 | Bootstrap-Fail, `error_class = "START_FAILED"` |
| Healthcheck | HTTP ≠ 200 oder `wp core is-installed` exit ≠ 0 | 39 | Bootstrap-Fail, `error_class = "HEALTH_FAILED"` |

**Retry-Verhalten:**

- **Kein** automatischer Retry. Bei jedem Fail geht der
  Bootstrap in `FAILURE`-State und triggert `rollback.sh`.
- Der Operator entscheidet, ob er es nochmal versucht
  (mit `bbr destroy` + `bbr create`).

**Logging:**

- `/var/log/bbr/bootstrap.log` — Bootstrap-Stufen
- `/var/log/bbr/install.log` — Installations-Details
- `/var/log/bbr/healthcheck.log` — Health-Probes
- `/var/log/bbr/rollback.log` — Cleanup-Aktionen
- Logs werden per IAP-Tunnel oder WG-Tunnel vom
  Operator gelesen, **niemals** automatisch exfiltriert.
- **`set +x`** und **`unset PS4`** bei allen Aufrufen,
  die mit Secrets interagieren (`wp config shuffle-salts`,
  `openssl rand`, `mysql_secure_installation`).

### D.4 Schlüsselmodell (Architektur)

**Public Key — Format und Speicherort:**

- Ed25519-Public-Key, 32 Byte, Base64-kodiert (mit
  Minisign-Header `RW...==`).
- **Im Plan** als `var.minisign_public_key` (Klartext,
  nicht geheim).
- **Im `metadata_startup_script`** als gerenderter
  Base64-String.
- **Auf der Lab-VM** unter
  `/var/lib/bbr/keys/minisign.pub` (Mode 0644, root:root).
- **Im Runtime-State** unter `minisign_public_key`
  (Klartext, nicht geheim).

**Mehrere gültige Public Keys:**

- Der Plan referenziert **mehrere** Public Keys in
  einem geordneten Trust-Store
  `var.minisign_trust_store` (Array von
  Base64-kodierten Public Keys, jedes mit
  `key_id` und `valid_since`).
- Bei der Verifikation probiert der Bootstrap
  jeden Key aus, bis einer passt. **Alle** Keys im
  Trust-Store sind gültig.

**Key-Rotation:**

- Eine Rotation fügt einen neuen Public Key zum
  Trust-Store hinzu und entfernt den alten
  (oder markiert ihn als deprecated).
- Ein **alter Artefakt**, das mit dem alten Private
  Key signiert wurde, bleibt verifizierbar, solange
  der **alte Public Key** im Trust-Store ist.
- Der Architektur-Mechanismus: `minisign_trust_store`
  enthält `n` aktive Keys. Rotation = neuer Key
  hinzufügen, alter Key bleibt für `n_min` Monate
  im Trust-Store. Nach Ablauf: alter Key wird entfernt.
- **Artefakte, die mit einem entfernten Key signiert
  wurden, sind nicht mehr verifizierbar.** Der Bootstrap
  failt dann mit `SIGNATURE_INVALID`.

**Verifikation alter Artefakte nach Rotation:**

- Ein altes Lab, das ein altes Artefakt verwendet,
  funktioniert weiterhin, solange der signierende
  Public Key im Trust-Store ist.
- Wenn der Trust-Store den Key entfernt (z. B. nach
  Ablauf der `valid_since` + Aufbewahrungsfrist), dann
  schlägt die Bootstrap-Verifikation für ein altes
  Artefakt fehl.
- Antwort: neues Lab mit aktuellem Artefakt (kein
  In-Place-Update).

**Verhalten bei ungültiger Signatur:**

- `minisign -V` exit ≠ 0 → Exit-Code 31
- `/var/log/bbr/bootstrap.log` enthält:
  `SIGNATURE_INVALID at <timestamp>; key_id=<key> tried; artifact_uri=<uri>`
  — **ohne** die tatsächliche Signatur oder den Public Key
  (kein Info-Leak).
- State transition: aktueller State → `FAILURE`
- `bootstrap_state.error_class = "SIGNATURE_INVALID"`
- `rollback.sh` wird aufgerufen
- Operator liest Log, entscheidet über Destroy + neuen Apply

**Verhalten bei fehlender Signatur:**

- Wenn das heruntergeladene Artefakt keine
  `.minisig`-Datei hat → Exit-Code 31
  (`SIGNATURE_MISSING` als Sub-Klasse)
- Gleiche Aktion wie bei ungültiger Signatur
- **Es gibt keinen Pfad, der eine fehlende Signatur
  toleriert.** Das ist Absicht: jeder Bootstrap MUSS
  eine gültige Minisign-Signatur haben.

### D.5 Versionierte, immutable Verzeichnisse

```
gs://bbr-bootstrap-<project>/
    artifacts/
        wordpress/
            6.8.2-r1/
                artifact.tar.zst
                artifact.tar.zst.sha256
                artifact.tar.zst.minisig
                manifest.json
            6.8.2-r2/
                ...
```

**Architektur-Eigenschaften:**

- **Kein** `latest`-Symlink.
- **Kein** Überschreiben. Eine `6.8.2-r1/`-Version
  bleibt für immer unter diesem Pfad.
- **Kein** Löschen durch den Bootstrap-Prozess.
  Alte Versionen werden durch GCS-Lifecycle-Policy
  oder manuelle Operator-Aktion entfernt.
- Neue Version = neuer Pfad (`6.8.2-r2/`).

### D.6 Rollback: Destroy + Create (keine In-Place-Upgrades)

```
ROLLBACK = Destroy(aktuelles Lab) + Create(neues Lab mit anderer Artefakt-Version)
```

- Es gibt kein `bbr upgrade`, kein Hot-Patch,
  kein `wp core update` im laufenden Lab.
- Ein "Rollback" auf eine alte Version bedeutet:
  Plan mit altem `artifact_uri` (z. B. `6.8.1-r1`)
  + neuer Plan-SHA-256 + neue Minisign-Signatur +
  `bbr destroy wordpress-smoke-001` +
  `bbr create wordpress-smoke-001`.
- Der Plan muss gegen den **alten** Pfad erzeugt
  werden. Solange die alte Version in GCS vorhanden
  ist, ist das möglich.

### D.7 Laufzeit im Lab: nur Konfiguration

Die Runtime im Lab **konfiguriert nur** — sie installiert
nicht.

**Erlaubt im Lab-Bootstrap:**

- `tar --use-compress-program=unzstd -xf` (Entpacken
  eines **bereits heruntergeladenen** Tarballs)
- `mv`, `cp`, `chmod`, `chown` (File-Operationen)
- `wp core is-installed`, `wp core install`,
  `wp config shuffle-salts`, `wp core verify-checksums`
  (WP-CLI auf **bereits entpackten** Dateien)
- `mysql_secure_installation`, `mysql` mit lokalem
  Socket (MariaDB-Setup)
- `php-fpm`, `nginx` start (Dienste starten)
- `curl -fs http://127.0.0.1/` (Healthcheck lokal)

**Verboten im Lab-Bootstrap:**

- `apt-get install`, `apt update`, `apt upgrade`
- `composer install`, `composer update`
- `git clone`, `git pull`
- `wget`
- `curl` zu **nicht-GCS-Zielen** (insbesondere
  wordpress.org, Plugin-Server, apt-Repos)
- `pip install`, `pip3 install`, `npm install`
- `docker run`, `podman run`

Diese Verbotsliste ist die Erweiterung der Phase-3-
`EGRESS_FORBIDDEN_KEYWORDS` und wird in Phase 4.0 im
`src/bbr/cli.py` um die Bootstrap-spezifischen
Patterns erweitert.

Falls technisch unvermeidbar: **explizit** im Plan zu
begründen und im Runtime-State unter
`install_state.justification` zu dokumentieren. Diese
Begründung wird Teil der Review-Pflicht.

### D.8 Secrets: Runtime-Erzeugung, niemals im Repo/Plan/State

Folgende Secrets werden auf der Lab-VM **zur Laufzeit**
erzeugt:

| Secret | Erzeugung | Speicherort VM | Modus | Eigentümer |
|---|---|---|---|---|
| `DB_PASSWORD` | `openssl rand -base64 32` | `/var/lib/bbr/secrets/db_password` | 0600 | root:root |
| `MYSQL_ROOT_PASSWORD` | `openssl rand -base64 32` | `/var/lib/bbr/secrets/mysql_root_password` | 0600 | root:root |
| WP-Salts (8 Stück) | `wp config shuffle-salts` | `/var/lib/bbr/secrets/wp-salts.json` | 0600 | root:root |
| WP-Auth-Keys (8 Stück) | `wp config shuffle-salts` | `/var/lib/bbr/secrets/wp-auth-keys.json` | 0600 | root:root |
| `wp-config.php` | gerendert aus `wp-config.php.tmpl` + lokale Secrets | `/var/www/html/wp-config.php` | 0640 | www-data:www-data |
| Minisign Public Key | im Plan gerendert | `/var/lib/bbr/keys/minisign.pub` | 0644 | root:root |

**Lebensdauer:** Lab-Lifetime (max 8 h). Nach `bbr destroy`
sind die VM und damit alle diese Dateien weg.

**Logging-Regeln:**

- `set +x` vor jedem Aufruf mit Secret-Output
- `unset PS4` (Prompt-String leer)
- Logs gehen nach `/var/log/bbr/*` und werden vom
  Operator per IAP-SSH gelesen, niemals automatisch
  exfiltriert
- `wp config shuffle-salts` selbst logged keine Salts
  (WP-CLI hat einen `--no-color` und `--quiet` Mode,
  der genutzt wird)

**Secrets erscheinen niemals in:**

- Terraform-State (keine Variablenwerte, keine Outputs)
- Runtime-State `state/<lab-id>.json` (nur die
  Existenz von Salts, nicht die Werte)
- Git-Repository (keine `.env`, keine `*.key`,
  keine getrackten Secrets)
- Logs (durch `set +x` + `unset PS4`)
- Bootstrap-Ausgaben (`wp-cli --quiet`)
- Diagnose-Reports (`bbr diagnose` schreibt nur
  nicht-sensitive Subset)

### D.9 Reproduzierbarkeit und Idempotenz

- **Reproduzierbarkeit:** SHA-256 + Minisign +
  Self-Link-Image = drei stabile Identifikatoren,
  die zusammen einen vollständig deterministischen
  Plan ergeben.
- **Idempotenz:** `bbr create` → `bbr destroy` →
  `bbr create` auf demselben Lab-ID funktioniert
  (CIDR-Reuse durch `allocate_cidr` verboten, also
  frische CIDR bei jedem `create`).
- **WP-CLI-Idempotenz:** `wp core install --skip-content`
  ist idempotent (zweimal = no-op, wenn DB bereits
  initialisiert).
- **Tar-Idempotenz:** `tar -xf` ist idempotent
  (zweimal = gleiches Resultat; optional `-k` für
  keine Überschreibung).

## Consequences

### Positive

- **Reproduzierbarkeit:** drei stabile Identifikatoren
  (SHA-256, Minisign, Self-Link-Image) ergeben einen
  vollständig deterministischen Plan.
- **Kosten:** ~0,13 EUR pro Zyklus. Keine monatlichen
  Fixkosten (Cloud NAT, AR, Egress).
- **Sicherheit:** Versorgungskette = 2 Quellen (GCP-Image
  + Operator-Artefakt). Minisign mit Ed25519, kleiner
  TCB, kein GPG-Keyring-Management.
- **Default-Deny bleibt:** Die Bootstrap-Egress-Firewall
  ist eine zusätzliche Schicht; die Phase-3-Deny-Firewall
  (Priorität 65000) bleibt aktiv. Im READY-Zustand hat
  das Lab **keinen** Egress.
- **Pattern-Guard-Konformität:** Minisign-Private-Key
  ist offline und niemals im Repository, im Plan oder
  in GCS. Salts werden zur Laufzeit erzeugt.
- **Phase-3-Invariante erhalten:** Plan-Determinismus,
  Plan-als-Source-of-Truth, Runtime-State als SSoT,
  CLI-only Transitions, v4-Closeout-Fixes,
  TTL-Mechanik, Cost-Guard — alles unverändert gültig.
- **Migrationsfreundlich:** Phase 4.1 (Multi-Node) und
  Phase 4.x (weitere Stacks) folgen demselben Muster.

### Negative

- **Operator-Disziplin für Schlüsselmaterial:** Der
  Minisign-Private-Key muss vom Operator gesichert
  werden (Betreiber-Verantwortung, siehe
  "Verbleibende Betreiber-Annahmen" in
  PHASE-4-PLAN Sektion 14).
- **CVE-Patch erfordert neues Artefakt + neuen Plan +
  neuen Apply.** Kein Live-Patch im Lifecycle.
- **Keine In-Place-Upgrades.** Jeder Versions-Sprung
  ist ein `bbr destroy` + `bbr create`-Zyklus.

## Alternatives

Die folgenden Alternativen wurden evaluiert und aus
den genannten Gründen verworfen. Details in
`notes/PHASE-4-PLAN.md` Abschnitt 5.3.

### B — Artifact Registry Docker-Image

Verworfen weil: Docker im Lab ist ein zusätzlicher
Vektor für Privilege-Escalation und kollidiert mit
der Phase-3-Egress-Forbidden-Keyword-Liste.

### C — Image-Baking (Packer / gcloud image create)

Verworfen weil: Custom-Images sind schwerer zu
auditieren und verlagern die Versorgungskette von
"Tarball + Standard-Image" zu "Custom-Image".

### D — Lokaler Mirror im Lab (zweite VM)

Verworfen weil: Verdoppelt die Compute-Kosten,
verdoppelt die Komplexität, löst das Supply-Chain-
Problem nicht.

### E — Startup-Script live (apt-get, curl wordpress.org)

Verworfen weil: Erfordert Cloud NAT (~32 EUR/Monat
Fixkosten) und bricht die Phase-3-Egress-Forbidden-
Keyword-Liste.

### F — Kombination A+E

Verworfen weil: Verwässert die Reproduzierbarkeit.

### G — SHA-256-only (ohne Minisign)

Verworfen weil: SHA-256 schützt nur vor
**Beschädigung**, nicht vor **Manipulation**. Wer
einen kompromittierten Build kompensiert, kann
seinen eigenen SHA-256 beifügen. Minisign bindet
den Build an einen kryptografischen Schlüssel,
dessen Private Hälfte nur der Operator besitzt.

## Verbleibende Betreiber-Annahmen

Diese sind **keine** Architekturentscheidungen mehr.
Sie sind **Betreiber-Verantwortung** und werden in
`notes/PHASE-4-PLAN.md` Sektion 14 vollständig
aufgelistet. Kurzform:

1. **Speicherort des privaten Minisign-Schlüssels**
   (z. B. `~/.bbr-keys/minisign.key`, Mode 0600)
2. **Backup-Strategie für den privaten Schlüssel**
   (z. B. verschlüsseltes Offline-Backup)
3. **Aufbewahrungsdauer alter Artefakte** (GCS-
   Lifecycle-Policy oder manuelle Operator-Aktion)
4. **Operator-Workstation-Setup** (welches OS, welche
   Minisign-Version)
5. **Release-Freigabeprozess** (wer entscheidet, dass
   ein neues Artefakt signiert wird)

## Referenzen

- `notes/PHASE-3-PLAN.md` (Phase-3-Architektur, Vorlage)
- `ADR-0009-lab-lifecycle.md` (Phase-3-Lifecycle, geltende
  Invarianten)
- `ADR-0011-phase-4-network-isolation.md` (Netzwerk,
  Private Google Access)
- `DIRECTIVE.md` Sections 22–25
- `ACCEPTANCE-CRITERIA.md`
- `src/bbr/cli.py` (`EGRESS_FORBIDDEN_KEYWORDS`,
  Credential-Preflight, Plan-Freshness)
- `src/bbr/pack_validation.py` (Cost-Guard,
  Image-Self-Link-Pflicht)
- `schemas/lab-pack.schema.json` (driver_payload ist
  freie Form, bootstrap_egress_policy bereits spezifiziert)
- `terraform/modules/compute-node/main.tf`
- `terraform/foundation/templates/bastion-startup.sh.tftpl`
  (Pattern für `set +x` / `unset PS4`)
- https://jedisct1.github.io/minisign/ (Minisign-Spec,
  Ed25519-basierte Signaturen)
