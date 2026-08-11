#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# provisioning/healthcheck.sh
#
# Healthcheck (Phase 4.0 D.3 / 9.3):
#   - HTTP 200 auf 127.0.0.1
#   - wp core is-installed
# Schreibt /var/lib/bbr/wordpress-ready bei Erfolg.
# -----------------------------------------------------------------------------

set -euo pipefail

DOCROOT="${DOCROOT:-/var/www/html}"
LOG=/var/log/bbr/healthcheck.log

log() {
  printf '%s healthcheck %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$LOG"
}

# HTTP must be exactly 200; curl transport success alone is insufficient.
http_status="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1/)" || {
  log "FAIL: curl transport"
  exit 1
}
if [[ "$http_status" != "200" ]]; then
  log "FAIL: HTTP status=$http_status expected=200"
  exit 1
fi

# WP installed.
if ! wp --allow-root --path="$DOCROOT" core is-installed; then
  log "FAIL: wp core is-installed"
  exit 1
fi

# Marker schreiben.
mkdir -p /var/lib/bbr
cat > /var/lib/bbr/wordpress-ready <<EOF
LAB_ID=wordpress-smoke-001
PACK_ID=wordpress-smoke
NODE_ID=wordpress-smoke-001
WP_VERSION=$(wp --allow-root --path="$DOCROOT" core version)
HEALTHCHECK_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF
chmod 0644 /var/lib/bbr/wordpress-ready
log "PASS"
exit 0
