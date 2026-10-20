"""Apply SQL migrations from database/migrations in order."""

from __future__ import annotations

from pathlib import Path

from app.infrastructure.database.connection import get_connection


def get_migrations_dir() -> Path:
    """Resolve repository database/migrations directory from backend cwd."""
    backend_root = Path(__file__).resolve().parents[3]
    repo_root = backend_root.parent
    migrations_dir = repo_root / "database" / "migrations"
    if not migrations_dir.is_dir():
        raise FileNotFoundError(f"Migrations directory not found: {migrations_dir}")
    return migrations_dir


TRACKING_TABLE = "schema_migrations"


def pending_migrations(all_files: list[str], already: set[str]) -> list[str]:
    """Migration file names still to apply, in lexical order."""
    return [name for name in sorted(all_files) if name not in already]


def apply_migrations(database_url: str | None = None) -> list[str]:
    """Apply *.sql migrations in lexical order, once each (tracked in schema_migrations).

    Each migration runs in its own transaction. On a database created before tracking existed, a migration
    whose objects already exist (duplicate table/object/column) is recorded as applied instead of failing.
    Returns the names applied (or adopted) in this call."""
    migrations_dir = get_migrations_dir()
    files = {p.name: p for p in migrations_dir.glob("*.sql")}
    applied: list[str] = []
    with get_connection(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE TABLE IF NOT EXISTS {TRACKING_TABLE} (filename TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
            )
            cur.execute(f"SELECT filename FROM {TRACKING_TABLE}")
            done = {(row["filename"] if isinstance(row, dict) else row[0]) for row in cur.fetchall()}
        conn.commit()
        for name in pending_migrations(list(files), done):
            sql = files[name].read_text(encoding="utf-8")
            try:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    cur.execute(f"INSERT INTO {TRACKING_TABLE} (filename) VALUES (%s)", (name,))
                conn.commit()
            except Exception as exc:  # noqa: BLE001 - adopt pre-existing schema objects only
                conn.rollback()
                code = getattr(exc, "sqlstate", None) or getattr(getattr(exc, "diag", None), "sqlstate", None)
                if code not in {"42P07", "42710", "42701", "42P06"}:  # duplicate table/object/column/schema
                    raise
                with conn.cursor() as cur:
                    cur.execute(f"INSERT INTO {TRACKING_TABLE} (filename) VALUES (%s) ON CONFLICT DO NOTHING", (name,))
                conn.commit()
            applied.append(name)
    return applied
