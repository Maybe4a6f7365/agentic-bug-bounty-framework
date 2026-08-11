-- Migration 003: program_policy table
-- Stores scraped HackerOne policy page content: vuln-class rules,
-- testing restrictions, safe harbor, scope descriptions, etc.
-- Populated via browser-based enrichment (scripts/enrich_policy.py).

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

-- Index for fast lookups by program
CREATE INDEX IF NOT EXISTS idx_program_policy_program ON program_policy(program_id, is_current);
