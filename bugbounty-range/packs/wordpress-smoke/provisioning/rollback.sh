#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# provisioning/rollback.sh
#
# Cleanup-Pfad nach Bootstrap-Failure (Phase 4.0 A.6, D.6).
# KEIN In-Place-Upgrade. Rollback = Destroy + Create.
# Dieses Skript entfernt lokal die Spuren einer fehlgeschlagenen
# Installation, sodass der nächste bbr verify-Lauf einen sauberen
# Zustand vorfindet.
# -----------------------------------------------------------------------------

set -uo pipefail

LOG=/var/log/bbr/rollback.log

log() {
  printf '%s rollback %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$LOG"
}

# Stoppe gestartete Services.
systemctl stop nginx          2>/dev/null || true
systemctl stop php8.2-fpm     2>/dev/null || true
systemctl stop mariadb        2>/dev/null || true

# Entferne entpacktes WordPress.
rm -rf /var/www/html/wp-admin /var/www/html/wp-content /var/www/html/wp-includes \
       /var/www/html/wp-config.php /var/www/html/license.txt /var/www/html/readme.html \
       /var/www/html/index.php /var/www/html/wp-*.php 2>/dev/null || true

# Entferne hochgeladene MariaDB-Daten (NICHT nur Daten leeren — die
# DB-Struktur gehört zum Lab-Lifecycle).
rm -rf /var/lib/mysql /var/lib/bbr/secrets 2>/dev/null || true

# Markierung entfernen.
rm -f /var/lib/bbr/wordpress-ready /var/lib/bbr/ready 2>/dev/null || true

log "rollback: complete"
exit 0
