-- Migration 003: Agent Foundation
-- Phase 1 Milestone 4 — platform-scoped agent registry, versioning, capabilities, prompts
-- AgentExecution and HumanApprovalGate remain application/domain contracts only (no tables)

CREATE TABLE IF NOT EXISTS agent_capabilities (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key         VARCHAR(128) NOT NULL,
    name        VARCHAR(255) NOT NULL,
    description TEXT,
    metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_agent_capabilities_key UNIQUE (key)
);

CREATE INDEX IF NOT EXISTS idx_agent_capabilities_key
    ON agent_capabilities(key);

CREATE TABLE IF NOT EXISTS agent_definitions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key             VARCHAR(128) NOT NULL,
    name            VARCHAR(255) NOT NULL,
    description     TEXT,
    status          VARCHAR(32) NOT NULL,
    current_version INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_agent_definitions_key UNIQUE (key)
);

CREATE INDEX IF NOT EXISTS idx_agent_definitions_status
    ON agent_definitions(status);

CREATE TABLE IF NOT EXISTS agent_versions (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_definition_id     UUID NOT NULL REFERENCES agent_definitions(id) ON DELETE CASCADE,
    version                 INTEGER NOT NULL,
    instructions            TEXT,
    configuration_metadata  JSONB NOT NULL DEFAULT '{}'::jsonb,
    status                  VARCHAR(32) NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by              VARCHAR(255),
    CONSTRAINT uq_agent_versions_definition_version UNIQUE (agent_definition_id, version)
);

CREATE INDEX IF NOT EXISTS idx_agent_versions_definition_id
    ON agent_versions(agent_definition_id);

CREATE INDEX IF NOT EXISTS idx_agent_versions_definition_status
    ON agent_versions(agent_definition_id, status);

CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_versions_one_active
    ON agent_versions(agent_definition_id)
    WHERE status = 'ACTIVE';

CREATE TABLE IF NOT EXISTS agent_version_capabilities (
    agent_version_id UUID NOT NULL REFERENCES agent_versions(id) ON DELETE CASCADE,
    capability_id    UUID NOT NULL REFERENCES agent_capabilities(id) ON DELETE RESTRICT,
    PRIMARY KEY (agent_version_id, capability_id)
);

CREATE INDEX IF NOT EXISTS idx_agent_version_capabilities_capability_id
    ON agent_version_capabilities(capability_id);

CREATE TABLE IF NOT EXISTS prompt_templates (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_version_id UUID NOT NULL REFERENCES agent_versions(id) ON DELETE CASCADE,
    version          INTEGER NOT NULL,
    name             VARCHAR(255) NOT NULL,
    template         TEXT NOT NULL,
    variables_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
    status           VARCHAR(32) NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by       VARCHAR(255),
    CONSTRAINT uq_prompt_templates_version_version UNIQUE (agent_version_id, version)
);

CREATE INDEX IF NOT EXISTS idx_prompt_templates_agent_version_id
    ON prompt_templates(agent_version_id);

INSERT INTO schema_migrations (version, name)
VALUES ('003', 'agent_foundation')
ON CONFLICT (version) DO NOTHING;
