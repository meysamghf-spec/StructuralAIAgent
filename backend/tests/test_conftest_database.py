import pytest

from app.application.service_factory import build_project_service, reset_test_service_caches
from tests.conftest import _derived_test_database_url, _truncate_public_tables


def test_derived_test_database_url_uses_suffixed_database() -> None:
    derived = _derived_test_database_url("postgresql://postgres@127.0.0.1:5432/structuralaiaagent")
    assert derived.endswith("/structuralaiaagent_test")


def test_derived_test_database_url_preserves_existing_test_database() -> None:
    original = "postgresql://postgres@127.0.0.1:5432/structuralaiaagent_test"
    assert _derived_test_database_url(original) == original


def test_db_session_truncates_between_tests(db_session: str) -> None:
    first = build_project_service().create_project("Isolation Project A").project
    assert first.id is not None


def test_db_session_does_not_leak_prior_project(db_session: str) -> None:
    projects = build_project_service().list_projects()
    assert projects == []


def test_reset_service_caches_clears_singletons(db_session: str) -> None:
    from app.application.service_factory import build_human_approval_service

    first = build_human_approval_service()
    reset_test_service_caches()
    second = build_human_approval_service()
    assert first is not second
