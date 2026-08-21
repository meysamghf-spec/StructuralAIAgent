-- Migration 014: External solver integration foundation
-- Persistent integration executions and analysis status extension

CREATE TABLE IF NOT EXISTS integration_executions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    software            VARCHAR(32) NOT NULL,
    operation           VARCHAR(64) NOT NULL,
    status              VARCHAR(64) NOT NULL,

    pem_snapshot_id     UUID,
    pem_version         INTEGER,
    analysis_run_id     UUID REFERENCES analysis_runs(id) ON DELETE SET NULL,

    message             TEXT NOT NULL,
    inputs              JSONB NOT NULL DEFAULT '{}'::jsonb,
    outputs             JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_by          VARCHAR(255),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_integration_executions_project_id
    ON integration_executions(project_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_integration_executions_software
    ON integration_executions(project_id, software, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_integration_executions_analysis_run_id
    ON integration_executions(analysis_run_id);

ALTER TABLE analysis_runs DROP CONSTRAINT IF EXISTS analysis_runs_status_check;

ALTER TABLE analysis_runs ADD CONSTRAINT analysis_runs_status_check
    CHECK (status IN (
        'CREATED',
        'RUNNING',
        'SUCCESS',
        'WARNING',
        'FAILED',
        'NOT_IMPLEMENTED',
        'REQUIRES_SOLVER',
        'REQUIRES_LOCAL_SOFTWARE',
        'MODEL_NOT_READY'
    ));

INSERT INTO schema_migrations (version, name)
VALUES ('014', 'external_solver_integration_foundation')
ON CONFLICT (version) DO NOTHING;
