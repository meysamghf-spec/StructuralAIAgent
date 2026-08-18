"""Shared pytest fixtures for PostgreSQL-backed persistence tests."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

import pytest

from app.application.service_factory import build_project_service
from app.application.project_service import ProjectService
from app.infrastructure.config import get_settings
from app.infrastructure.database.connection import DatabaseConnectionError, check_connection, get_connection
from app.infrastructure.database.migrations import apply_migrations


def _resolve_test_database_url() -> str:
    get_settings.cache_clear()
    return os.environ.get("TEST_DATABASE_URL") or get_settings().effective_test_database_url


@pytest.fixture(scope="session")
def test_database_url() -> str:
    return _resolve_test_database_url()


@pytest.fixture(scope="session")
def database_ready(test_database_url: str) -> str:
    try:
        check_connection(test_database_url)
    except DatabaseConnectionError as exc:
        pytest.skip(f"PostgreSQL unavailable for persistence tests: {exc}")
    apply_migrations(test_database_url)
    return test_database_url


@pytest.fixture
def db_session(database_ready: str, monkeypatch: pytest.MonkeyPatch) -> Generator[str, None, None]:
    """Isolate each persistence test with a clean database."""
    monkeypatch.setenv("DATABASE_URL", database_ready)
    get_settings.cache_clear()

    with get_connection(database_ready) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                TRUNCATE TABLE
                    project_files,
                    prompt_templates,
                    agent_version_capabilities,
                    agent_versions,
                    agent_capabilities,
                    agent_definitions,
                    revisions,
                    pem_snapshots,
                    projects
                RESTART IDENTITY CASCADE
                """
            )
    yield database_ready


@pytest.fixture
def project_service(db_session: str) -> ProjectService:
    return build_project_service()


@pytest.fixture
def api_client(db_session: str, tmp_path, monkeypatch: pytest.MonkeyPatch) -> Generator:
    storage_root = tmp_path / "file_storage"
    storage_root.mkdir()
    monkeypatch.setenv("FILE_STORAGE_ROOT", str(storage_root))
    get_settings.cache_clear()

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture
def file_storage_root(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Path:
    storage_root = tmp_path / "file_storage"
    storage_root.mkdir()
    monkeypatch.setenv("FILE_STORAGE_ROOT", str(storage_root))
    get_settings.cache_clear()
    return storage_root
