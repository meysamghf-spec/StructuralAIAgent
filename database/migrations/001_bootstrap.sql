-- Migration 001: Bootstrap schema
-- Phase 1 Milestone 1 — minimum infrastructure only
-- Full approved schema deferred to Milestone 2+

CREATE TABLE IF NOT EXISTS schema_migrations (
    id          SERIAL PRIMARY KEY,
    version     VARCHAR(64) NOT NULL UNIQUE,
    name        VARCHAR(255) NOT NULL,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO schema_migrations (version, name)
VALUES ('001', 'bootstrap')
ON CONFLICT (version) DO NOTHING;
