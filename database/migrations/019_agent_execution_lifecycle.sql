-- Migration 019: Extended agent execution lifecycle states

ALTER TABLE agent_executions
    DROP CONSTRAINT IF EXISTS agent_executions_status_check;

ALTER TABLE agent_executions
    ADD CONSTRAINT agent_executions_status_check
        CHECK (execution_status IN (
            'QUEUED', 'CREATED', 'RUNNING', 'COMPLETED', 'FAILED', 'BLOCKED',
            'REQUIRES_HUMAN_APPROVAL', 'WAITING_APPROVAL', 'CANCELLED'
        ));

INSERT INTO schema_migrations (version, name)
VALUES ('019', 'agent_execution_lifecycle')
ON CONFLICT (version) DO NOTHING;
