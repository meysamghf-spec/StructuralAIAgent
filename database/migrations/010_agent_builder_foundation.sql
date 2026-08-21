-- Migration 010: Agent Builder foundation
-- Project-scoped agents, version tests, publication audit trail

ALTER TABLE agent_definitions
    ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES projects(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_agent_definitions_project_id
    ON agent_definitions(project_id);

ALTER TABLE agent_definitions
    DROP CONSTRAINT IF EXISTS uq_agent_definitions_key;

CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_definitions_global_key
    ON agent_definitions(key)
    WHERE project_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_definitions_project_key
    ON agent_definitions(project_id, key)
    WHERE project_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS agent_version_tests (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_definition_id UUID NOT NULL REFERENCES agent_definitions(id) ON DELETE CASCADE,
    agent_version       INTEGER NOT NULL,
    project_id          UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    test_input          JSONB NOT NULL DEFAULT '{}'::jsonb,
    result              JSONB NOT NULL DEFAULT '{}'::jsonb,
    validation_status   VARCHAR(32),
    errors              JSONB NOT NULL DEFAULT '[]'::jsonb,
    execution_metadata  JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by          VARCHAR(255),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_version_tests_definition_version
    ON agent_version_tests(agent_definition_id, agent_version, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_version_tests_project_id
    ON agent_version_tests(project_id);

CREATE TABLE IF NOT EXISTS agent_builder_publications (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_definition_id UUID NOT NULL REFERENCES agent_definitions(id) ON DELETE CASCADE,
    agent_version       INTEGER NOT NULL,
    project_id          UUID REFERENCES projects(id) ON DELETE SET NULL,
    action              VARCHAR(64) NOT NULL,
    status              VARCHAR(32) NOT NULL,
    approval_request_id UUID REFERENCES human_approval_requests(id) ON DELETE SET NULL,
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by          VARCHAR(255),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_builder_publications_definition
    ON agent_builder_publications(agent_definition_id, created_at DESC);

INSERT INTO schema_migrations (version, name)
VALUES ('010', 'agent_builder_foundation')
ON CONFLICT (version) DO NOTHING;
