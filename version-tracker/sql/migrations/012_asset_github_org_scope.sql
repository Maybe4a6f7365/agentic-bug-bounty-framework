-- Migration 012 — extend asset.vector_type CHECK to allow 'github_org_scope'.
--
-- The 2026-08-06 SOURCE_CODE wildcard fix introduced a new vector_type
-- 'github_org_scope' for org-wide scope wildcards (e.g., 'Shopify/*').
-- The migration 011 extended the version_source.source_type CHECK
-- but missed the asset.vector_type CHECK.
--
-- SQLite can't modify a CHECK constraint in place, so we rebuild the
-- table with the extended constraint.

CREATE TABLE asset_new (
    asset_id                INTEGER PRIMARY KEY AUTOINCREMENT,
    vector_type             TEXT NOT NULL
                            CHECK (vector_type IN (
                                'website','api','github_repository','github_org_scope',
                                'android_app','ios_app','package','docker_image','other'
                            )),
    canonical_identifier    TEXT NOT NULL,
    display_name            TEXT,
    description             TEXT,
    environment             TEXT
                            CHECK (environment IN ('prod','staging','dev','unknown')),
    status                  TEXT NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active','deprecated','removed')),
    discovery_method        TEXT,
    discovery_source_url    TEXT,
    metadata                TEXT,
    first_seen_at           TEXT NOT NULL,
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(vector_type, canonical_identifier)
);

INSERT INTO asset_new
SELECT asset_id, vector_type, canonical_identifier, display_name, description,
       environment, status, discovery_method, discovery_source_url, metadata,
       first_seen_at, created_at, updated_at
FROM asset;

DROP TABLE asset;

ALTER TABLE asset_new RENAME TO asset;

CREATE INDEX idx_asset_type ON asset(vector_type, canonical_identifier);