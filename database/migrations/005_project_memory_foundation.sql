-- Migration 005: Project Memory foundation
-- Phase 3 - Project Memory
CREATE TABLE IF NOT EXISTS project_memory (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    memory_type         VARCHAR(64) NOT NULL,
    content             TEXT NOT NULL,

    source_type         VARCHAR(64),
    source_id           UUID,

    confidence          DOUBLE PRECISION,

    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_by          VARCHAR(255),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_project_memory_project_id
    ON project_memory(project_id);

CREATE INDEX IF NOT EXISTS idx_project_memory_project_type
    ON project_memory(project_id, memory_type);

CREATE INDEX IF NOT EXISTS idx_project_memory_project_created
    ON project_memory(project_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_project_memory_metadata_gin
    ON project_memory USING GIN (metadata);

INSERT INTO schema_migrations (version, name)
VALUES ('005', 'project_memory_foundation')
ON CONFLICT (version) DO NOTHING;
