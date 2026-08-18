# Database Migrations

PostgreSQL is the primary database (AG-34).

## Structure

- `migrations/` — ordered SQL migration files applied in lexical order
- `001_bootstrap.sql` — schema migration tracking table (Milestone 1)
- `002_pem_foundation.sql` — projects, PEM snapshots (JSONB), revisions (Milestone 2)
- `003_agent_foundation.sql` — agent registry, versions, capabilities, prompts (Milestone 4)
- `004_file_ingestion_foundation.sql` — project-scoped file registry (Milestone 5)

## Milestone 2 Schema

| Table | Purpose |
|-------|---------|
| `projects` | Project registry; root of project isolation via `project_id` |
| `pem_snapshots` | Versioned `ProjectEngineeringModel` documents (JSONB SSOT) |
| `revisions` | Traceable change records linking before/after PEM snapshots |

`CodeConfiguration` and `UnitConfiguration` are first-class structures embedded in `pem_snapshots.snapshot_data`.

## Milestone 4 Schema

| Table | Purpose |
|-------|---------|
| `agent_definitions` | Platform-scoped agent registry entries |
| `agent_versions` | Immutable versioned agent configurations |
| `agent_capabilities` | Capability catalog |
| `agent_version_capabilities` | Capabilities assigned to a version |
| `prompt_templates` | Versioned prompt templates per agent version |

Agent definitions are **platform-scoped** (no `project_id`). Project isolation remains on PEM/project tables.

## Milestone 5 Schema

| Table | Purpose |
|-------|---------|
| `project_files` | Project-scoped uploaded file metadata, parsing/extraction status, storage path |

Files are stored on the local filesystem (`FILE_STORAGE_ROOT`); the database holds metadata only. No PEM linkage in M5.

## Configuration

Set `DATABASE_URL` in `.env` (see root `.env.example`):

```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/structuralaiaagent
```

Optional test database:

```
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/structuralaiaagent_test
```

File storage (M5):

```
FILE_STORAGE_ROOT=/absolute/path/outside/repo/file_storage
MAX_UPLOAD_BYTES=10485760
```

## Apply migrations (manual)

```bash
psql "$DATABASE_URL" -f database/migrations/001_bootstrap.sql
psql "$DATABASE_URL" -f database/migrations/002_pem_foundation.sql
psql "$DATABASE_URL" -f database/migrations/003_agent_foundation.sql
psql "$DATABASE_URL" -f database/migrations/004_file_ingestion_foundation.sql
```

Backend persistence tests apply migrations automatically when PostgreSQL is reachable.

## Verify schema

```bash
psql "$DATABASE_URL" -c "\dt"
psql "$DATABASE_URL" -c "\d pem_snapshots"
```
