"""Deterministic ACI 318 RC beam flexure + shear capability."""

from __future__ import annotations

import math

import pytest

from app.application.aci_rc_beam_check import (
    is_aci_rc_beam_check_request,
    parse_aci_rc_beam_inputs,
    run_aci_rc_beam_check,
)
from app.application.agent_intent_routing import resolve_primary_agent_type
from app.application.engineering_agent_handlers import ConcreteDesignAgentHandler, SteelDesignAgentHandler
from app.application.service_factory import build_code_engine_service, build_unit_conversion_service
from app.application.unit_conversion_service import UnitConversionService
from app.domain.models.agent import EngineeringAgentType
from app.domain.models.pem import (
    StandardReference,
    create_software_default_code_configuration,
)
from app.domain.models.units import EngineeringQuantityType


COMPLETE_REQUEST = (
    "Check this RC beam per ACI 318: span 6 m, 20 kN/m, "
    "b=300 mm, h=500 mm, d=450 mm, fc=25 MPa, fy=400 MPa, As=1500 mm2."
)

# Independent Whitney flexure in SI (kN·m): φMn = 0.9 · As · fy · (d − a/2)
_AS_M2 = 1500e-6
_FY_PA = 400e6
_FC_PA = 25e6
_B_M = 0.3
_D_M = 0.45
_A_M = (_AS_M2 * _FY_PA) / (0.85 * _FC_PA * _B_M)
_PHI_MN_KN_M = 0.9 * _AS_M2 * _FY_PA * (_D_M - _A_M / 2.0) / 1000.0


def _code_engine():
    return build_code_engine_service()


def _context(code=None) -> dict:
    config = code or create_software_default_code_configuration()
    return {
        "project_id": "00000000-0000-0000-0000-000000000001",
        "project_name": "ACI Check",
        "code_configuration": config.model_dump(mode="json"),
        "files": [],
    }


def test_detector_requires_design_and_beam() -> None:
    assert is_aci_rc_beam_check_request("Design this beam.")
    assert is_aci_rc_beam_check_request(COMPLETE_REQUEST)
    assert not is_aci_rc_beam_check_request(
        "Analyze a simply supported reinforced concrete beam with a 6 m span and uniform load of 20 kN/m."
    )
    assert not is_aci_rc_beam_check_request("Calculate the required reinforcement for this column.")
    assert not is_aci_rc_beam_check_request("Design this steel beam.")


def test_design_this_beam_routes_to_concrete() -> None:
    agent_type, _ = resolve_primary_agent_type("Design this beam.")
    assert agent_type == EngineeringAgentType.CONCRETE_DESIGN_AGENT


def test_aci_prompt_routes_to_concrete() -> None:
    agent_type, _ = resolve_primary_agent_type(COMPLETE_REQUEST)
    assert agent_type == EngineeringAgentType.CONCRETE_DESIGN_AGENT


def test_missing_inputs_are_listed_and_not_invented() -> None:
    outcome = run_aci_rc_beam_check(
        user_request="Design this beam.",
        parameters={},
        context=_context(),
        code_engine=_code_engine(),
    )
    assert outcome is not None
    assert outcome.status == "MISSING_REQUIRED_INPUT"
    assert outcome.requires_approval is False
    assert "Width b" in outcome.payload["missing"]
    assert "Tension reinforcement area As" in outcome.payload["missing"]
    assert outcome.payload["results"] == {}


def test_invalid_range_is_rejected() -> None:
    outcome = run_aci_rc_beam_check(
        user_request="Check this RC beam b=10 mm h=500 mm d=450 mm fc=25 MPa fy=400 MPa As=1500 Mu=90 Vu=60",
        parameters={},
        context=_context(),
        code_engine=_code_engine(),
    )
    assert outcome is not None
    assert outcome.status == "INVALID_INPUT"
    assert outcome.requires_approval is False
    assert any("Width" in item for item in outcome.payload["warnings"])


