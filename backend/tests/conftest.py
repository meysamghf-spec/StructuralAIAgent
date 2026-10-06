"""Shared pytest fixtures for PostgreSQL-backed persistence tests."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import psycopg
import pytest
from psycopg import sql

from app.application.service_factory import build_project_service, reset_test_service_caches
from app.application.project_service import ProjectService
from app.infrastructure.config import get_settings
from app.infrastructure.database.connection import DatabaseConnectionError, check_connection, get_connection
from app.infrastructure.database.migrations import apply_migrations


def _derived_test_database_url(resolved_database_url: str) -> str:
    """Use a dedicated *_test database so pytest TRUNCATE never wipes dev accounts."""
    parsed = urlparse(resolved_database_url)
    db_name = (parsed.path or "/structuralaiaagent").lstrip("/") or "structuralaiaagent"
    if db_name.endswith("_test"):
        return resolved_database_url
    return urlunparse(parsed._replace(path=f"/{db_name}_test"))


def _resolve_test_database_url() -> str:
    get_settings.cache_clear()
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit
    settings = get_settings()
    if settings.test_database_url:
        return settings.test_database_url
    return _derived_test_database_url(settings.resolved_database_url)


def _ensure_database_exists(database_url: str) -> None:
    try:
        check_connection(database_url)
        return
    except DatabaseConnectionError:
        pass

    parsed = urlparse(database_url)
    db_name = (parsed.path or "").lstrip("/")
    if not db_name:
        raise DatabaseConnectionError("Test database URL must include a database name")

    admin_url = urlunparse(parsed._replace(path="/postgres"))
    try:
        with psycopg.connect(admin_url, autocommit=True, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL("SELECT 1 FROM pg_database WHERE datname = {}").format(sql.Literal(db_name))
                )
                if cur.fetchone() is None:
                    cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
    except Exception as exc:  # noqa: BLE001 — surface as domain-specific error
        raise DatabaseConnectionError(f"Unable to ensure test database exists: {exc}") from exc

    check_connection(database_url)


def _truncate_public_tables(database_url: str) -> None:
    with get_connection(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                  AND tablename <> 'schema_migrations'
                ORDER BY tablename
                """
            )
            rows = cur.fetchall()
            table_names = [
                row["tablename"] if isinstance(row, dict) else row[0]
                for row in rows
            ]
            if not table_names:
                return
            cur.execute(
                sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY CASCADE").format(
                    sql.SQL(", ").join(sql.Identifier(name) for name in table_names)
                )
            )


@pytest.fixture(scope="session")
def test_database_url() -> str:
    return _resolve_test_database_url()


@pytest.fixture(scope="session")
def database_ready(test_database_url: str) -> str:
    try:
        _ensure_database_exists(test_database_url)
    except DatabaseConnectionError as exc:
        pytest.skip(f"PostgreSQL unavailable for persistence tests: {exc}")
    apply_migrations(test_database_url)
    return test_database_url


@pytest.fixture
def db_session(database_ready: str, monkeypatch: pytest.MonkeyPatch) -> Generator[str, None, None]:
    """Isolate each persistence test with a clean database."""
    monkeypatch.setenv("DATABASE_URL", database_ready)
    monkeypatch.setenv("TEST_DATABASE_URL", database_ready)
    reset_test_service_caches()
    _truncate_public_tables(database_ready)
    yield database_ready


@pytest.fixture
def project_service(db_session: str) -> ProjectService:
    return build_project_service()


@pytest.fixture
def api_client(db_session: str, tmp_path, monkeypatch: pytest.MonkeyPatch) -> Generator:
    storage_root = tmp_path / "file_storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("FILE_STORAGE_ROOT", str(storage_root))
    get_settings.cache_clear()

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture
def file_storage_root(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Path:
    storage_root = tmp_path / "file_storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("FILE_STORAGE_ROOT", str(storage_root))
    get_settings.cache_clear()
    return storage_root
