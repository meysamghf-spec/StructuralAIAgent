-- Engineering learning records. Distinct from project_memory: these are
-- approval-gated, scope-isolated experience items, not PEM data.

CREATE TABLE IF NOT EXISTS engineering_learning_records (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id            UUID REFERENCES projects(id) ON DELETE CASCADE,
    owner_account_id      VARCHAR(255) NOT NULL,
    agent_id              VARCHAR(255),
    task_id               UUID,
    source_snapshot_id    UUID,
    source_element_ids    JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_element_type   VARCHAR(64),
    input_context         JSONB NOT NULL DEFAULT '{}'::jsonb,
    agent_output          JSONB NOT NULL DEFAULT '{}'::jsonb,
    human_correction      JSONB,
    engineering_reason    TEXT,
    validation_result     VARCHAR(64) NOT NULL DEFAULT 'NOT_CHECKED',
    approval_status       VARCHAR(32) NOT NULL DEFAULT 'CANDIDATE',
    learning_scope        VARCHAR(32) NOT NULL,
    applicability         JSONB NOT NULL DEFAULT '{}'::jsonb,
    confidence            DOUBLE PRECISION,
    provenance            JSONB NOT NULL DEFAULT '{}'::jsonb,
    reviewed_by           VARCHAR(255),
    reviewed_at           TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT engineering_learning_scope_check
        CHECK (learning_scope IN ('PROJECT', 'ENGINEER', 'GLOBAL')),
    CONSTRAINT engineering_learning_status_check
        CHECK (approval_status IN ('CANDIDATE', 'REVIEW', 'APPROVED', 'REJECTED')),
    CONSTRAINT engineering_learning_project_scope_check
        CHECK (learning_scope <> 'PROJECT' OR project_id IS NOT NULL),
    CONSTRAINT engineering_learning_confidence_check
        CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1))
);

CREATE INDEX IF NOT EXISTS idx_engineering_learning_project
    ON engineering_learning_records(project_id, approval_status);

CREATE INDEX IF NOT EXISTS idx_engineering_learning_owner_scope
    ON engineering_learning_records(owner_account_id, learning_scope, approval_status);

CREATE INDEX IF NOT EXISTS idx_engineering_learning_created
    ON engineering_learning_records(created_at ASC, id ASC);

CREATE TABLE IF NOT EXISTS engineering_learning_uses (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    learning_record_id    UUID NOT NULL REFERENCES engineering_learning_records(id) ON DELETE CASCADE,
    project_id            UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    task_id               UUID NOT NULL,
    explanation           TEXT NOT NULL,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_engineering_learning_uses_task
    ON engineering_learning_uses(project_id, task_id, created_at ASC);

INSERT INTO schema_migrations (version, name)
VALUES ('021', 'engineering_learning_foundation')
ON CONFLICT (version) DO NOTHING;
