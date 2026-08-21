-- Migration 015: Validated engineering result ingestion foundation

CREATE TABLE IF NOT EXISTS engineering_result_sets (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id              UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    analysis_run_id         UUID REFERENCES analysis_runs(id) ON DELETE SET NULL,
    integration_execution_id UUID REFERENCES integration_executions(id) ON DELETE SET NULL,

    pem_snapshot_id         UUID NOT NULL,
    pem_version             INTEGER NOT NULL,

    software                VARCHAR(32) NOT NULL,
    software_version        VARCHAR(64) NOT NULL,
    analysis_type           VARCHAR(64) NOT NULL,

    validation_status       VARCHAR(64) NOT NULL,
    engineering_results_available BOOLEAN NOT NULL DEFAULT FALSE,

    result_types            JSONB NOT NULL DEFAULT '[]'::jsonb,
    results                 JSONB NOT NULL DEFAULT '{}'::jsonb,
    provenance              JSONB NOT NULL DEFAULT '{}'::jsonb,
    validation_summary      JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata                JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_by              VARCHAR(255),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_engineering_result_sets_project_id
    ON engineering_result_sets(project_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_engineering_result_sets_analysis_run_id
    ON engineering_result_sets(analysis_run_id);

CREATE INDEX IF NOT EXISTS idx_engineering_result_sets_integration_execution_id
    ON engineering_result_sets(integration_execution_id);

INSERT INTO schema_migrations (version, name)
VALUES ('015', 'engineering_result_ingestion_foundation')
ON CONFLICT (version) DO NOTHING;
