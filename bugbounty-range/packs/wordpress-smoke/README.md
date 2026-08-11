# WordPress-Smoke Pack

**Phase 4.0 — Controlled Bootstrap und reproduzierbare
Applikationsbereitstellung.**

Dieses Pack erweitert die Phase-3-Lifecycle-Plattform um eine
kontrollierte Anwendungsinstallation. Die Lab-VM (Single-Node
`raw_vm`, Debian 12) zieht einen SHA-256+Minisign-verifizierten
Bootstrap-Tarball aus GCS, installiert WordPress mit
lokaler MariaDB, und führt einen HTTP-200-Healthcheck aus.

## Eigenschaften

- **Pack-ID:** `wordpress-smoke`
- **Version:** `0.4.0`
- **Treiber:** `raw_vm`
- **Architektur:** Single-Node
- **Anwendungs-Stack:** WordPress + PHP-FPM + nginx + MariaDB (lokal)
- **Build-Pfad:** Offline `tools/build_bootstrap_tarball.sh`
- **Bootstrap-Mechanismus:** GCS-Tarball + SHA-256 + Minisign
- **Public-Internet:** Kein Egress während READY

## Architektur

```
┌──────────────────────────────────────────────────────┐
│ GCS: bbr-bootstrap-<project>/                       │
│     artifacts/wordpress/<version>-<revision>/       │
│       - artifact.tar.zst                             │
│       - artifact.tar.zst.sha256                      │
│       - artifact.tar.zst.minisig                     │
│       - manifest.json                                │
└──────────────────────────────────────────────────────┘
                       │
                       │ Private Google Access (kein NAT)
                       ▼
┌──────────────────────────────────────────────────────┐
│ Lab-VM (wordpress-smoke-001)                        │
│ Phase 30  gsutil cp                                  │
│ Phase 31  minisign -V                                │
│ Phase 32  sha256sum -c                               │
│ Phase 33  jq -e .manifest_version >= 1               │
│ Phase 34  jq -r .artifact_sha256 == computed         │
│ Phase 35  tar -xf                                    │
│ Phase 36  install-wordpress.sh                       │
│ Phase 37  configure.sh (wp-config.php + Salts)       │
│ Phase 38  systemctl start mariadb / php-fpm / nginx  │
│ Phase 39  curl http://127.0.0.1/ + wp core installed │
└──────────────────────────────────────────────────────┘
```

## Voraussetzungen

### Operator-Workstation

- Minisign (>= 0.9) mit Private Key
- WordPress-Core, WP-CLI, Plugins, Themes offline
- `zstd`, `tar`, `sha256sum`, `jq` in spezifizierten Versionen
  (siehe `BUILD-ENVIRONMENT.md`)

### GCP

- Bootstrap-Bucket `bbr-bootstrap-<project>` mit:
  - Uniform Bucket-Level Access
  - Public Access Prevention enforced
  - Object Versioning enabled
  - Region: `europe-west3`

### Lab-VM

- Minisign (>= 0.9) für `minisign -V`
- `gsutil` für GCS-Pull
- `tar` mit zstd-Support
- `jq`, `sha256sum`, `openssl`
- `wp-cli` (`/usr/local/bin/wp`)
- `mariadb-server`, `php8.3-fpm`, `nginx`

## Kosten

Pro Zyklus (8h) ca. 0,13 EUR. Per-Cycle-Limit 0,20 EUR.
Phase-3-Limit 1,00 EUR bleibt unverändert.

## Verwendung

```bash
# Operator-Workstation: Artefakt bauen
tools/build_bootstrap_tarball.sh \
  --source-dir ./wordpress-source \
  --input-manifest ./input-sha256.json \
  --output-dir ./out/6.8.2-r1 \
  --minisign-key ~/.bbr-keys/minisign.key \
  --artifact-version 6.8.2-r1 \
  --bootstrap-version 4.0.0 \
  --wordpress-version 6.8.2 \
  --php-version 8.3 \
  --mariadb-version 10.11.6 \
  --supported-platform projects/debian-cloud/global/images/debian-12-bookworm-v20260721 \
  --build-id build-2026-07-26-001

# Operator-Workstation: Upload nach EXECUTE-Gate
gsutil cp ./out/6.8.2-r1/* \
  gs://bbr-bootstrap-<project>/artifacts/wordpress/6.8.2-r1/

# Plattform-CLI: Plan + Create
bbr validate packs/wordpress-smoke
bbr plan    packs/wordpress-smoke --lab-id wordpress-smoke-001
bbr create  wordpress-smoke-001 --plan-file ... --expected-sha256 ... --expected-commit ...
bbr verify  wordpress-smoke-001
bbr destroy wordpress-smoke-001
```

## Lifecycle

12 Zustände (PHASE-4-PLAN Sektion 9):

```
DEFINED → VALIDATED → PLANNED → CREATED → BOOTSTRAPPING
  → VERIFYING_ARTIFACT → INSTALLING → CONFIGURING → STARTING
  → READY → HEALTHY → VERIFIED
```

Plus: `STOPPED → DESTROYED` und `FAILURE → ROLLBACK → DESTROYED`.

## Siehe auch

- `manifest.json` (Pack-Manifest, schema-validiert)
- `BUILD-ENVIRONMENT.md` (Build-Reproduzierbarkeit)
- `provisioning/README.md` (Skript-Dokumentation)
- `docs/architecture-decisions/ADR-0010-...`
- `docs/architecture-decisions/ADR-0011-...`
- `notes/PHASE-4-PLAN.md`
