-- Migration 011: Analysis engine foundation
-- Persistent analysis runs linked to PEM snapshots

CREATE TABLE IF NOT EXISTS analysis_runs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    pem_snapshot_id     UUID NOT NULL,
    pem_version         INTEGER NOT NULL,

    analysis_type       VARCHAR(64) NOT NULL,
    status              VARCHAR(32) NOT NULL,
    capability_status   VARCHAR(64) NOT NULL,

    message             TEXT NOT NULL,

    inputs              JSONB NOT NULL DEFAULT '{}'::jsonb,
    outputs             JSONB NOT NULL DEFAULT '{}'::jsonb,
    model_summary       JSONB NOT NULL DEFAULT '{}'::jsonb,
    validation_summary  JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_by          VARCHAR(255),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ,

    CONSTRAINT analysis_runs_status_check
        CHECK (status IN (
            'CREATED',
            'RUNNING',
            'SUCCESS',
            'WARNING',
            'FAILED',
            'NOT_IMPLEMENTED',
            'REQUIRES_SOLVER',
            'MODEL_NOT_READY'
        ))
);

CREATE INDEX IF NOT EXISTS idx_analysis_runs_project_id
    ON analysis_runs(project_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_analysis_runs_project_pem_version
    ON analysis_runs(project_id, pem_version DESC);

CREATE INDEX IF NOT EXISTS idx_analysis_runs_project_type
    ON analysis_runs(project_id, analysis_type);

INSERT INTO schema_migrations (version, name)
VALUES ('011', 'analysis_engine_foundation')
ON CONFLICT (version) DO NOTHING;
