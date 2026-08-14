-- Migration 002: PEM persistence foundation
-- Phase 1 Milestone 2 — Project, PEM snapshots, revisions
-- CodeConfiguration and UnitConfiguration are stored as first-class PEM structures in snapshot_data (JSONB)

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS projects (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pem_snapshots (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id    UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    version       INTEGER NOT NULL,
    snapshot_data JSONB NOT NULL,
    is_current    BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_pem_snapshots_project_version UNIQUE (project_id, version)
);

CREATE INDEX IF NOT EXISTS idx_pem_snapshots_project_id
    ON pem_snapshots(project_id);

CREATE INDEX IF NOT EXISTS idx_pem_snapshots_project_current
    ON pem_snapshots(project_id)
    WHERE is_current = TRUE;

CREATE INDEX IF NOT EXISTS idx_pem_snapshots_snapshot_data_gin
    ON pem_snapshots USING GIN (snapshot_data);

CREATE TABLE IF NOT EXISTS revisions (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id         UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    revision_number    INTEGER NOT NULL,
    change_type        VARCHAR(64) NOT NULL,
    summary            TEXT NOT NULL,
    before_snapshot_id UUID REFERENCES pem_snapshots(id) ON DELETE SET NULL,
    after_snapshot_id  UUID NOT NULL REFERENCES pem_snapshots(id) ON DELETE RESTRICT,
    created_by         VARCHAR(255),
    metadata           JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_revisions_project_number UNIQUE (project_id, revision_number)
);

CREATE INDEX IF NOT EXISTS idx_revisions_project_id
    ON revisions(project_id);

CREATE INDEX IF NOT EXISTS idx_revisions_after_snapshot_id
    ON revisions(after_snapshot_id);

INSERT INTO schema_migrations (version, name)
VALUES ('002', 'pem_foundation')
ON CONFLICT (version) DO NOTHING;
