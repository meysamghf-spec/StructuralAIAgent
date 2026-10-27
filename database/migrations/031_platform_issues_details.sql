-- Feature-request auto-report: structured, non-sensitive details for an issue (capability key, size / ETA, closest
-- alternative, project context). Additive and idempotent; old code ignores the column, bug issues keep '{}'.
ALTER TABLE platform_issues ADD COLUMN IF NOT EXISTS details JSONB NOT NULL DEFAULT '{}'::jsonb;
CREATE INDEX IF NOT EXISTS idx_platform_issues_category ON platform_issues(category, created_at DESC);
