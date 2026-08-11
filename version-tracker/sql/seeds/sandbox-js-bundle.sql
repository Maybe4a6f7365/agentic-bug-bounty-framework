-- Phase 2 sandbox seed — JS bundle integrity source
-- Created: 2026-07-30 by subagent vt-phase-7-handoff-and-pr (Phase 7 handoff).
-- Phase 2 itself did not commit a seed file — this seed is generated now from the
-- live DB state so future operators can reproduce the JS-bundle wiring from SQL alone.
--
-- Sandbox-only wiring (local loopback, NOT a production target).
-- Reproduce: python3 -m http.server 18101 --bind 127.0.0.1
--            (serving /opt/data/.hermes/cache/vt-phase2/sandbox-js-bundle/)
--
-- IDs inserted into the live DB during Phase 2:
--   target_id = 1          (canonical_name='sandbox' — synthetic target)
--   asset_id  = 2          (vector_type='website', canonical_identifier='sandbox-js-bundle')
--   target_asset_id = 1    (target_id=1 ↔ asset_id=2, is_current=1)
--   version_source_id = 40 (asset_id=2, source_type='js_bundle', check_method='script_src_diff')
--
-- INSERT OR IGNORE makes this seed idempotent on re-run.
-- The (vector_type, canonical_identifier) UNIQUE on asset and the
-- (asset_id, source_type, check_method, source_identifier) UNIQUE on
-- version_source are the natural deduplication keys.

-- target: synthetic 'sandbox' (the precondition Phase 2 created because the live
-- DB originally had 0 real target rows; any later importer may insert real targets
-- around target_id=1, but the synthetic row remains at id=1).
INSERT OR IGNORE INTO target (canonical_name, company_name, description, main_site_url,
                              target_status, created_at, updated_at)
VALUES ('sandbox', 'Sandbox',
        'Synthetic target for Phase 2 JS bundle wiring (local-loopback only)',
        'http://127.0.0.1:18101/', 'active',
        '2026-07-30 15:49:44', '2026-07-30 15:49:44');

-- asset: JS-bundle sandbox set
INSERT OR IGNORE INTO asset (vector_type, canonical_identifier, display_name, environment, status,
                             discovery_method, first_seen_at, created_at, updated_at)
VALUES ('website', 'sandbox-js-bundle', 'Sandbox JS bundle set', 'prod', 'active',
        'manual_js_bundle_discovery',
        '2026-07-30 15:49:44', '2026-07-30 15:49:44', '2026-07-30 15:49:44');

-- target_asset link: target_id=(sandbox) ↔ asset_id=(sandbox-js-bundle)
INSERT OR IGNORE INTO target_asset (target_id, asset_id, relationship, first_seen_at, last_seen_at, is_current)
VALUES (
    (SELECT target_id FROM target WHERE canonical_name='sandbox' ORDER BY target_id DESC LIMIT 1),
    (SELECT asset_id FROM asset WHERE canonical_identifier='sandbox-js-bundle' ORDER BY asset_id DESC LIMIT 1),
    'direct', '2026-07-30 15:49:44', '2026-07-30 15:49:44', 1
);

-- version_source: js_bundle / script_src_diff against the loopback homepage
INSERT OR IGNORE INTO version_source (asset_id, source_type, source_url, source_identifier,
                                      check_method, config, enabled, check_interval, on_error_policy)
VALUES (
    (SELECT asset_id FROM asset WHERE canonical_identifier='sandbox-js-bundle' ORDER BY asset_id DESC LIMIT 1),
    'js_bundle', 'http://127.0.0.1:18101/', 'homepage_script_set',
    'script_src_diff',
    json_object('page_url', 'http://127.0.0.1:18101/',
                'script_filter', null,
                'user_agent', 'research_headers'),
    1, 86400, 'standard'
);
