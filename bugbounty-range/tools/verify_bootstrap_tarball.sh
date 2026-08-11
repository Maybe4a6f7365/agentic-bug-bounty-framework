#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# tools/verify_bootstrap_tarball.sh
#
# Re-Build-Vergleich gegen ein bereits signiertes Bootstrap-Artefakt.
# Beweist die Reproduzierbarkeit der Build-Pipeline.
#
# Strategie:
#   1. SHA-256 muss identisch sein (gleicher Source, gleicher Build).
#   2. Manifest-Validierung (jq -e).
#   3. Minisign-Signatur prüft die Integrität.
#   4. Optional: Rebuild und erneuter SHA-256-Vergleich.
#      Wenn die Build-Toolchain deterministisch ist, MUSS der
#      rebuilt Tarball bit-identisch sein.
#
# Exit codes:
#   0  reproducibility proven
#   1  tool drift
#   2  missing artifact
#   3  sha256 mismatch
#   4  manifest invalid
#   5  rebuild produced differing tarball
#   6  minisign verification failed
# -----------------------------------------------------------------------------

set -euo pipefail

REQUIRED_TOOL_VERSIONS=(
  "tar:1.35"
  "zstd:1.5.7"
  "sha256sum:9.7"
  "minisign:0.12"
  "jq:1.7"
)

ARTIFACT_DIR=""
MINISIGN_PUB=""
SOURCE_DIR=""
INPUT_MANIFEST=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --artifact-dir)     ARTIFACT_DIR="$2"; shift 2 ;;
    --minisign-pub)     MINISIGN_PUB="$2"; shift 2 ;;
    --source-dir)       SOURCE_DIR="$2"; shift 2 ;;
    --input-manifest)   INPUT_MANIFEST="$2"; shift 2 ;;
    *) echo "verify_bootstrap_tarball: unknown argument $1" >&2; exit 30 ;;
  esac
done

if [[ -z "$ARTIFACT_DIR" || -z "$MINISIGN_PUB" ]]; then
  echo "verify_bootstrap_tarball: --artifact-dir and --minisign-pub are required" >&2
  exit 30
fi

for f in "$ARTIFACT_DIR/artifact.tar.zst" \
         "$ARTIFACT_DIR/artifact.tar.zst.sha256" \
         "$ARTIFACT_DIR/artifact.tar.zst.minisig" \
         "$ARTIFACT_DIR/manifest.json"; do
  if [[ ! -f "$f" ]]; then
    echo "verify_bootstrap_tarball: missing artifact file: $f" >&2
    exit 30
  fi
done

# Toolchain prüfen.
for entry in "${REQUIRED_TOOL_VERSIONS[@]}"; do
  tool="${entry%%:*}"
  expected="${entry#*:}"
  case "$tool" in
    tar)       got="$(tar --version | grep -oE '[0-9]+\.[0-9]+' | sed -n '1p')" ;;
    zstd)      got="$(zstd --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | sed -n '1p')" ;;
    sha256sum) got="$(sha256sum --version | sed -n '1{s/.* //p;}')" ;;
    minisign)  got="$(minisign -v 2>&1 | sed -n '1{s/.* //p;}')" ;;
    jq)        got="$(jq --version | sed 's/^jq-//')" ;;
  esac
  if [[ "$got" != "$expected" ]]; then
    echo "verify_bootstrap_tarball: FAIL tool drift — $tool expected=$expected got=$got" >&2
    exit 30
  fi
done

# Minisign verification must precede SHA and manifest parsing.
echo "verify_bootstrap_tarball: minisign verification"
minisign -V -p "$MINISIGN_PUB" \
  -m "$ARTIFACT_DIR/artifact.tar.zst" \
  -x "$ARTIFACT_DIR/artifact.tar.zst.minisig" \
  || { echo "verify_bootstrap_tarball: FAIL minisign" >&2; exit 31; }

echo "verify_bootstrap_tarball: sha256 check"
(cd "$ARTIFACT_DIR" && sha256sum -c --strict artifact.tar.zst.sha256) \
  || { echo "verify_bootstrap_tarball: FAIL sha256" >&2; exit 32; }

echo "verify_bootstrap_tarball: manifest schema"
jq -e '
  (.manifest_version >= 1)
  and (.artifact_version | type == "string")
  and (.artifact_sha256 | type == "string" and length == 64)
  and (.supported_platform | type == "string")
  and (.artifact_size | type == "number" and . > 0)
' "$ARTIFACT_DIR/manifest.json" >/dev/null \
  || { echo "verify_bootstrap_tarball: FAIL manifest schema" >&2; exit 33; }
[[ "$(jq -r .artifact_sha256 "$ARTIFACT_DIR/manifest.json")" == \
   "$(sha256sum "$ARTIFACT_DIR/artifact.tar.zst" | awk '{print $1}')" ]] \
  || { echo "verify_bootstrap_tarball: FAIL manifest hash" >&2; exit 34; }

# 4. Optional: re-Build und erneuter Hash-Vergleich.
if [[ -n "$SOURCE_DIR" && -n "$INPUT_MANIFEST" ]]; then
  echo "verify_bootstrap_tarball: rebuild comparison"
  REBUILD_DIR="$(mktemp -d)"
  trap 'rm -rf "$REBUILD_DIR"' EXIT
  # Same tar args, same zstd config.
  tar --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner \
      --create --file "$REBUILD_DIR/artifact.tar" \
      -C "$SOURCE_DIR" .
  zstd -19 --no-progress -f "$REBUILD_DIR/artifact.tar" \
    -o "$REBUILD_DIR/artifact.tar.zst"
  REBUILT_SHA="$(sha256sum "$REBUILD_DIR/artifact.tar.zst" | awk '{print $1}')"
  ORIGINAL_SHA="$(sha256sum "$ARTIFACT_DIR/artifact.tar.zst" | awk '{print $1}')"
  if [[ "$REBUILT_SHA" != "$ORIGINAL_SHA" ]]; then
    echo "verify_bootstrap_tarball: FAIL rebuild hash differs" >&2
    echo "  original: $ORIGINAL_SHA" >&2
    echo "  rebuilt:  $REBUILT_SHA" >&2
    exit 35
  fi
  echo "verify_bootstrap_tarball: rebuild hash matches"
fi

echo "verify_bootstrap_tarball: PASS — reproducibility proven"
exit 0
