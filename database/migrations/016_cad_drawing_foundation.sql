-- Migration 016: CAD drawing generation foundation

CREATE TABLE IF NOT EXISTS cad_drawings (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    pem_snapshot_id     UUID NOT NULL,
    pem_version         INTEGER NOT NULL,

    drawing_type        VARCHAR(64) NOT NULL,
    output_format       VARCHAR(16) NOT NULL,
    status              VARCHAR(64) NOT NULL,
    validation_status   VARCHAR(64) NOT NULL,

    message             TEXT NOT NULL,
    file_path           TEXT,
    layer_summary       JSONB NOT NULL DEFAULT '{}'::jsonb,
    drawing_metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
    validation_summary  JSONB NOT NULL DEFAULT '{}'::jsonb,
    provenance          JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_by          VARCHAR(255),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_cad_drawings_project_id
    ON cad_drawings(project_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_cad_drawings_pem_version
    ON cad_drawings(project_id, pem_version DESC);

INSERT INTO schema_migrations (version, name)
VALUES ('016', 'cad_drawing_foundation')
ON CONFLICT (version) DO NOTHING;
