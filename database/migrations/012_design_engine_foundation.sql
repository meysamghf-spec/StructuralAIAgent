-- Migration 012: Design engine foundation
-- Persistent design runs linked to PEM snapshots and optional analysis runs

CREATE TABLE IF NOT EXISTS design_runs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    pem_snapshot_id     UUID NOT NULL,
    pem_version         INTEGER NOT NULL,
    analysis_run_id     UUID REFERENCES analysis_runs(id) ON DELETE SET NULL,

    design_type         VARCHAR(64) NOT NULL,
    status              VARCHAR(32) NOT NULL,
    capability_status   VARCHAR(64) NOT NULL,

    message             TEXT NOT NULL,
    code_edition        VARCHAR(128),

    inputs              JSONB NOT NULL DEFAULT '{}'::jsonb,
    outputs             JSONB NOT NULL DEFAULT '{}'::jsonb,
    model_summary       JSONB NOT NULL DEFAULT '{}'::jsonb,
    validation_summary  JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_by          VARCHAR(255),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ,

    CONSTRAINT design_runs_status_check
        CHECK (status IN (
            'CREATED',
            'RUNNING',
            'PASS',
            'FAIL',
            'WARNING',
            'NOT_IMPLEMENTED',
            'REQUIRES_SOLVER',
            'REQUIRES_ANALYSIS',
            'MODEL_NOT_READY',
            'REQUIRES_ENGINEER_REVIEW'
        ))
);

CREATE INDEX IF NOT EXISTS idx_design_runs_project_id
    ON design_runs(project_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_design_runs_project_pem_version
    ON design_runs(project_id, pem_version DESC);

CREATE INDEX IF NOT EXISTS idx_design_runs_analysis_run_id
    ON design_runs(analysis_run_id);

CREATE INDEX IF NOT EXISTS idx_design_runs_project_type
    ON design_runs(project_id, design_type);

INSERT INTO schema_migrations (version, name)
VALUES ('012', 'design_engine_foundation')
ON CONFLICT (version) DO NOTHING;
