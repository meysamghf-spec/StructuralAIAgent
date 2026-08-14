"""Apply migrations and print schema verification (no secrets)."""

from __future__ import annotations

import json
import sys

from app.infrastructure.config import get_settings
from app.infrastructure.database.connection import check_connection, get_connection
from app.infrastructure.database.migrations import apply_migrations


def main() -> int:
    get_settings.cache_clear()
    settings = get_settings()
    url = settings.resolved_database_url

    try:
        check_connection(url)
    except Exception as exc:
        print(f"Connection failed: {exc}", file=sys.stderr)
        return 1

    applied = apply_migrations(url)
    print("Migrations applied:", applied)

    with get_connection(url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
                """
            )
            tables = [row["table_name"] for row in cur.fetchall()]
            print("Public tables:", json.dumps(tables))

            cur.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'pem_snapshots'
                ORDER BY ordinal_position
                """
            )
            pem_columns = {row["column_name"]: row["data_type"] for row in cur.fetchall()}
            print("pem_snapshots columns:", json.dumps(pem_columns))

            cur.execute("SELECT version, name FROM schema_migrations ORDER BY version")
            migrations = [dict(row) for row in cur.fetchall()]
            print("schema_migrations:", json.dumps(migrations))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
