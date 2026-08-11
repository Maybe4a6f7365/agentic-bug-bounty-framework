#!/usr/bin/env bash
set -euo pipefail
set +x
unset PS4

DOCROOT="${DOCROOT:-/var/www/html}"
LOG=/var/log/bbr/install.log
WP_URL="${WP_URL:-http://127.0.0.1}"
wp --allow-root --quiet --path="$DOCROOT" option update home "$WP_URL"
wp --allow-root --quiet --path="$DOCROOT" option update siteurl "$WP_URL"
wp --allow-root --quiet --path="$DOCROOT" config shuffle-salts
chmod 0640 "$DOCROOT/wp-config.php"
chown www-data:www-data "$DOCROOT/wp-config.php"
printf '%s configure salts complete\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG"
