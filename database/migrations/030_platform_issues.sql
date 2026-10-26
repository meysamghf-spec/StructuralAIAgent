-- Platform helper: structured issue reports (user reported or auto detected). Records only; no code is changed by them.
CREATE TABLE IF NOT EXISTS platform_issues (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    category VARCHAR(32) NOT NULL DEFAULT 'bug',
    severity VARCHAR(16) NOT NULL DEFAULT 'medium',
    source VARCHAR(24) NOT NULL DEFAULT 'user_report',
    status VARCHAR(24) NOT NULL DEFAULT 'open',
    page VARCHAR(255) NOT NULL DEFAULT '',
    conversation_id VARCHAR(64) NOT NULL DEFAULT '',
    project_id VARCHAR(64) NOT NULL DEFAULT '',
    account_id VARCHAR(255) NOT NULL DEFAULT '',
    user_message TEXT NOT NULL DEFAULT '',
    assistant_excerpt TEXT NOT NULL DEFAULT '',
    error_text TEXT NOT NULL DEFAULT '',
    steps_to_reproduce JSONB NOT NULL DEFAULT '[]'::jsonb,
    expected TEXT NOT NULL DEFAULT '',
    actual TEXT NOT NULL DEFAULT '',
    suspected_files JSONB NOT NULL DEFAULT '[]'::jsonb,
    app_version VARCHAR(64) NOT NULL DEFAULT '',
    locale VARCHAR(16) NOT NULL DEFAULT '',
    dedupe_key VARCHAR(64) NOT NULL,
    occurrences INTEGER NOT NULL DEFAULT 1,
    fix_note TEXT NOT NULL DEFAULT '',
    fix_pr_url TEXT NOT NULL DEFAULT '',
    proposed_fix JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_platform_issues_status ON platform_issues(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_platform_issues_dedupe ON platform_issues(dedupe_key);
CREATE INDEX IF NOT EXISTS idx_platform_issues_account ON platform_issues(account_id, created_at DESC);
