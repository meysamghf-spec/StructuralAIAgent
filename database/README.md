# Database Migrations

PostgreSQL is the primary database (AG-34).

## Structure

- `migrations/` — ordered SQL migration files
- Migrations are applied manually or via a future migration runner in Milestone 2+

## Milestone 1

`001_bootstrap.sql` creates only the `schema_migrations` tracking table.

The approved Phase 1 production schema will be implemented in subsequent milestones.

## Configuration

Set `DATABASE_URL` in `.env` (see root `.env.example`):

```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/engineering_ai_platform
```

## Apply bootstrap migration (manual)

```bash
psql "$DATABASE_URL" -f database/migrations/001_bootstrap.sql
```
