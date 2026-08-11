-- Phase 5 engagement envelope for synthetic sandbox target (target_id=1).
-- Idempotent by the exact entity/note tuple.
INSERT OR IGNORE INTO research_note (entity_type, entity_id, note)
VALUES (
  'target',
  1,
  'Engagement envelope — sandbox target (target_id=1):
- Phase 2 mechanism #1 (JS bundle integrity): wired via version_source_id=40, source_type=''js_bundle'', check_method=''script_src_diff'', sandbox http://127.0.0.1:18101/ — TORN DOWN post-validation
- Phase 3 mechanism #2 (security headers): wired via version_source_id=41, source_type=''api'', check_method=''header_diff'', sandbox http://127.0.0.1:18102/ — TORN DOWN post-validation
- Phase 4 mechanism #3 (robots/sitemap): wired via version_source_id=42+43, source_type=''xml_diff'', check_method=''xml_diff'', sandbox http://127.0.0.1:18103/ — TORN DOWN post-validation
- All fetches to loopback (127.0.0.1:1810x); zero external/production targets touched
- OSINT boundary: no enumeration, no probing, no payload submission. Verified per OSINT-CODEREVIEW-1/2/3 negative tests in tests/.
- DB path caveat (Phase 0 path-map bug, fixed in Phase 4 handoff §9): every runner invocation must export VERSION_TRACKER_DB=/opt/data/.hermes/version-tracker/version_tracker.db explicitly.'
);
