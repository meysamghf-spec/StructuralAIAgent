-- Migration 004: File ingestion foundation
-- Phase 1 Milestone 5 — project-scoped file registry and metadata
-- Does not link to PEM, Project Memory, or agent execution

CREATE TABLE IF NOT EXISTS project_files (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id         UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    filename           VARCHAR(255) NOT NULL,
    content_type       VARCHAR(128),
    file_type          VARCHAR(64) NOT NULL,
    file_version       INTEGER NOT NULL,
    source             VARCHAR(64) NOT NULL,
    upload_time        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    parsing_status     VARCHAR(32) NOT NULL,
    extraction_status  VARCHAR(32) NOT NULL,
    confidence         DOUBLE PRECISION,
    storage_path       VARCHAR(512) NOT NULL,
    metadata           JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by         VARCHAR(255),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_project_files_project_filename_version UNIQUE (project_id, filename, file_version)
);

CREATE INDEX IF NOT EXISTS idx_project_files_project_id
    ON project_files(project_id);

CREATE INDEX IF NOT EXISTS idx_project_files_project_upload_time
    ON project_files(project_id, upload_time DESC);

INSERT INTO schema_migrations (version, name)
VALUES ('004', 'file_ingestion_foundation')
ON CONFLICT (version) DO NOTHING;
