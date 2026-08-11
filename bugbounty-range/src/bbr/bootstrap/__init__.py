"""bbr.bootstrap — Phase 4.0 bootstrap verification utilities.

Sub-modules:
  - verifier     Minisign / SHA-256 / manifest validation
  - secrets      Runtime secret generation
  - downloader   GCS artifact pull (synthetic in tests)

Exit codes 30-39 (Phase 4.0, ADR-0010):
  30  GCS pull failed
  31  signature invalid or missing
  32  sha256 mismatch
  33  manifest schema invalid
  34  manifest hash inconsistency
  35  extract failed
  36  install failed
  37  config failed
  38  start failed
  39  healthcheck failed
"""
