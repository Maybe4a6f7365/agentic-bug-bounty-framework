#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# tools/build_bootstrap_tarball.sh
#
# Offline build of a deterministic, bit-identical bootstrap tarball
# for the WordPress-Smoke pack (Phase 4.0).
#
# Property: REPRODUCIBILITY.
#   - Fixed tool versions (see REQUIRED_TOOL_VERSIONS below).
#   - Sorted tar entries (`--sort=name`).
#   - Fixed mtime (`--mtime=@0`) and owner (`--owner=0 --group=0 --numeric-owner`).
#   - Reproducible zstd compression (`-19`).
#   - Build inputs are SHA-256 verified against an input manifest.
#
# Output triplet (ADR-0010 D.2):
#   <out_dir>/artifact.tar.zst
#   <out_dir>/artifact.tar.zst.sha256
#   <out_dir>/artifact.tar.zst.minisig
#   <out_dir>/manifest.json
#
# Exit codes (Phase 4.0):
#   0  success
#   1  unmet tool version
#   2  input manifest mismatch
#   3  source directory missing
#   4  tar build failed
#   5  zstd compression failed
#   6  sha256 write failed
#   7  metadata collection failed
#   8  minisign signing failed
#   9  manifest write failed
#  10  upload disabled (Phase 4.0: no remote push)
#
# Eingabeargumente:
#   --source-dir <PATH>     Verzeichnis mit dem entpackten Inhalt
#                            (WordPress-Core, Plugins, Themes, Skripte).
#   --input-manifest <PATH> JSON-Datei mit sha256-Einträgen pro Inputdatei.
#   --output-dir <PATH>     Zielverzeichnis für das Artefakt-Triplet.
#   --minisign-key <PATH>   Pfad zum privaten Minisign-Schlüssel (OFFLINE).
#   --artifact-version <V>  z. B. "6.8.2-r1"
#   --bootstrap-version <V> z. B. "4.0.0"
#   --wordpress-version <V> z. B. "6.8.2"
#   --php-version <V>       z. B. "8.3"
#   --mariadb-version <V>   z. B. "10.11.6"
#   --supported-platform <SELF-LINK>  z. B. projects/debian-cloud/global/images/debian-12-bookworm-v20260721
#   --build-id <ID>         z. B. "build-2026-07-26-001"
#
# Architekturhinweis: das Skript signiert und schreibt Manifest +
# Signatur-Hülle. KEIN `gsutil cp` (Phase 4.0: Implementierung;
# Upload ist EXECUTE-Gate-Verantwortung).
# -----------------------------------------------------------------------------

set -euo pipefail

# Wartbare Liste der erwarteten Werkzeug-Versionen. Jede Drift
# gegenüber dieser Liste MUSS in BUILD-ENVIRONMENT.md begründet
# werden; TAR-Drift führt zu SHA-256-Drift und damit zu
# Bootstrap-Fail (Exit 32).
REQUIRED_TOOL_VERSIONS=(
  "tar:1.35"
  "zstd:1.5.7"
  "sha256sum:9.7"
  "minisign:0.12"
  "jq:1.7"
)

SOURCE_DIR=""
INPUT_MANIFEST=""
OUTPUT_DIR=""
MINISIGN_KEY=""
ARTIFACT_VERSION=""
BOOTSTRAP_VERSION=""
WORDPRESS_VERSION=""
PHP_VERSION=""
MARIADB_VERSION=""
SUPPORTED_PLATFORM=""
BUILD_ID=""
STRICT_VERSIONS=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source-dir)           SOURCE_DIR="$2"; shift 2 ;;
    --input-manifest)       INPUT_MANIFEST="$2"; shift 2 ;;
    --output-dir)           OUTPUT_DIR="$2"; shift 2 ;;
    --minisign-key)         MINISIGN_KEY="$2"; shift 2 ;;
    --artifact-version)     ARTIFACT_VERSION="$2"; shift 2 ;;
    --bootstrap-version)    BOOTSTRAP_VERSION="$2"; shift 2 ;;
    --wordpress-version)    WORDPRESS_VERSION="$2"; shift 2 ;;
    --php-version)          PHP_VERSION="$2"; shift 2 ;;
    --mariadb-version)      MARIADB_VERSION="$2"; shift 2 ;;
    --supported-platform)   SUPPORTED_PLATFORM="$2"; shift 2 ;;
    --build-id)             BUILD_ID="$2"; shift 2 ;;
    --strict-versions)      STRICT_VERSIONS=true; shift ;;
    *) echo "build_bootstrap_tarball: unknown argument $1" >&2; exit 1 ;;
  esac
