# Build Environment — WordPress-Smoke Bootstrap Artefakt

**Phase 4.0 — Reproduzierbarkeit (PHASE-4-PLAN Sektion 11.7)**

Dieses Dokument beschreibt die Build-Umgebung, mit der das
Bootstrap-Artefakt (`artifact.tar.zst` + `.sha256` + `.minisig` +
`manifest.json`) **offline** auf der Operator-Workstation erzeugt
wird. Drift in einer der hier dokumentierten Komponenten
kann zu SHA-256-Drift im Tarball und damit zu Bootstrap-Fail
führen.

## Toolchain-Versionen (Hermes Phase 4A)

Die folgenden Versionen sind die einzigen, mit denen das
Artefakt gebaut werden darf. Jede Drift ist **explizit** in
einem ADR-Addendum oder in PHASE-4-PLAN Sektion 14 zu
begründen.

| Tool       | Version | Verwendung |
|------------|---------|------------|
| `tar`      | 1.35    | Deterministische Tar-Erzeugung (--sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner) |
| `zstd`     | 1.5.7   | Reproduzierbare Tarball-Kompression (`-19 --no-progress`) |
| `sha256sum`| 9.7     | Hash-Berechnung, Verifikation |
| `minisign` | 0.12    | Ed25519-Signatur (statischer Binary, kleiner TCB) |
| `jq`       | 1.7     | Manifest-Schema-Validierung |
| `gsutil`   | 5.37    | GCS-Upload |
| `openssl`  | 3.5.6   | Secret-Erzeugung (`openssl rand -base64 32`) |
| `wp-cli`   | 2.12.0  | `wp config shuffle-salts`, `wp core is-installed` |

Diese Versionen stehen als Referenz in
`tools/build_bootstrap_tarball.sh`. `--strict-versions` macht Drift
zu Exit 1. Ohne Strict-Modus ist Toolchain-Drift zulässig, sofern Hash
und Signatur verifizieren. Echte Byte-für-Byte-Reproduzierbarkeit
erfordert diese exakten Versionen; künftig kann dafür zusätzlich ein
fest versionierter Build-Container verwendet werden.

## Build-Argumentliste (deterministische Tar-Args)

```bash
tar --sort=name \
    --mtime=@0 \
    --owner=0 --group=0 --numeric-owner \
    --create \
    --file artifact.tar \
    -C <source_dir> .
```

| Argument | Wirkung |
|---|---|
| `--sort=name` | Sortiert Tar-Einträge vor Schreiben. Reproduzierbarkeit. |
| `--mtime=@0` | MTime auf Unix-Epoche 0. Reproduzierbarkeit. |
| `--owner=0 --group=0 --numeric-owner` | Numerische Owner=0. Reproduzierbarkeit. |

## Kompression

```bash
zstd -19 --no-progress -f artifact.tar -o artifact.tar.zst
```

| Argument | Wirkung |
|---|---|
| `-19` | Maximale Kompressions-Stufe (deterministisch). |
| `--no-progress` | Kein Status-Output. Reproduzierbarkeit. |
| `-f` | Overwrite ohne Rückfrage. |

## Variierende Felder

Von allen Manifest-Feldern ist **ausschließlich**
`manifest.json:build_timestamp` zeitabhängig. Der Tarball
selbst MUSS bit-identisch sein (gleiches Source → gleicher
SHA-256).

## Build-Architektur

```
Operator-Workstation (kein Netzwerk-Zwang)
  ↓
tools/build_bootstrap_tarball.sh:
  1. Toolchain-Versions-Check
  2. Source-Verzeichnis vorhanden
  3. Input-Manifest SHA-256-Check
  4. tar --sort=name --mtime=@0 ...
  5. zstd -19
  6. sha256sum → artifact.tar.zst.sha256
  7. minisign -S -s <key> -m artifact.tar.zst
  8. manifest.json (13 Felder)
  9. NICHT: gsutil cp (Phase 4.0 EXECUTE-Gate)
```

## Verifikation

```bash
tools/verify_bootstrap_tarball.sh \
  --artifact-dir <out_dir> \
  --minisign-pub <pub> \
  --source-dir <source> \
  --input-manifest <input-manifest>
```

Verifikation prüft:

1. SHA-256 gegen sidecar
2. Manifest-Schema (json-shape)
3. Minisign-Signatur
4. Optional: Rebuild → bit-identischer Hash

## Reproduzierbarkeits-Invariante

> Gleicher Source-Tree + gleiche Build-Args + gleiche
> Toolchain-Version = gleicher Tarball-SHA-256.

Abweichungen sind **immer** durch Toolchain-Drift oder
`build_timestamp` erklärbar und müssen in
`notes/PHASE-4-PLAN.md` Sektion 14 dokumentiert werden.

## Build-Inputs (sha256-verifiziert)

Vor dem eigentlichen Build prüft `build_bootstrap_tarball.sh`:

```bash
jq -r '.inputs[] | "\(.sha256)  \(.path)"' input-manifest.json \
  | (cd source_dir && sha256sum -c --strict -)
```

Diese Liste wird vom Operator vor jedem Build erstellt und
enthält alle Eingabedateien (WordPress-Core, Plugins, Themes,
Composer-Abhängigkeiten, wp-cli.phar).

## Betriebssystem-Voraussetzungen

Phase 4.0 empfiehlt (ohne Verpflichtung):

- Debian 12 (bookworm) oder
- Ubuntu 22.04 LTS oder
- Fedora 38+

Build-Tests sind auf Debian 12 (bookworm) ausgeführt.

## Custom Image

Phase 4A verwendet das feste Image
`projects/your-lab-name-your-researcher-handle/global/images/bbr-debian-12-with-minisign-20260727`.
Es basiert auf
`projects/debian-cloud/global/images/debian-12-bookworm-v20260721` und
enthält `/usr/local/bin/minisign` Version 0.12. Das löst den
Trust-Bootstrap: die Signatur wird geprüft, bevor Inhalt aus dem
Release-Artefakt ausgeführt wird.

Bake-Prozedur:

1. `minisign-0.12-linux.tar.gz` wird mit SHA-256
   `9a599b48ba6eb7b1e80f12f36b94ceca7c00b7a5173c95c3efc88d9822957e73`
   in den privaten Bootstrap-Bucket geladen.
2. Eine temporäre VM aus dem festen Debian-Image lädt das Archiv mit
   Metadata-Server-Token, prüft den Hash, installiert den Binary und
   führt `minisign -v` aus.
3. Die VM wird gestoppt; aus ihrer Boot-Disk wird das UEFI-kompatible
   Image erzeugt.
4. Nach `READY` wird die temporäre VM gelöscht. Der Self-Link wird im
   Pack-Manifest und Terraform-Plan eingefroren.

Der produktive Private Key liegt ausschließlich unter
`~/.bbr-keys/minisign.key` (0600). Der Demo-Pfad nutzt bewusst `-W`
ohne Passphrase; produktiver Regelbetrieb verlangt einen
passphrase-geschützten Schlüssel und ein verschlüsseltes Offline-Backup.
