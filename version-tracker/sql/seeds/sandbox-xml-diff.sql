-- Phase 4 sandbox seed — XML / robots.txt diff source
-- Created: 2026-07-30 by subagent vt-phase-4-xml-wiring
-- Sandbox-only wiring (local loopback, NOT a production target)
-- Reproduce: python3 -m http.server 18103 --bind 127.0.0.1 (serving /opt/data/.hermes/cache/vt-phase4/sandbox-xml/)
--
-- IDs inserted into the live DB during this phase:
--   asset_id = 4
--   target_asset_id = 3
--   version_source_id = 42 (robots_txt)
--   version_source_id = 43 (sitemap_xml)
--
-- INSERT OR IGNORE makes this seed idempotent on re-run.
-- The (vector_type, canonical_identifier) UNIQUE on asset and the
-- (asset_id, source_type, check_method, source_identifier) UNIQUE on
-- version_source are the natural deduplication keys.

-- asset: xml/robots.txt dual feed for the sandbox target
INSERT OR IGNORE INTO asset (vector_type, canonical_identifier, display_name, environment, status,
                             discovery_method, first_seen_at, created_at, updated_at)
VALUES ('website', 'sandbox-xml-diff', 'Sandbox robots+sitemap', 'prod', 'active',
        'manual_xml_diff_discovery', '2026-07-30T21:21:04Z', '2026-07-30T21:21:04Z', '2026-07-30T21:21:04Z');

-- target_asset link: target_id=1 (synthetic 'sandbox' from Phase 2) ↔ asset_id=4
INSERT OR IGNORE INTO target_asset (target_id, asset_id, relationship, first_seen_at, last_seen_at, is_current)
VALUES (
    (SELECT target_id FROM target WHERE canonical_name='sandbox' ORDER BY target_id DESC LIMIT 1),
    (SELECT asset_id FROM asset WHERE canonical_identifier='sandbox-xml-diff' ORDER BY asset_id DESC LIMIT 1),
    'direct', '2026-07-30T21:21:04Z', '2026-07-30T21:21:04Z', 1
);

-- version_source A: robots.txt at the sandbox root
INSERT OR IGNORE INTO version_source (asset_id, source_type, source_url, source_identifier,
                                      check_method, config, enabled, check_interval, on_error_policy)
VALUES (
    (SELECT asset_id FROM asset WHERE canonical_identifier='sandbox-xml-diff' ORDER BY asset_id DESC LIMIT 1),
    'xml_diff', 'http://127.0.0.1:18103/robots.txt', 'robots_txt',
    'xml_diff',
    json_object('feed_url', 'http://127.0.0.1:18103/robots.txt'),
    1, 86400, 'standard'
);

-- version_source B: sitemap.xml at the sandbox root
INSERT OR IGNORE INTO version_source (asset_id, source_type, source_url, source_identifier,
                                      check_method, config, enabled, check_interval, on_error_policy)
VALUES (
    (SELECT asset_id FROM asset WHERE canonical_identifier='sandbox-xml-diff' ORDER BY asset_id DESC LIMIT 1),
    'xml_diff', 'http://127.0.0.1:18103/sitemap.xml', 'sitemap_xml',
    'xml_diff',
    json_object('feed_url', 'http://127.0.0.1:18103/sitemap.xml'),
    1, 86400, 'standard'
);
