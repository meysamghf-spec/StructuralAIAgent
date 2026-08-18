-- Migration 009: Engineering Agent Runtime foundation
-- Project-scoped agent executions; extends agent_definitions with agent_type

ALTER TABLE agent_definitions
    ADD COLUMN IF NOT EXISTS agent_type VARCHAR(64);

ALTER TABLE agent_definitions
    ADD COLUMN IF NOT EXISTS configuration JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_agent_definitions_agent_type
    ON agent_definitions(agent_type);

CREATE TABLE IF NOT EXISTS agent_executions (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id              UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    agent_definition_id     UUID NOT NULL REFERENCES agent_definitions(id) ON DELETE RESTRICT,
    agent_version           INTEGER NOT NULL,

    execution_status        VARCHAR(32) NOT NULL DEFAULT 'CREATED',
    input_request           JSONB NOT NULL DEFAULT '{}'::jsonb,
    context_snapshot        JSONB NOT NULL DEFAULT '{}'::jsonb,
    output                  JSONB,
    agent_result            JSONB,
    validation_status       VARCHAR(32),
    traceability_metadata   JSONB NOT NULL DEFAULT '{}'::jsonb,
    prompt_generation       JSONB,
    approval_request_id     UUID REFERENCES human_approval_requests(id) ON DELETE SET NULL,
    error_metadata          JSONB NOT NULL DEFAULT '{}'::jsonb,

    started_at              TIMESTAMPTZ,
    completed_at            TIMESTAMPTZ,
    created_by              VARCHAR(255),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT agent_executions_status_check
        CHECK (execution_status IN (
            'CREATED', 'RUNNING', 'COMPLETED', 'FAILED',
            'WAITING_APPROVAL', 'CANCELLED'
        ))
);

CREATE INDEX IF NOT EXISTS idx_agent_executions_project_id
    ON agent_executions(project_id);

CREATE INDEX IF NOT EXISTS idx_agent_executions_project_status
    ON agent_executions(project_id, execution_status);

CREATE INDEX IF NOT EXISTS idx_agent_executions_agent_definition
    ON agent_executions(agent_definition_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_executions_created
    ON agent_executions(project_id, created_at DESC);

INSERT INTO schema_migrations (version, name)
VALUES ('009', 'agent_runtime_foundation')
ON CONFLICT (version) DO NOTHING;
