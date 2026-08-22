-- User identity and project ownership foundation

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(320) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name VARCHAR(255),
    account_id VARCHAR(255) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_account_id ON users(account_id);

ALTER TABLE projects
    ADD COLUMN IF NOT EXISTS owner_account_id VARCHAR(255) NOT NULL DEFAULT 'legacy';

CREATE INDEX IF NOT EXISTS idx_projects_owner_account_id ON projects(owner_account_id);

UPDATE projects
SET owner_account_id = 'legacy'
WHERE owner_account_id IS NULL OR owner_account_id = '';

INSERT INTO schema_migrations (version, name)
VALUES ('018', 'user_identity_foundation')
ON CONFLICT (version) DO NOTHING;