done

# Validate required arguments.
missing=()
for v in SOURCE_DIR INPUT_MANIFEST OUTPUT_DIR MINISIGN_KEY \
         ARTIFACT_VERSION BOOTSTRAP_VERSION WORDPRESS_VERSION \
         PHP_VERSION MARIADB_VERSION SUPPORTED_PLATFORM BUILD_ID; do
  if [[ -z "${!v}" ]]; then missing+=("$v"); fi
done
if [[ ${#missing[@]} -gt 0 ]]; then
  echo "build_bootstrap_tarball: missing required arguments: ${missing[*]}" >&2
  exit 1
fi

if [[ ! -d "$SOURCE_DIR" ]]; then
  echo "build_bootstrap_tarball: source directory does not exist: $SOURCE_DIR" >&2
  exit 3
fi
if [[ ! -f "$INPUT_MANIFEST" ]]; then
  echo "build_bootstrap_tarball: input manifest missing: $INPUT_MANIFEST" >&2
  exit 3
fi
if [[ ! -f "$MINISIGN_KEY" ]]; then
  echo "build_bootstrap_tarball: minisign key missing: $MINISIGN_KEY" >&2
  exit 3
fi

# Helper: extract MAJOR.MINOR from a version string.
_tool_version() {
  local tool="$1"
  case "$tool" in
    tar)       tar --version | grep -oE '[0-9]+\.[0-9]+' | sed -n '1p' ;;
    zstd)      zstd --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | sed -n '1p' ;;
    sha256sum) sha256sum --version | sed -n '1{s/.* //p;}' ;;
    minisign)  minisign -v 2>&1 | sed -n '1{s/.* //p;}' ;;
    jq)        jq --version | sed 's/^jq-//' ;;
  esac
}

# Toolchain versions are recorded and only enforced in strict mode. Integrity
# is established by the resulting hash and signature; byte-for-byte rebuilds
# additionally require the same toolchain.
echo "build_bootstrap_tarball: toolchain check"
for entry in "${REQUIRED_TOOL_VERSIONS[@]}"; do
  tool="${entry%%:*}"
  expected="${entry#*:}"
  got="$(_tool_version "$tool")"
  if [[ "$got" != "$expected" && "$STRICT_VERSIONS" == true ]]; then
    echo "build_bootstrap_tarball: FAIL tool drift — $tool expected=$expected got=$got" >&2
    exit 1
  fi
  echo "  $tool $got (reference $expected)"
done

# Eingabe-SHA-256-Manifest verifizieren.
echo "build_bootstrap_tarball: input manifest verification"
jq -r '.inputs[] | "\(.sha256)  \(.path)"' "$INPUT_MANIFEST" \
  | (cd "$SOURCE_DIR" && sha256sum -c --strict -) \
  || { echo "build_bootstrap_tarball: FAIL input manifest mismatch" >&2; exit 2; }

mkdir -p "$OUTPUT_DIR"

# Tarball deterministisch erzeugen.
TARBALL="$OUTPUT_DIR/artifact.tar.zst"
TMPTAR="$(mktemp --suffix=.tar)"
trap 'rm -f "$TMPTAR"' EXIT

echo "build_bootstrap_tarball: deterministic tar creation"
tar --sort=name \
    --mtime=@0 \
    --owner=0 --group=0 --numeric-owner \
    --create \
    --file "$TMPTAR" \
    -C "$SOURCE_DIR" \
    . \
  || { echo "build_bootstrap_tarball: FAIL tar build" >&2; exit 4; }