def test_effective_depth_must_be_less_than_height() -> None:
    outcome = run_aci_rc_beam_check(
        user_request="Check this RC beam b=300 mm h=400 mm d=450 mm fc=25 MPa fy=400 MPa As=1500 Mu=90 Vu=60",
        parameters={},
        context=_context(),
        code_engine=_code_engine(),
    )
    assert outcome is not None
    assert outcome.status == "INVALID_INPUT"


def test_unsupported_eurocode_is_not_pretended() -> None:
    config = create_software_default_code_configuration()
    config.concrete_standard = StandardReference(
        family="EC2",
        edition="EN 1992-1-1",
        full_designation="Eurocode 2",
    )
    config.concrete_edition = "EN 1992-1-1"
    outcome = run_aci_rc_beam_check(
        user_request=COMPLETE_REQUEST,
        parameters={},
        context=_context(config),
        code_engine=_code_engine(),
    )
    assert outcome is not None
    assert outcome.status == "UNSUPPORTED_CODE"
    assert outcome.requires_approval is False
    assert "ACI CODE-318-25" in outcome.message


def test_aci_318_19_is_unsupported() -> None:
    config = create_software_default_code_configuration()
    config.concrete_standard = StandardReference(
        family="ACI 318",
        edition="ACI 318-19",
        full_designation="ACI 318-19",
    )
    config.concrete_edition = "ACI 318-19"
    outcome = run_aci_rc_beam_check(
        user_request=COMPLETE_REQUEST,
        parameters={},
        context=_context(config),
        code_engine=_code_engine(),
    )
    assert outcome is not None
    assert outcome.status == "UNSUPPORTED_CODE"


def test_hand_verifiable_whitney_flexure_and_aci_shear() -> None:
    units = UnitConversionService()
    outcome = run_aci_rc_beam_check(
        user_request=COMPLETE_REQUEST,
        parameters={},
        context=_context(),
        code_engine=_code_engine(),
        units=units,
    )
    assert outcome is not None
    assert outcome.status == "PASS"
    assert outcome.requires_approval is True
    results = outcome.payload["results"]
    assert results["phi_mn_kn_m"] == pytest.approx(_PHI_MN_KN_M, rel=1e-3)
    assert results["flexure_outcome"] == "PASS"
    assert results["shear_outcome"] == "PASS"
    assert outcome.payload["demands"]["mu_kn_m"] == pytest.approx(90.0, rel=1e-6)
    assert outcome.payload["demands"]["vu_kn"] == pytest.approx(60.0, rel=1e-6)
    assert results["flexure_utilization"] == pytest.approx(90.0 / results["phi_mn_kn_m"], rel=1e-3)
    assert results["flexure_utilization"] < 1.0

    width_in = units.convert(300.0, from_unit="mm", to_unit="in", quantity_type=EngineeringQuantityType.LENGTH).value
    d_in = units.convert(450.0, from_unit="mm", to_unit="in", quantity_type=EngineeringQuantityType.LENGTH).value
    fc_psi = units.convert(25.0, from_unit="MPa", to_unit="psi", quantity_type=EngineeringQuantityType.STRESS).value
    expected_phi_vc_kip = 0.75 * 2.0 * math.sqrt(fc_psi) * width_in * d_in / 1000.0
    expected_phi_vc_kn = units.convert(
        expected_phi_vc_kip, from_unit="kip", to_unit="kN", quantity_type=EngineeringQuantityType.FORCE
    ).value
    assert results["phi_vc_kn"] == pytest.approx(expected_phi_vc_kn, rel=1e-3)
    assert results["shear_utilization"] == pytest.approx(60.0 / results["phi_vc_kn"], rel=1e-3)


