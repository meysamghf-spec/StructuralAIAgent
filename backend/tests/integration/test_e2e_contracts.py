"""Migration integrity and workflow contract verification."""

from __future__ import annotations

from app.application.service_factory import build_design_engine_service
from app.domain.models.design import DesignRequest
from app.infrastructure.database.migrations import get_migrations_dir
from tests.integration.helpers import create_project, populate_standard_pem


def test_migration_017_foreign_keys_and_indexes() -> None:
    sql = (get_migrations_dir() / "017_crypto_payment_foundation.sql").read_text(encoding="utf-8")
    assert "REFERENCES crypto_payments(id)" in sql
    assert "idx_crypto_payments_tx_network" in sql
    assert "idx_upgrade_entitlements_active_product" in sql
    assert "payment_audit_events" in sql


def test_migration_order_includes_all_foundation_files() -> None:
    files = sorted(path.name for path in get_migrations_dir().glob("*.sql"))
    assert files[-1] == "017_crypto_payment_foundation.sql"
    assert "001_bootstrap.sql" in files


def test_deterministic_design_repeatability(db_session) -> None:
    project = create_project("Determinism")
    populate_standard_pem(project.id)
    service = build_design_engine_service()
    first = service.run_design(
        DesignRequest(project_id=project.id, design_type="CONCRETE_BEAM"),
    )
    second = service.run_design(
        DesignRequest(project_id=project.id, design_type="CONCRETE_BEAM"),
    )
    assert first.status == second.status
    assert first.capability_status == second.capability_status


def test_project_pem_version_preserved_on_design_run(db_session) -> None:
    project = create_project("PEM version contract")
    version, _ = populate_standard_pem(project.id)
    run = build_design_engine_service().run_design(
        DesignRequest(project_id=project.id, design_type="CONCRETE_BEAM"),
    )
    assert run.pem_version == version
