"""CodeEngine and CompatibilityEngine tests."""

from app.application.compatibility_engine import CompatibilityEngine
from app.application.service_factory import build_code_engine_service
from app.domain.models.pem import (
    CompatibilityStatus,
    create_software_default_code_configuration,
)


def test_list_us_default_standards() -> None:
    service = build_code_engine_service()
    standards = service.list_available_standards()
    plugin_ids = {item.plugin_id for item in standards}
    assert plugin_ids == {"ACI318-25", "AISC360-22", "ASCE7-22", "IBC-2024"}


def test_get_us_code_defaults() -> None:
    from app.domain.models.pem import Jurisdiction

    service = build_code_engine_service()
    defaults = service.get_defaults(Jurisdiction.US)
    config = defaults.configuration
    assert config.governing_building_code.edition == "IBC 2024"
    assert config.loading_standard.edition == "ASCE 7-22"
    assert config.concrete_standard.edition == "ACI CODE-318-25"
    assert config.steel_standard.edition == "AISC 360-22"


def test_validate_default_configuration_is_valid() -> None:
    service = build_code_engine_service()
    config = create_software_default_code_configuration()
    result = service.validate_configuration(config)
    assert result.is_valid is True
    assert not any(conflict.severity == "ERROR" for conflict in result.conflicts)


def test_detect_marked_conflict() -> None:
    engine = CompatibilityEngine()
    config = create_software_default_code_configuration()
    config.compatibility_status = CompatibilityStatus.CONFLICT
    conflicts = engine.detect_conflicts(config)
    assert any(item.conflict_type == "MARKED_CONFLICT" for item in conflicts)


def test_run_stub_check_returns_not_applicable() -> None:
    service = build_code_engine_service()
    config = create_software_default_code_configuration()
    result = service.run_check(
        "AISC360-22",
        "flexural_strength",
        {"moment_kip_ft": 100.0},
        code_configuration=config,
    )
    assert result.outcome.value == "NOT_APPLICABLE"
    assert result.code_family == "AISC 360"


def test_default_jurisdiction_is_iran() -> None:
    from app.domain.models.pem import Jurisdiction

    config = build_code_engine_service().get_defaults().configuration
    assert config.jurisdiction == Jurisdiction.IRAN
    assert "Mabhas 9" in config.concrete_standard.edition
