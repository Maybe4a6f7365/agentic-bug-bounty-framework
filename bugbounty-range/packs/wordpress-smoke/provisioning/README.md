# WordPress-Smoke Pack — Provisioning Scripts

Diese Skripte werden auf der Lab-VM nach dem ersten Boot
ausgeführt. Sie sind **Templates** — die echten WordPress-Binaries,
`wp-cli.phar`, Plugin- und Theme-Archive sind **nicht**
Bestandteil dieses Repositories. Sie werden offline durch
`tools/build_bootstrap_tarball.sh` zu einem reproduzierbaren
Artefakt gebaut und in GCS abgelegt.

## Reihenfolge (hart kodiert)

| Exit-Code | Phase | Skript / Befehl |
|---|---|---|
| 30 | Download | `gsutil cp` (GCS → VM) |
| 31 | Signaturprüfung | `minisign -V -p <pub> -m <artifact>` |
| 32 | SHA-256 | `sha256sum -c --strict` |
| 33 | Manifest-Schema | `jq -e` |
| 34 | Manifest-Hash-Konsistenz | `jq -r .artifact_sha256` |
| 35 | Entpacken | `tar --use-compress-program=unzstd -xf` |
| 36 | Installation | `install-wordpress.sh` |
| 37 | Konfiguration | `configure.sh` (wp-config.php) |
| 38 | Start | `systemctl start mariadb / php-fpm / nginx` |
| 39 | Healthcheck | `healthcheck.sh` |

Jeder Fail ist **fatal**. KEIN Skip, KEIN automatischer Retry.
Operator entscheidet, ob `bbr destroy` + `bbr create` läuft.

## Logging

- `/var/log/bbr/bootstrap.log`
- `/var/log/bbr/install.log`
- `/var/log/bbr/healthcheck.log`
- `/var/log/bbr/rollback.log`

Logs sind **nie** automatisch exfiltriert. Operator liest
über IAP-SSH oder WG-Overlay.

## Secrets

- `set +x` und `unset PS4` vor jedem Aufruf, der mit
  Secrets interagiert.
- DB-Passwörter: `openssl rand -base64 32`, in
  `/var/lib/bbr/secrets/`, Modus 0600, root:root.
- WP-Salts: `wp config shuffle-salts`.

## Siehe auch

- ADR-0010 (`docs/architecture-decisions/ADR-0010-phase-4-appliance-bootstrap.md`)
- ADR-0011 (`docs/architecture-decisions/ADR-0011-phase-4-network-isolation.md`)
- PHASE-4-PLAN (`notes/PHASE-4-PLAN.md`)
- BUILD-ENVIRONMENT.md in diesem Verzeichnis
