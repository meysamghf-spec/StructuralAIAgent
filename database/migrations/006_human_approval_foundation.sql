-- Migration 006: Human Approval Gate foundation
-- Persistent approval workflows with project isolation and audit history

CREATE TABLE IF NOT EXISTS human_approval_requests (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    requester           VARCHAR(255) NOT NULL,
    target_type         VARCHAR(64) NOT NULL,
    target_action       VARCHAR(255) NOT NULL,
    target_object_type  VARCHAR(64),
    target_object_id    UUID,

    summary             TEXT NOT NULL,
    status              VARCHAR(32) NOT NULL DEFAULT 'PENDING',

    approver            VARCHAR(255),
    decision            VARCHAR(32),
    rejection_reason    TEXT,

    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,

    requested_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT human_approval_requests_status_check
        CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED'))
);

CREATE TABLE IF NOT EXISTS human_approval_events (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    approval_request_id UUID NOT NULL REFERENCES human_approval_requests(id) ON DELETE CASCADE,
    project_id          UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    event_type          VARCHAR(32) NOT NULL,
    actor               VARCHAR(255) NOT NULL,
    reason              TEXT,
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT human_approval_events_event_type_check
        CHECK (event_type IN ('CREATED', 'APPROVED', 'REJECTED', 'CANCELLED'))
);

CREATE INDEX IF NOT EXISTS idx_human_approval_requests_project_id
    ON human_approval_requests(project_id);

CREATE INDEX IF NOT EXISTS idx_human_approval_requests_project_status
    ON human_approval_requests(project_id, status);

CREATE INDEX IF NOT EXISTS idx_human_approval_requests_project_requested
    ON human_approval_requests(project_id, requested_at DESC);

CREATE INDEX IF NOT EXISTS idx_human_approval_events_project_id
    ON human_approval_events(project_id);

CREATE INDEX IF NOT EXISTS idx_human_approval_events_request_id
    ON human_approval_events(approval_request_id, created_at ASC);

INSERT INTO schema_migrations (version, name)
VALUES ('006', 'human_approval_foundation')
ON CONFLICT (version) DO NOTHING;