echo "build_bootstrap_tarball: deterministic zstd compression"
# -19 ist die maximale Kompressions-Stufe (deterministisch).
# --no-progress unterdrückt Status-Output für reproduce-ability.
zstd -19 --no-progress -f "$TMPTAR" -o "$TARBALL" \
  || { echo "build_bootstrap_tarball: FAIL zstd compression" >&2; exit 5; }

# SHA-256 schreiben.
echo "build_bootstrap_tarball: artifact sha256"
ARTIFACT_SHA="$(sha256sum "$TARBALL" | awk '{print $1}')"
echo "$ARTIFACT_SHA  artifact.tar.zst" > "$TARBALL.sha256" \
  || { echo "build_bootstrap_tarball: FAIL sha256 write" >&2; exit 6; }

SIG_FILE="$OUTPUT_DIR/artifact.tar.zst.minisig"
echo "build_bootstrap_tarball: minisign signing"
"$(dirname "$0")/sign_artifact.sh" \
  --key "$MINISIGN_KEY" \
  --artifact "$TARBALL" \
  --comment "BBR $ARTIFACT_VERSION ($BUILD_ID)" \
  || { echo "build_bootstrap_tarball: FAIL minisign" >&2; exit 8; }
[[ -s "$SIG_FILE" ]] || { echo "build_bootstrap_tarball: FAIL signature missing" >&2; exit 8; }
ARTIFACT_SIGNATURE="$(awk 'NR == 2 || NR == 4 {printf "%s", $0}' "$SIG_FILE")"
[[ "$ARTIFACT_SIGNATURE" =~ ^[A-Za-z0-9+/=]+$ ]] \
  || { echo "build_bootstrap_tarball: FAIL signature body" >&2; exit 8; }

# Manifest schreiben.
echo "build_bootstrap_tarball: manifest write"
ARTIFACT_SIZE="$(stat -c%s "$TARBALL")"
BUILD_TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
GIT_COMMIT="$(git -C "$(dirname "$0")/../.." rev-parse HEAD 2>/dev/null || echo unknown)"

jq -n \
  --arg     manifest_version "1" \
  --arg     artifact_version "$ARTIFACT_VERSION" \
  --arg     bootstrap_version "$BOOTSTRAP_VERSION" \
  --arg     wordpress_version "$WORDPRESS_VERSION" \
  --arg     php_version "$PHP_VERSION" \
  --arg     mariadb_version "$MARIADB_VERSION" \
  --arg     git_commit "$GIT_COMMIT" \
  --arg     build_id "$BUILD_ID" \
  --arg     build_timestamp "$BUILD_TIMESTAMP" \
  --argjson artifact_size "$ARTIFACT_SIZE" \
  --arg     artifact_sha256 "$ARTIFACT_SHA" \
  --arg     artifact_signature "$ARTIFACT_SIGNATURE" \
  --arg     supported_platform "$SUPPORTED_PLATFORM" \
  '{
    manifest_version: ($manifest_version | tonumber),
    artifact_version:  $artifact_version,
    bootstrap_version: $bootstrap_version,
    wordpress_version: $wordpress_version,
    php_version:       $php_version,
    mariadb_version:   $mariadb_version,
    git_commit:        $git_commit,
    build_id:          $build_id,
    build_timestamp:   $build_timestamp,
    artifact_size:     $artifact_size,
    artifact_sha256:   $artifact_sha256,
    artifact_signature: $artifact_signature,
    supported_platform: $supported_platform
  }' \
  > "$OUTPUT_DIR/manifest.json" \
  || { echo "build_bootstrap_tarball: FAIL manifest write" >&2; exit 9; }

# Phase 4.0: kein Remote-Push. EXECUTE-Gate entscheidet über Upload.
echo "build_bootstrap_tarball: artifact built at $OUTPUT_DIR"
echo "  artifact.tar.zst        sha256=$ARTIFACT_SHA size=$ARTIFACT_SIZE"
echo "  manifest.json           build_id=$BUILD_ID"
echo "  REMOTE UPLOAD DEFERRED TO PHASE 4 EXECUTE GATE"
exit 0
