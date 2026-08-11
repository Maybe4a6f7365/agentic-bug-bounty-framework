#!/usr/bin/env bash
set -euo pipefail
unset PS4

DOCROOT="${DOCROOT:-/var/www/html}"
SECRETS=/var/lib/bbr/secrets
LOG=/var/log/bbr/install.log
PACKAGE_DIR="${PACKAGE_DIR:-/opt/bbr/packages}"

mapfile -t packages < <(find "$PACKAGE_DIR" -maxdepth 1 -type f -name '*.deb' -print | LC_ALL=C sort)
if [[ ${#packages[@]} -eq 0 ]]; then
  printf '%s install failed: no offline packages\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG"
  exit 1
fi
# Temporäre leere APT-Quellen erzeugen (Cleanup bei Erfolg und Fehler)
empty_sources="$(mktemp)"
empty_source_parts="$(mktemp -d)"
cleanup() {
  rm -f "$empty_sources"
  rm -rf "$empty_source_parts"
}
trap cleanup EXIT

DEBIAN_FRONTEND=noninteractive \
apt-get \
  -o "Dir::Etc::sourcelist=${empty_sources}" \
  -o "Dir::Etc::sourceparts=${empty_source_parts}" \
  -o "APT::Get::List-Cleanup=0" \
  -o "Dir::Cache::Archives=${PACKAGE_DIR}" \
  --no-download \
  --no-remove \
  --no-install-recommends \
  --assume-yes \
  install \
  "${packages[@]}" \
  >>"$LOG" 2>&1

# Post-Install Integritätsgates
dpkg --audit >>"$LOG" 2>&1
if [[ -n "$(dpkg --audit 2>&1)" ]]; then
  printf '%s install failed: dpkg --audit not empty\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG"
  exit 36
fi

apt-get check >>"$LOG" 2>&1 || {
  printf '%s install failed: apt-get check failed\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG"
  exit 36
}

# Explizite Paketprüfung
dpkg-query -W nginx nginx-common php8.2-fpm mariadb-server mariadb-common gawk libmpfr6 >>"$LOG" 2>&1 || {
  printf '%s install failed: package verification failed\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG"
  exit 36
}

# Verzeichnis- und Binary-Prüfung
test -d /etc/nginx/sites-available || {
  printf '%s install failed: /etc/nginx/sites-available missing\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG"
  exit 36
}
test -f /etc/nginx/snippets/fastcgi-php.conf || {
  printf '%s install failed: /etc/nginx/snippets/fastcgi-php.conf missing\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG"
  exit 36
}
command -v php >>"$LOG" 2>&1 || {
  printf '%s install failed: php binary missing\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG"
  exit 36
}
command -v mariadb >>"$LOG" 2>&1 || {
  printf '%s install failed: mariadb binary missing\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG"
  exit 36
}

# Database and WordPress configuration happens only after all packages install.
if [[ ! -d /var/lib/mysql/mysql ]]; then
  mariadb-install-db --user=mysql --datadir=/var/lib/mysql >>"$LOG" 2>&1
fi
systemctl start mariadb

set +x
DB_USER_PASSWORD="$(openssl rand -base64 32)"
DB_ROOT_PASSWORD="$(openssl rand -base64 32)"
WP_USER_PASSWORD="$(openssl rand -base64 32)"
printf '%s\n' "$DB_USER_PASSWORD" > "$SECRETS/db_password"
printf '%s\n' "$DB_ROOT_PASSWORD" > "$SECRETS/mysql_root_password"
printf '%s\n' "$WP_USER_PASSWORD" > "$SECRETS/wp_admin_password"
chmod 0600 "$SECRETS"/*

mariadb --protocol=socket <<SQL
CREATE DATABASE IF NOT EXISTS wordpress;
CREATE USER IF NOT EXISTS 'wp'@'localhost' IDENTIFIED BY '$DB_USER_PASSWORD';
ALTER USER 'wp'@'localhost' IDENTIFIED BY '$DB_USER_PASSWORD';
GRANT ALL ON wordpress.* TO 'wp'@'localhost';
FLUSH PRIVILEGES;
SQL

sed -e "s|__DB_NAME__|wordpress|g" \
    -e "s|__DB_USER__|wp|g" \
    -e "s|__DB_PASSWORD__|$DB_USER_PASSWORD|g" \
    -e "s|__TABLE_PREFIX__|wp_|g" \
    /var/lib/bbr/provisioning/wp-config.php.tmpl > "$DOCROOT/wp-config.php"
chmod 0640 "$DOCROOT/wp-config.php"
chown www-data:www-data "$DOCROOT/wp-config.php"

if ! wp --allow-root --path="$DOCROOT" core is-installed >/dev/null 2>&1; then
  wp --allow-root --quiet --path="$DOCROOT" core install \
    --url="${WP_URL:-http://localhost}" \
    --title="${WP_TITLE:-BugBountyRange WordPress Smoke}" \
    --admin_user="${WP_USER:-admin}" \
    --admin_password="$WP_USER_PASSWORD" \
    --admin_email="${WP_ADMIN_EMAIL:-admin@example.invalid}"
fi
unset DB_USER_PASSWORD DB_ROOT_PASSWORD WP_USER_PASSWORD
printf '%s install complete\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG"
