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


def apply_migrations(database_url: str | None = None) -> list[str]:
    """Apply all *.sql migrations in lexical order. Returns applied file names."""
    migrations_dir = get_migrations_dir()
    applied: list[str] = []
    migration_files = sorted(migrations_dir.glob("*.sql"))

    with get_connection(database_url) as conn:
        with conn.cursor() as cur:
            for migration_file in migration_files:
                sql = migration_file.read_text(encoding="utf-8")
                cur.execute(sql)
                applied.append(migration_file.name)
    return applied
