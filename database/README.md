# Database Migrations

PostgreSQL is the primary database (AG-34).

## Structure

- `migrations/` — ordered SQL migration files applied in lexical order
- `001_bootstrap.sql` — schema migration tracking table (Milestone 1)
- `002_pem_foundation.sql` — projects, PEM snapshots (JSONB), revisions (Milestone 2)

## Milestone 2 Schema

| Table | Purpose |
|-------|---------|
| `projects` | Project registry; root of project isolation via `project_id` |
| `pem_snapshots` | Versioned `ProjectEngineeringModel` documents (JSONB SSOT) |
| `revisions` | Traceable change records linking before/after PEM snapshots |

`CodeConfiguration` and `UnitConfiguration` are first-class structures embedded in `pem_snapshots.snapshot_data`.

## Configuration

Set `DATABASE_URL` in `.env` (see root `.env.example`):

```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/structuralaiaagent
```

Optional test database:

```
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/structuralaiaagent_test
```

## Apply migrations (manual)

```bash
psql "$DATABASE_URL" -f database/migrations/001_bootstrap.sql
psql "$DATABASE_URL" -f database/migrations/002_pem_foundation.sql
```

Backend persistence tests apply migrations automatically when PostgreSQL is reachable.

## Verify schema

```bash
psql "$DATABASE_URL" -c "\dt"
psql "$DATABASE_URL" -c "\d pem_snapshots"
```
