-- Migration 013: Optimization engine foundation
-- Persistent optimization runs linked to PEM, analysis, and design runs

CREATE TABLE IF NOT EXISTS optimization_runs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    pem_snapshot_id     UUID NOT NULL,
    pem_version         INTEGER NOT NULL,
    analysis_run_id     UUID REFERENCES analysis_runs(id) ON DELETE SET NULL,
    design_run_id       UUID REFERENCES design_runs(id) ON DELETE SET NULL,

    optimization_type   VARCHAR(64) NOT NULL,
    objective           VARCHAR(255) NOT NULL,
    status              VARCHAR(32) NOT NULL,
    capability_status   VARCHAR(64) NOT NULL,

    message             TEXT NOT NULL,
    code_edition        VARCHAR(128),

    constraints         JSONB NOT NULL DEFAULT '{}'::jsonb,
    inputs              JSONB NOT NULL DEFAULT '{}'::jsonb,
    outputs             JSONB NOT NULL DEFAULT '{}'::jsonb,
    model_summary       JSONB NOT NULL DEFAULT '{}'::jsonb,
    validation_summary  JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_by          VARCHAR(255),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ,

    CONSTRAINT optimization_runs_status_check
        CHECK (status IN (
            'CREATED',
            'RUNNING',
            'PASS',
            'FAIL',
            'WARNING',
            'NOT_IMPLEMENTED',
            'REQUIRES_SOLVER',
            'REQUIRES_ANALYSIS',
            'REQUIRES_DESIGN',
            'MODEL_NOT_READY',
            'REQUIRES_ENGINEER_REVIEW'
        ))
);

CREATE INDEX IF NOT EXISTS idx_optimization_runs_project_id
    ON optimization_runs(project_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_optimization_runs_project_pem_version
    ON optimization_runs(project_id, pem_version DESC);

CREATE INDEX IF NOT EXISTS idx_optimization_runs_analysis_run_id
    ON optimization_runs(analysis_run_id);

CREATE INDEX IF NOT EXISTS idx_optimization_runs_design_run_id
    ON optimization_runs(design_run_id);

INSERT INTO schema_migrations (version, name)
VALUES ('013', 'optimization_engine_foundation')
ON CONFLICT (version) DO NOTHING;
