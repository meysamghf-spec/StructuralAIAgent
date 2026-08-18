-- Migration 007: Traceability chain persistence
-- Polymorphic provenance links with project isolation

CREATE TABLE IF NOT EXISTS traceability_links (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    source_type         VARCHAR(64) NOT NULL,
    source_id           UUID NOT NULL,
    target_type         VARCHAR(64) NOT NULL,
    target_id           UUID NOT NULL,

    relationship_type   VARCHAR(64) NOT NULL,
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_traceability_links_project_id
    ON traceability_links(project_id);

CREATE INDEX IF NOT EXISTS idx_traceability_links_source
    ON traceability_links(project_id, source_type, source_id);

CREATE INDEX IF NOT EXISTS idx_traceability_links_target
    ON traceability_links(project_id, target_type, target_id);

CREATE INDEX IF NOT EXISTS idx_traceability_links_relationship
    ON traceability_links(project_id, relationship_type);

CREATE INDEX IF NOT EXISTS idx_traceability_links_created
    ON traceability_links(project_id, created_at ASC);

INSERT INTO schema_migrations (version, name)
VALUES ('007', 'traceability_foundation')
ON CONFLICT (version) DO NOTHING;
