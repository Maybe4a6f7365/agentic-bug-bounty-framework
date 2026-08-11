#!/usr/bin/env bash
# Install the already verified and extracted offline runtime bundle.

set -euo pipefail
unset PS4

BBR_ROOT="${BBR_ROOT:-/opt/bbr}"
LOG=/var/log/bbr/bootstrap.log

log() {
  printf '%s bootstrap %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$LOG"
}

mkdir -p /var/log/bbr /var/lib/bbr/secrets /var/lib/bbr/provisioning
chmod 0700 /var/lib/bbr/secrets

install -m 0755 "$BBR_ROOT/bin/wp" /usr/local/bin/wp
install -m 0755 "$BBR_ROOT/bin/minisign" /usr/local/bin/minisign
cp -a "$BBR_ROOT/provisioning/." /var/lib/bbr/provisioning/
rm -rf /var/www/html
mkdir -p /var/www/html
cp -a "$BBR_ROOT/runtime/www/." /var/www/html/

getent group mysql >/dev/null || groupadd --system mysql
id mysql >/dev/null 2>&1 || useradd --system --gid mysql --home-dir /nonexistent --shell /usr/sbin/nologin mysql
getent group www-data >/dev/null || groupadd --system www-data
id www-data >/dev/null 2>&1 || useradd --system --gid www-data --home-dir /var/www --shell /usr/sbin/nologin www-data

mkdir -p /run/mysqld /run/php /var/lib/mysql
chown -R mysql:mysql /run/mysqld /var/lib/mysql
chown -R www-data:www-data /var/www/html

/var/lib/bbr/provisioning/install-wordpress.sh || exit 36
test -d /etc/nginx/sites-available || exit 36
test -f /etc/nginx/snippets/fastcgi-php.conf || exit 36

cat > /etc/nginx/sites-available/default <<'EOF'
server {
  listen 80 default_server;
  root /var/www/html;
  index index.php index.html;
  location / { try_files $uri $uri/ /index.php?$args; }
  location ~ \.php$ {
    include snippets/fastcgi-php.conf;
    fastcgi_pass unix:/run/php/php8.2-fpm.sock;
  }
}
EOF

systemctl daemon-reload
/var/lib/bbr/provisioning/configure.sh || exit 37
systemctl restart mariadb php8.2-fpm nginx || exit 38
/var/lib/bbr/provisioning/healthcheck.sh || exit 39
log "COMPLETED"
