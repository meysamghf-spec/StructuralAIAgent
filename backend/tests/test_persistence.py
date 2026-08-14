from uuid import uuid4

import pytest

from app.application.service_factory import build_pem_service, build_project_service
from app.domain.models.pem import (
    CodeConfigurationStatus,
    Jurisdiction,
    ProfileType,
    UnitSystem,
    create_software_default_code_configuration,
    create_us_customary_unit_configuration,
)
from app.domain.models.revision import RevisionChangeType
from app.infrastructure.database.connection import check_connection
from app.infrastructure.repositories.postgres_pem_repository import PostgresPemRepository
from app.infrastructure.repositories.postgres_revision_repository import PostgresRevisionRepository


def test_database_connection(db_session: str) -> None:
    check_connection(db_session)


def test_project_creation_persists_project_and_initial_pem(project_service) -> None:
    result = project_service.create_project("Tower A", description="Test tower")

    assert result.project.name == "Tower A"
    assert result.project.description == "Test tower"
    assert result.snapshot_version == 1
    assert result.revision.revision_number == 1
    assert result.revision.change_type == RevisionChangeType.INITIAL

    loaded = project_service.get_project(result.project.id)
    assert loaded is not None
    assert loaded.id == result.project.id


def test_pem_snapshot_persistence_is_versioned(project_service) -> None:
    bootstrap = project_service.create_project("Versioned Project")
    pem_service = build_pem_service()
    pem_repo = PostgresPemRepository()

    pem_v2 = pem_service.get_current_pem(bootstrap.project.id)
    assert pem_v2 is not None
    pem_v2.metadata.description = "Updated description"
    snapshot_id, version = pem_service.save_new_version(bootstrap.project.id, pem_v2)

    assert version == 2
    assert snapshot_id is not None

    current = pem_repo.get_current(bootstrap.project.id)
    assert current is not None
    assert current.metadata.description == "Updated description"

    historical = pem_repo.get_snapshot_by_version(bootstrap.project.id, 1)
    assert historical is not None
    assert historical.metadata.description != "Updated description"

    versions = pem_repo.list_versions(bootstrap.project.id)
    assert versions == [1, 2]


def test_revision_creation_links_snapshots(project_service) -> None:
    bootstrap = project_service.create_project("Revision Project")
    pem_repo = PostgresPemRepository()
    revision_repo = PostgresRevisionRepository()

    before_id = bootstrap.snapshot_id
    pem_v2 = pem_repo.get_current(bootstrap.project.id)
    assert pem_v2 is not None
    pem_v2.metadata.description = "Revision 2"
    after_id, version = pem_repo.save_snapshot(bootstrap.project.id, pem_v2)
    assert version == 2

    revision = revision_repo.create(
        bootstrap.project.id,
        RevisionChangeType.PEM_UPDATE,
        "Manual revision for test",
        after_snapshot_id=after_id,
        before_snapshot_id=before_id,
        created_by="test-engineer",
    )

    revisions = revision_repo.list_for_project(bootstrap.project.id)
    assert any(item.id == revision.id for item in revisions)
    assert revision.before_snapshot_id == before_id
    assert revision.after_snapshot_id == after_id
    assert revision.revision_number == 2


def test_code_configuration_persisted_in_pem_snapshot(project_service) -> None:
    result = project_service.create_project("Code Config Project")
    pem = result.pem

    code = pem.code_configuration
    assert code.profile_type == ProfileType.SOFTWARE_DEFAULT
    assert code.jurisdiction == Jurisdiction.US
    assert code.governing_building_code.edition == "IBC 2024"
    assert code.loading_standard.edition == "ASCE 7-22"
    assert code.concrete_standard.edition == "ACI CODE-318-25"
    assert code.steel_standard.edition == "AISC 360-22"
    assert code.status == CodeConfigurationStatus.SOFTWARE_DEFAULT

    reloaded = build_pem_service().get_current_pem(result.project.id)
    assert reloaded is not None
    assert (
        reloaded.code_configuration.governing_building_code.edition
        == "IBC 2024"
    )


def test_unit_configuration_persisted_in_pem_snapshot(project_service) -> None:
    result = project_service.create_project("Unit Config Project")
    units = result.pem.unit_configuration

    assert units.system == UnitSystem.US_CUSTOMARY
    assert units.length_unit == "ft"
    assert units.force_unit == "kip"
    assert units.stress_unit == "ksi"

    reloaded = build_pem_service().get_current_pem(result.project.id)
    assert reloaded is not None
    assert reloaded.unit_configuration.system == UnitSystem.US_CUSTOMARY


def test_project_isolation(project_service) -> None:
    project_a = project_service.create_project("Project A")
    project_b = project_service.create_project("Project B")

    pem_service = build_pem_service()
    pem_a = pem_service.get_current_pem(project_a.project.id)
    pem_b = pem_service.get_current_pem(project_b.project.id)

    assert pem_a is not None
    assert pem_b is not None
    assert pem_a.project_id == project_a.project.id
    assert pem_b.project_id == project_b.project.id
    assert pem_a.project_id != pem_b.project_id

    pem_a.metadata.name = "Mutated A"
    pem_service.save_new_version(project_a.project.id, pem_a)

    reloaded_b = pem_service.get_current_pem(project_b.project.id)
    assert reloaded_b is not None
    assert reloaded_b.metadata.name == "Project B"


def test_software_default_factories() -> None:
    code = create_software_default_code_configuration()
    units = create_us_customary_unit_configuration()

    assert code.governing_code_edition == "2024"
    assert code.loading_edition == "ASCE 7-22"
    assert units.length_unit == "ft"


def test_get_current_pem_returns_none_for_unknown_project(db_session: str) -> None:
    pem_service = build_pem_service()
    assert pem_service.get_current_pem(uuid4()) is None
