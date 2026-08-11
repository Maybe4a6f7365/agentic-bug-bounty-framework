-- version-tracker schema v1 (SQLite)
-- sqlite3 version_tracker.db < sql/schema.sql
-- Every connection: PRAGMA foreign_keys = ON; PRAGMA journal_mode=WAL;

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ── Platforms and Programs ──────────────────────────────────────

CREATE TABLE bug_bounty_platform (
    platform_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT NOT NULL,
    slug              TEXT NOT NULL UNIQUE,
    base_url          TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE bug_bounty_program (
    program_id                INTEGER PRIMARY KEY AUTOINCREMENT,
    platform_id               INTEGER NOT NULL REFERENCES bug_bounty_platform(platform_id),
    external_handle           TEXT NOT NULL,
    name                      TEXT NOT NULL,
    program_url               TEXT,
    program_status            TEXT NOT NULL DEFAULT 'open'
                              CHECK (program_status IN ('open','closed','paused','vdp_only')),
    managed_program           INTEGER,
    offers_bounties           INTEGER,
    policy_url                TEXT,
    first_seen_at             TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at              TEXT NOT NULL DEFAULT (datetime('now')),
    raw_metadata              TEXT,                             -- JSON stored as TEXT
    created_at                TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at                TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(platform_id, external_handle)
);

-- Migration-003 parity: canonical fresh databases include the same policy store.
-- Keep this DDL in lockstep with sql/migrations/003_program_policy.sql.
CREATE TABLE IF NOT EXISTS program_policy (
    policy_id INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id INTEGER NOT NULL REFERENCES bug_bounty_program(program_id),
    policy_url TEXT NOT NULL,
    raw_text TEXT,
    scraped_at TEXT NOT NULL,
    content_hash TEXT NOT NULL,

    -- Parsed sections (structured from raw_text)
    scope_description TEXT,           -- "Scope" section describing what's covered
    out_of_scope_vulns TEXT,          -- JSON array of excluded vulnerability classes
    program_rules TEXT,               -- Do / Do NOT rules
    safe_harbor TEXT,                 -- Safe harbor language
    disclosure_policy TEXT,           -- Disclosure terms
    testing_restrictions TEXT,        -- Rate limits, auth requirements, etc.
    rewards_info TEXT,                -- Bounty ranges, swag, etc.

    -- Metadata
    is_current INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    UNIQUE(program_id, content_hash)
);

CREATE INDEX IF NOT EXISTS idx_program_policy_program ON program_policy(program_id, is_current);

-- ── Targets and Assets (decoupled per council review) ───────────

CREATE TABLE target (
    target_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name    TEXT NOT NULL,
    company_name      TEXT,
    description       TEXT,
    main_site_url     TEXT,
    target_status     TEXT NOT NULL DEFAULT 'active'
                      CHECK (target_status IN ('active','deprecated','unknown')),
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE asset (
    asset_id                INTEGER PRIMARY KEY AUTOINCREMENT,
    vector_type             TEXT NOT NULL
                            CHECK (vector_type IN (
                                'website','api','github_repository','android_app',
                                'ios_app','package','docker_image','other'
                            )),
    canonical_identifier    TEXT NOT NULL,
    display_name            TEXT,
    description             TEXT,
    environment             TEXT CHECK (environment IN ('prod','staging','dev','unknown')),
    status                  TEXT NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active','deprecated','removed')),
    discovery_method        TEXT,
    discovery_source_url    TEXT,
    metadata                TEXT,                             -- JSON as TEXT
    first_seen_at           TEXT NOT NULL DEFAULT (datetime('now')),
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at              TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(vector_type, canonical_identifier)
);

CREATE TABLE target_asset (
    target_asset_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id         INTEGER NOT NULL REFERENCES target(target_id),
    asset_id          INTEGER NOT NULL REFERENCES asset(asset_id),
    relationship      TEXT NOT NULL DEFAULT 'direct'
                      CHECK (relationship IN ('direct','inferred','shared_company','third_party_asset')),
    first_seen_at     TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at      TEXT NOT NULL DEFAULT (datetime('now')),
    is_current        INTEGER NOT NULL DEFAULT 1,
    UNIQUE(target_id, asset_id)
);

-- ── Scope Tracking ──────────────────────────────────────────────

CREATE TABLE scope_record (
    scope_id                INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id              INTEGER NOT NULL REFERENCES bug_bounty_program(program_id),
    asset_id                INTEGER REFERENCES asset(asset_id),
    asset_identifier        TEXT NOT NULL,
    asset_type              TEXT NOT NULL,
    scope_status            TEXT NOT NULL
                            CHECK (scope_status IN ('in_scope','out_of_scope','under_review','removed')),
    eligible_for_bounty     INTEGER,
    eligible_for_submission INTEGER,
    instruction             TEXT,
    is_current              INTEGER NOT NULL DEFAULT 1,
    verification_status     TEXT NOT NULL DEFAULT 'unverified'
                            CHECK (verification_status IN ('unverified','verified','disputed')),
    source_id               INTEGER,
    first_seen_at           TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at            TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(program_id, asset_identifier, asset_type)
);

CREATE TABLE scope_observation (
    scope_observation_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id            INTEGER REFERENCES bug_bounty_program(program_id),
    source_id             INTEGER,
    snapshot_hash         TEXT NOT NULL,
    observed_at           TEXT NOT NULL DEFAULT (datetime('now')),
    raw_payload           TEXT NOT NULL                       -- JSON as TEXT
);

CREATE TABLE scope_change_event (
    change_event_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id            INTEGER NOT NULL REFERENCES bug_bounty_program(program_id),
    asset_id              INTEGER REFERENCES asset(asset_id),
    change_type           TEXT NOT NULL
                          CHECK (change_type IN (
                              'asset_added','asset_removed','asset_type_changed',
                              'eligibility_changed','instruction_changed',
                              'program_status_changed','other'
                          )),
    old_value             TEXT,                               -- JSON as TEXT
    new_value             TEXT,                               -- JSON as TEXT
    old_value_hash        TEXT NOT NULL,
    new_value_hash        TEXT NOT NULL,
    detected_at           TEXT NOT NULL DEFAULT (datetime('now')),
    source_observation_id INTEGER NOT NULL REFERENCES scope_observation(scope_observation_id),
    review_status         TEXT NOT NULL DEFAULT 'new'
                          CHECK (review_status IN ('new','reviewed','dismissed','queued_for_research')),
    UNIQUE(program_id, change_type, asset_id, old_value_hash, new_value_hash)
);

-- ── Version Tracking ────────────────────────────────────────────

CREATE TABLE version_source (
    version_source_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id              INTEGER NOT NULL REFERENCES asset(asset_id),
    source_type           TEXT NOT NULL
                          CHECK (source_type IN (
                              'github','github_release','api','rss','css_selector',
                              'android_store','ios_store','package_registry',
                              'changedetection_webhook','custom','manual',
                              'js_bundle','xml_diff'
                          )),
    source_url            TEXT,
    source_identifier     TEXT NOT NULL,
    check_method          TEXT NOT NULL,

    -- Pattern stored in the DB (operator requirement)
    -- config JSON shape varies by source_type:
    --   github_release: {"repo":"Shopify/cli","api_endpoint":"/releases/latest","field":"tag_name"}
    --   rss:            {"feed_url":"https://example.com/changelog.xml"}
    --   api:            {"api_url":"https://api.example.com/version","path":"$.version"}
    --   css_selector:   {"page_url":"https://example.com/changelog","selector":"h2.version","attribute":"text"}
    --   custom:         {"script_params":{...}, "any":"other fields"}
    config                TEXT,                               -- JSON as TEXT

    enabled               INTEGER NOT NULL DEFAULT 1,
    check_interval        INTEGER NOT NULL DEFAULT 1800,      -- seconds (30m)

    -- Error handling / self-healing
    -- auto_action stored in error_classification table; on_error_policy governs per-source behavior
    on_error_policy       TEXT NOT NULL DEFAULT 'standard'
                          CHECK (on_error_policy IN (
                              'standard',
                              'retry_aggressive',
                              'trigger_discovery',
                              'alert_only',
                              'silent'
                          )),
    last_checked_at       TEXT,
    last_success_at       TEXT,
    last_error_at         TEXT,
    last_error_code       TEXT,
    last_error            TEXT,
    consecutive_failures  INTEGER NOT NULL DEFAULT 0,
    next_check_at         TEXT,                                -- computed: last_checked_at + check_interval
    UNIQUE(asset_id, source_type, check_method, source_identifier)
);

-- Error classification — stored in DB, queried at runtime
CREATE TABLE error_classification (
    error_class_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    error_code            TEXT NOT NULL UNIQUE,
    description           TEXT NOT NULL,
    is_transient          INTEGER NOT NULL,                   -- 1=retry, 0=structural
    auto_action           TEXT NOT NULL DEFAULT 'log'
                          CHECK (auto_action IN (
                              'log','disable_source','trigger_discovery',
                              'alert_operator','flag_for_review'
                          )),
    discovery_prompt      TEXT,
    max_retries           INTEGER NOT NULL DEFAULT 3,
    created_at            TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT INTO error_classification (error_code, description, is_transient, auto_action, discovery_prompt, max_retries) VALUES
    ('STORAGE_MOVED',     'Changelog/release page returned 301/404 — location moved',          0, 'trigger_discovery', 'Re-discover version sources for {canonical_identifier}. Previous source_type={source_type}, source_url={source_url} returned {error_code}. Find the new location.', 1),
    ('PAGE_STRUCTURE',    'HTML selector that extracted version no longer matches',             0, 'trigger_discovery', 'The version selector for {canonical_identifier} at {source_url} no longer matches. Re-discover the page structure.', 2),
    ('FEED_GONE',         'RSS/Atom URL no longer serves XML or returns 404',                  0, 'trigger_discovery', 'RSS feed at {source_url} for {canonical_identifier} is gone. Find alternative feed or changelog source.', 1),
    ('APP_UNLISTED',      'Play Store / App Store returns not found for package/bundle ID',     0, 'disable_source',    NULL, 1),
    ('AUTH_REQUIRED',     'Repo went private or feed requires authentication',                  0, 'alert_operator',    'Asset {canonical_identifier} source {source_url} now requires authentication. Repo may have gone private.', 1),
    ('RATE_LIMITED',      'API rate limit hit',                                                 1, 'log',               NULL, 3),
    ('TIMEOUT',           'Request timed out',                                                  1, 'log',               NULL, 3),
    ('DNS_FAILURE',       'DNS resolution failed',                                              1, 'log',               NULL, 3),
    ('TLS_ERROR',         'TLS certificate error',                                              0, 'alert_operator',    'TLS error on {source_url} for {canonical_identifier}.', 2),
    ('PARSE_ERROR',       'Response received but version could not be extracted',               0, 'trigger_discovery', 'Version extraction failed for {canonical_identifier} at {source_url}. Response structure may have changed. Re-discover.', 3),
    ('EMPTY_RESPONSE',    'Response received but body was empty',                               0, 'trigger_discovery', 'Empty response from {source_url} for {canonical_identifier}. Source may have moved or changed format.', 2),
    ('UNKNOWN',           'Unclassified error',                                                 1, 'log',               NULL, 5),
    -- Bot walls are detected and respected, never bypassed. flag_for_review
    -- disables the source and files a research_note for a human to triage.
    ('BOT_WALL',          'Host is blocking automated access (WAF/CDN/bot manager)',            0, 'flag_for_review',   NULL, 2),
    ('CAPTCHA_GATE',      'Interactive captcha gate. Not solved — needs manual review',         0, 'flag_for_review',   NULL, 1);

-- ── Source provenance ───────────────────────────────────────────

CREATE TABLE source (
    source_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type       TEXT NOT NULL
                      CHECK (source_type IN (
                          'github_dataset','h1_api','bugcrowd_api','intigriti_api',
                          'github_commit','github_release','rss_feed','android_store',
                          'ios_store','package_registry','changedetection_webhook',
                          'manual','other'
                      )),
    name              TEXT NOT NULL,
    url               TEXT,
    retrieved_at      TEXT NOT NULL DEFAULT (datetime('now')),
    content_hash      TEXT NOT NULL,
    parser_version    TEXT,
    raw_payload       TEXT                                     -- JSON as TEXT
);

-- ── Observations ────────────────────────────────────────────────

CREATE TABLE version_observation (
    version_observation_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    version_source_id       INTEGER NOT NULL REFERENCES version_source(version_source_id),
    asset_id                INTEGER NOT NULL REFERENCES asset(asset_id),
    version_value           TEXT,
    immutable_identifier    TEXT NOT NULL,
    commit_hash             TEXT,
    release_id              TEXT,
    build_number            TEXT,
    published_at            TEXT,
    observed_at             TEXT NOT NULL DEFAULT (datetime('now')),
    content_hash            TEXT,
    raw_metadata            TEXT,                             -- JSON as TEXT
    source_id               INTEGER REFERENCES source(source_id),
    is_current              INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE version_change_event (
    version_change_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    version_source_id         INTEGER NOT NULL REFERENCES version_source(version_source_id),
    asset_id                  INTEGER NOT NULL REFERENCES asset(asset_id),
    change_type               TEXT NOT NULL
                              CHECK (change_type IN (
                                  'release_published','commit_advanced',
                                  'api_version_changed','build_number_changed',
                                  'changelog_entry_added','content_changed',
                                  'version_regressed','source_disappeared',
                                  'security_header_changed','js_bundle_changed',
                                  'xml_diff_changed'
                              )),
    previous_observation_id   INTEGER REFERENCES version_observation(version_observation_id),
    current_observation_id    INTEGER REFERENCES version_observation(version_observation_id),
    detected_at               TEXT NOT NULL DEFAULT (datetime('now')),
    research_status           TEXT NOT NULL DEFAULT 'new'
                              CHECK (research_status IN (
                                  'new','triaged','investigating','not_relevant','queued','complete'
                              )),
    notes                     TEXT,
    item_identifier           TEXT NOT NULL DEFAULT '',
    change_details            TEXT,
    UNIQUE(version_source_id, current_observation_id, change_type, item_identifier)
);

-- ── Operational tracking ────────────────────────────────────────

CREATE TABLE check_run (
    check_run_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    version_source_id   INTEGER NOT NULL REFERENCES version_source(version_source_id),
    batch_id            TEXT,
    started_at          TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at         TEXT,
    status              TEXT NOT NULL DEFAULT 'running'
                        CHECK (status IN ('running','success','failure','timeout','skipped')),
    error_code          TEXT REFERENCES error_classification(error_code),
    error_message       TEXT,
    content_hash        TEXT,
    changed             INTEGER,
    observation_id      INTEGER REFERENCES version_observation(version_observation_id),
    source_id           INTEGER REFERENCES source(source_id)
);

-- ── Research artifacts ──────────────────────────────────────────

CREATE TABLE finding (
    finding_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    version_change_id   INTEGER REFERENCES version_change_event(version_change_id),
    title               TEXT NOT NULL,
    severity            TEXT,
    platform            TEXT,
    report_id           TEXT,
    bounty_amount       REAL,
    bounty_currency     TEXT DEFAULT 'USD',
    status              TEXT NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft','submitted','triaged','resolved','closed','not_submitted')),
    notes               TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE research_note (
    note_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type         TEXT NOT NULL
                        CHECK (entity_type IN ('target','asset','version_change','finding','program','version_source')),
    entity_id           INTEGER NOT NULL,
    note                TEXT NOT NULL,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ── Indexes ─────────────────────────────────────────────────────

CREATE INDEX idx_version_source_enabled ON version_source(enabled);
CREATE INDEX idx_version_source_last_checked ON version_source(last_checked_at);
CREATE INDEX idx_version_source_failures ON version_source(consecutive_failures);
CREATE INDEX idx_vs_due ON version_source(enabled, next_check_at, last_checked_at);
CREATE INDEX idx_scope_record_status ON scope_record(program_id, scope_status);
CREATE INDEX idx_scope_record_asset ON scope_record(asset_id);
CREATE INDEX idx_version_change_research ON version_change_event(research_status, detected_at DESC);
CREATE INDEX idx_version_change_source ON version_change_event(version_source_id, detected_at DESC);
CREATE INDEX idx_version_obs_source ON version_observation(version_source_id, observed_at DESC);
-- SQLite supports partial indexes (DuckDB does not):
CREATE INDEX idx_version_obs_current ON version_observation(version_source_id) WHERE is_current = 1;
CREATE INDEX idx_program_target_current ON target_asset(target_id, is_current);
CREATE INDEX idx_bug_bounty_program_status ON bug_bounty_program(program_status);
CREATE INDEX idx_check_run_batch ON check_run(batch_id);
CREATE INDEX idx_check_run_status ON check_run(status);
CREATE INDEX idx_asset_type ON asset(vector_type, canonical_identifier);

-- ── Host/subdomain inventory (E.3) ────────────────────────────────

CREATE TABLE discovered_host (
    host_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    hostname            TEXT NOT NULL,
    port                INTEGER NOT NULL DEFAULT 0,    -- 0 = default port for protocol
    protocol            TEXT NOT NULL DEFAULT 'https'
                        CHECK (protocol IN ('http','https','unknown')),
    version_source_id   INTEGER REFERENCES version_source(version_source_id),
    asset_id            INTEGER REFERENCES asset(asset_id),
    source_url          TEXT,
    discovery_method    TEXT NOT NULL DEFAULT 'version_check'
                        CHECK (discovery_method IN ('version_check','manual','scope_import')),
    first_seen_at       TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at        TEXT NOT NULL DEFAULT (datetime('now')),
    is_active           INTEGER NOT NULL DEFAULT 1,
    resolved_ips        TEXT,                              -- JSON array, populated by DNS resolution
    UNIQUE(hostname, port, protocol)
);

CREATE INDEX idx_discovered_host_hostname ON discovered_host(hostname);
CREATE INDEX idx_discovered_host_active ON discovered_host(is_active);

-- ── HTTP cache (ETag/Last-Modified for conditional requests) ─────

CREATE TABLE http_cache (
    url             TEXT PRIMARY KEY,
    etag            TEXT,
    last_modified   TEXT,
    body_hash       TEXT NOT NULL,
    status_code     INTEGER NOT NULL DEFAULT 200,
    cached_at       TEXT NOT NULL DEFAULT (datetime('now')),
    last_hit_at     TEXT NOT NULL DEFAULT (datetime('now')),
    hit_count       INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX idx_http_cache_last_hit ON http_cache(last_hit_at);
