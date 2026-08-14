"""PostgreSQL connection management — credentials from environment only."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row

from app.infrastructure.config import get_settings


class DatabaseConnectionError(Exception):
    """Raised when the database is unreachable or misconfigured."""


def check_connection(database_url: str | None = None) -> None:
    """Verify PostgreSQL connectivity; raise DatabaseConnectionError on failure."""
    url = database_url or get_settings().resolved_database_url
    try:
        with psycopg.connect(url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
    except Exception as exc:  # noqa: BLE001 — surface as domain-specific error
        raise DatabaseConnectionError(f"Unable to connect to PostgreSQL: {exc}") from exc


@contextmanager
def get_connection(database_url: str | None = None) -> Generator[psycopg.Connection[Any], None, None]:
    """Yield a PostgreSQL connection using dict rows."""
    url = database_url or get_settings().resolved_database_url
    conn = psycopg.connect(url, row_factory=dict_row)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
