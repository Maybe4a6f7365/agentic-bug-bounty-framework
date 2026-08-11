#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# tools/sign_artifact.sh
#
# Minisign-Wrapper für die Operator-Workstation. Betreiber-Verantwortung
# (PHASE-4-PLAN Sektion 14.6). Signiert einen Bootstrap-Tarball und
# legt die .minisig-Datei im selben Verzeichnis ab.
#
# Voraussetzungen:
#   - Minisign installiert (>= 0.9)
#   - Privater Schlüssel an dem vom Operator festgelegten Pfad
#     (PHASE-4-PLAN B1: typischerweise ~/.bbr-keys/minisign.key)
#   - Schlüssel-Modus 0600; Eigentümer root/operator
#
# Exit codes:
#   0  SIGNED
#   1  Aufruf ungültig
#   2  Minisign nicht gefunden
#   3  Schlüssel nicht lesbar / falscher Modus
#   4  Minisign-Signatur fehlgeschlagen
# -----------------------------------------------------------------------------

set -euo pipefail

MINISIGN_KEY=""
ARTIFACT_PATH=""
COMMENT="BBR Phase 4.0 bootstrap artifact"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --key)         MINISIGN_KEY="$2"; shift 2 ;;
    --artifact)    ARTIFACT_PATH="$2"; shift 2 ;;
    --comment)     COMMENT="$2"; shift 2 ;;
    *) echo "sign_artifact: unknown argument $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$MINISIGN_KEY" || -z "$ARTIFACT_PATH" ]]; then
  echo "sign_artifact: --key and --artifact are required" >&2
  exit 1
fi

if ! command -v minisign >/dev/null 2>&1; then
  echo "sign_artifact: FAIL — minisign not installed" >&2
  exit 2
fi

if [[ ! -f "$MINISIGN_KEY" ]]; then
  echo "sign_artifact: FAIL — minisign key not found: $MINISIGN_KEY" >&2
  exit 3
fi

# Schlüssel-Modus MUSS 0600 sein. Stärkerer Modus (0700) ist
# auch OK; restriktiver (0444) ebenfalls. Wir lehnen alles
# lesbar-für-Gruppe/Others ab.
KEY_MODE="$(stat -c%a "$MINISIGN_KEY")"
GROUP_BIT="${KEY_MODE:1:1}"
OTHER_BIT="${KEY_MODE:2:1}"
if [[ "$GROUP_BIT" != "0" || "$OTHER_BIT" != "0" ]]; then
  echo "sign_artifact: FAIL — minisign key has permissive mode: $KEY_MODE" >&2
  echo "  required: 0600 or stricter" >&2
  exit 3
fi

echo "sign_artifact: signing $ARTIFACT_PATH"
minisign -S -s "$MINISIGN_KEY" -m "$ARTIFACT_PATH" -c "$COMMENT" \
  || { echo "sign_artifact: FAIL — minisign signing failed" >&2; exit 4; }

echo "sign_artifact: signed"
exit 0
