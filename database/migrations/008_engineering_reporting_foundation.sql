-- Migration 008: Engineering reporting foundation
-- Reproducible report metadata and versioned structured content

CREATE TABLE IF NOT EXISTS reports (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    report_type         VARCHAR(64) NOT NULL,
    title               VARCHAR(255) NOT NULL,
    status              VARCHAR(32) NOT NULL DEFAULT 'DRAFT',

    current_version     INTEGER NOT NULL DEFAULT 0,
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_by          VARCHAR(255),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT reports_status_check
        CHECK (status IN ('DRAFT', 'GENERATING', 'COMPLETED', 'FAILED'))
);

CREATE TABLE IF NOT EXISTS report_versions (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id               UUID NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    project_id              UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    version                 INTEGER NOT NULL,
    status                  VARCHAR(32) NOT NULL,
    output_format           VARCHAR(32) NOT NULL DEFAULT 'STRUCTURED',

    content                 JSONB NOT NULL,
    traceability_metadata   JSONB NOT NULL DEFAULT '{}'::jsonb,

    generated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    generated_by            VARCHAR(255),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT report_versions_status_check
        CHECK (status IN ('GENERATING', 'COMPLETED', 'FAILED')),
    CONSTRAINT report_versions_unique_version UNIQUE (report_id, version)
);

CREATE INDEX IF NOT EXISTS idx_reports_project_id
    ON reports(project_id);

CREATE INDEX IF NOT EXISTS idx_reports_project_type
    ON reports(project_id, report_type);

CREATE INDEX IF NOT EXISTS idx_report_versions_report_id
    ON report_versions(report_id, version DESC);

CREATE INDEX IF NOT EXISTS idx_report_versions_project_id
    ON report_versions(project_id, generated_at DESC);

INSERT INTO schema_migrations (version, name)
VALUES ('008', 'engineering_reporting_foundation')
ON CONFLICT (version) DO NOTHING;
