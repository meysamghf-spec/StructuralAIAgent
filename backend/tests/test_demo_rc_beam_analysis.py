"""Unit tests for deterministic RC beam Demo analysis."""

from app.application.demo_rc_beam_analysis import (
    DEMO_DISCLAIMER,
    analyze_simply_supported_rc_beam,
    is_demo_rc_beam_request,
)
from app.application.agent_intent_routing import resolve_primary_agent_type
from app.application.engineering_agent_handlers import AnalysisAgentHandler, ConcreteDesignAgentHandler
from app.domain.models.agent import EngineeringAgentType


def test_default_demo_beam_moment_and_shear() -> None:
    result = analyze_simply_supported_rc_beam(
        "Analyze a simply supported reinforced concrete beam with a 6 m span and uniform load of 20 kN/m."
    )
    assert result is not None
    assert result.max_moment_kn_m == 90.0
    assert result.max_shear_kn == 60.0
    assert result.moment_formula == "M = wL²/8"
    assert DEMO_DISCLAIMER in result.to_markdown()
    payload = result.to_dict()
    assert payload["demo"] is True
    assert payload["kind"] == "demo_rc_beam"


def test_non_beam_request_is_not_demo() -> None:
    assert not is_demo_rc_beam_request("Create a new project named Tower A")
    assert analyze_simply_supported_rc_beam("What is the weather?") is None


def test_demo_prompt_routes_to_analysis_or_concrete() -> None:
    agent_type, _ = resolve_primary_agent_type(
        "Analyze a simply supported reinforced concrete beam with a 6 m span and uniform load of 20 kN/m."
    )
    assert agent_type in {
        EngineeringAgentType.ANALYSIS_AGENT,
        EngineeringAgentType.CONCRETE_DESIGN_AGENT,
    }


class _UnavailableAnalysis:
    def run_analysis(self, *args, **kwargs):
        raise AssertionError("Demo path must not call the CSI analysis engine")


class _UnavailableDesign:
    def run_design(self, *args, **kwargs):
        raise AssertionError("Demo path must not call the design engine")


class _DemoServices:
    analysis_engine = _UnavailableAnalysis()
    design_engine = _UnavailableDesign()


def test_analysis_handler_uses_demo_path_without_solver() -> None:
    handler = AnalysisAgentHandler(services=_DemoServices())  # type: ignore[arg-type]
    result = handler.execute(
        user_request="Analyze a simply supported RC beam span 6 m uniform load 20 kN/m",
        parameters={},
        context={"project_id": "00000000-0000-0000-0000-000000000001", "project_name": "Demo"},
    )
    assert result.structured_output["capability_status"] == "DEMO_COMPLETED"
    assert result.structured_output["demo_rc_beam"]["results"]["max_moment_kn_m"] == 90.0


def test_concrete_handler_uses_demo_path_without_design_engine() -> None:
    handler = ConcreteDesignAgentHandler(services=_DemoServices())  # type: ignore[arg-type]
    result = handler.execute(
        user_request="Analyze a simply supported reinforced concrete beam with a 6 m span and uniform load of 20 kN/m.",
        parameters={},
        context={"project_id": "00000000-0000-0000-0000-000000000001"},
    )
    assert result.structured_output["demo_rc_beam"]["results"]["max_shear_kn"] == 60.0
