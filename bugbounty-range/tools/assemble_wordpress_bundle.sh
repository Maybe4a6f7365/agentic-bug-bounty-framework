#!/usr/bin/env bash
# Assemble the complete offline WordPress runtime tree from the operator cache.

set -euo pipefail

CACHE_DIR="${BBR_BUILD_CACHE:-/home/admin/.bbr-build/cache}"
OUTPUT_DIR=""
PACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../packs/wordpress-smoke" && pwd)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cache-dir) CACHE_DIR="$2"; shift 2 ;;
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    *) echo "assemble_wordpress_bundle: unknown argument $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$OUTPUT_DIR" ]]; then
  echo "assemble_wordpress_bundle: --output-dir is required" >&2
  exit 1
fi

WORDPRESS_ARCHIVE="$CACHE_DIR/wordpress-6.8.2.tar.gz"
MINISIGN_ARCHIVE="$CACHE_DIR/minisign-0.12-linux.tar.gz"
WP_CLI_PHAR="$CACHE_DIR/wp-cli-2.12.0.phar"
EXPECTED_WORDPRESS_SHA="d85a72e392bfe866816b3c2ebc6a44699072aa50cc3a620f1c4ed2f13b645e2b"

for input in "$WORDPRESS_ARCHIVE" "$MINISIGN_ARCHIVE" "$WP_CLI_PHAR"; do
  [[ -f "$input" ]] || { echo "assemble_wordpress_bundle: missing $input" >&2; exit 2; }
done
printf '%s  %s\n' "$EXPECTED_WORDPRESS_SHA" "$WORDPRESS_ARCHIVE" | sha256sum -c -

mapfile -t debs < <(find "$CACHE_DIR" -maxdepth 1 -type f -name '*.deb' -print | LC_ALL=C sort)
if [[ ${#debs[@]} -eq 0 ]]; then
  echo "assemble_wordpress_bundle: no cached Debian packages in $CACHE_DIR" >&2
  exit 2
fi

rm -rf "$OUTPUT_DIR"
mkdir -p \
  "$OUTPUT_DIR/bin" \
  "$OUTPUT_DIR/packages" \
  "$OUTPUT_DIR/runtime/nginx/sbin" \
  "$OUTPUT_DIR/runtime/php/sbin" \
  "$OUTPUT_DIR/runtime/mariadb/usr" \
  "$OUTPUT_DIR/runtime/www" \
  "$OUTPUT_DIR/provisioning" \
  "$OUTPUT_DIR/secrets"

for deb in "${debs[@]}"; do
  install -m 0644 "$deb" "$OUTPUT_DIR/packages/$(basename "$deb")"
done

tar -xzf "$WORDPRESS_ARCHIVE" --strip-components=1 -C "$OUTPUT_DIR/runtime/www"
tar -xzf "$MINISIGN_ARCHIVE" \
  --strip-components=2 \
  -C "$OUTPUT_DIR/bin" \
  minisign-linux/x86_64/minisign
install -m 0755 "$WP_CLI_PHAR" "$OUTPUT_DIR/bin/wp"
cp "$PACK_DIR"/provisioning/* "$OUTPUT_DIR/provisioning/"
chmod 0755 "$OUTPUT_DIR"/provisioning/*.sh "$OUTPUT_DIR/bin/minisign" "$OUTPUT_DIR/bin/wp"
chmod 0700 "$OUTPUT_DIR/secrets"

jq -n \
  --arg wordpress_sha256 "$(sha256sum "$WORDPRESS_ARCHIVE" | awk '{print $1}')" \
  --arg minisign_sha256 "$(sha256sum "$MINISIGN_ARCHIVE" | awk '{print $1}')" \
  --arg wp_cli_sha256 "$(sha256sum "$WP_CLI_PHAR" | awk '{print $1}')" \
  --argjson debian_package_count "${#debs[@]}" \
  '{
    bundle_format: 1,
    wordpress_sha256: $wordpress_sha256,
    minisign_sha256: $minisign_sha256,
    wp_cli_sha256: $wp_cli_sha256,
    debian_package_count: $debian_package_count
  }' > "$OUTPUT_DIR/manifest.json"

{
  printf '{\n  "format": 1,\n  "packages": [\n'
  for index in "${!debs[@]}"; do
    deb="${debs[$index]}"
    comma=","
    [[ "$index" -eq $((${#debs[@]} - 1)) ]] && comma=""
    printf '    {"file":"%s","sha256":"%s"}%s\n' \
      "$(basename "$deb")" "$(sha256sum "$deb" | awk '{print $1}')" "$comma"
  done
  printf '  ]\n}\n'
} > "$OUTPUT_DIR/package-inputs.json"

echo "assemble_wordpress_bundle: assembled ${#debs[@]} Debian packages at $OUTPUT_DIR"