def test_explicit_demands_do_not_use_udl_formulas() -> None:
    outcome = run_aci_rc_beam_check(
        user_request=(
            "Check this RC beam b=300 mm h=500 mm d=450 mm fc=25 MPa fy=400 MPa "
            "As=1500 mm2 Mu=120 kN·m Vu=80 kN"
        ),
        parameters={},
        context=_context(),
        code_engine=_code_engine(),
    )
    assert outcome is not None
    assert outcome.payload["demand_source"] == "user_supplied"
    assert outcome.payload["demands"]["mu_kn_m"] == pytest.approx(120.0, rel=1e-3)
    assert outcome.payload["demands"]["vu_kn"] == pytest.approx(80.0, rel=1e-3)


def test_overutilized_flexure_fails() -> None:
    outcome = run_aci_rc_beam_check(
        user_request=(
            "Check this RC beam b=300 mm h=500 mm d=450 mm fc=25 MPa fy=400 MPa "
            "As=1500 mm2 Mu=400 kN·m Vu=10 kN"
        ),
        parameters={},
        context=_context(),
        code_engine=_code_engine(),
    )
    assert outcome is not None
    assert outcome.status == "FAIL"
    assert outcome.payload["results"]["flexure_outcome"] == "FAIL"
    assert outcome.payload["results"]["shear_outcome"] == "PASS"


def test_unit_tables_include_mm_and_mm2() -> None:
    units = build_unit_conversion_service()
    length = units.convert(300.0, from_unit="mm", to_unit="in", quantity_type=EngineeringQuantityType.LENGTH)
    area = units.convert(1500.0, from_unit="mm2", to_unit="in2", quantity_type=EngineeringQuantityType.AREA)
    assert length.value == pytest.approx(11.811023622, rel=1e-6)
    assert area.value == pytest.approx(2.325003875, rel=1e-6)


def test_parameters_override_text_parsing() -> None:
    parsed = parse_aci_rc_beam_inputs(
        "Check this RC beam",
        {
            "width_mm": 300,
            "height_mm": 500,
            "effective_depth_mm": 450,
            "fc_mpa": 25,
            "fy_mpa": 400,
            "as_mm2": 1500,
            "mu_kn_m": 90,
            "vu_kn": 60,
        },
    )
    assert parsed.width_mm == 300
    assert parsed.as_mm2 == 1500
    assert parsed.mu_kn_m == 90


class _UnavailableDesign:
    def run_design(self, *args, **kwargs):
        raise AssertionError("ACI path must not call the CSI design engine")


class _AciServices:
    design_engine = _UnavailableDesign()
    code_engine = build_code_engine_service()


def test_concrete_handler_runs_aci_check_without_csi() -> None:
    handler = ConcreteDesignAgentHandler(services=_AciServices())  # type: ignore[arg-type]
    result = handler.execute(
        user_request=COMPLETE_REQUEST,
        parameters={},
        context=_context(),
    )
    assert result.structured_output["aci_rc_beam"]["kind"] == "aci_rc_beam"
    assert result.structured_output["capability_status"] == "PASS"
    assert result.validation_information["requires_approval"] is True


def test_concrete_handler_missing_inputs_skip_approval() -> None:
    handler = ConcreteDesignAgentHandler(services=_AciServices())  # type: ignore[arg-type]
    result = handler.execute(
        user_request="Design this beam.",
        parameters={},
        context=_context(),
    )
    assert result.structured_output["capability_status"] == "MISSING_REQUIRED_INPUT"
    assert result.validation_information["requires_approval"] is False
    assert "I will not invent" in result.structured_output["status_message"]


def test_steel_handler_redirects_only_for_explicit_concrete() -> None:
    handler = SteelDesignAgentHandler(services=_AciServices())  # type: ignore[arg-type]
    result = handler.execute(
        user_request="Check this RC beam per ACI 318: b=300 mm h=500 mm d=450 mm fc=25 fy=400 As=1500 Mu=90 Vu=60",
        parameters={},
        context=_context(),
    )
    assert result.structured_output.get("aci_rc_beam")
