"""Unit tests for advanced prompt generation."""

from uuid import uuid4

from app.application.prompt_generation_service import PromptGenerationService
from app.application.service_factory import build_ai_gateway_service
from app.domain.models.agent import EngineeringAgentType


def _service() -> PromptGenerationService:
    return PromptGenerationService(ai_gateway=build_ai_gateway_service())


def _empty_context() -> dict:
    return {
        "project_id": str(uuid4()),
        "project_name": "Test Tower",
        "pem_version": None,
        "code_configuration": None,
        "unit_configuration": None,
        "memory_total_count": 0,
        "memory_counts_by_type": {},
        "memories": [],
        "files": [],
    }


def test_prompt_generation_routes_seismic_request() -> None:
    result = _service().generate(
        user_request="Prepare a seismic load assessment",
        context_summary=_empty_context(),
    )

    assert result.selected_agent_type == EngineeringAgentType.SEISMIC_AGENT
    assert "seismic" in result.user_intent.lower()
    assert result.execution_plan
    assert result.execution_plan[-1]["capability_kind"] == "deterministic_service"


def test_prompt_generation_detects_missing_code_and_units() -> None:
    result = _service().generate(
        user_request="Review this model and provide an execution drawing",
        context_summary=_empty_context(),
    )

    assert result.selected_agent_type == EngineeringAgentType.STRUCTURAL_MODELING_AGENT
    assert "Project code configuration" in result.missing_information
    assert "Project unit system" in result.missing_information
    assert "engineering_model" in result.context_requirements


def test_prompt_generation_preserves_approved_constraints() -> None:
    context = _empty_context()
    context["memories"] = [
        {
            "id": str(uuid4()),
            "memory_type": "DECISION",
            "content": "Use C30 concrete for all beams.",
        },
        {
            "id": str(uuid4()),
            "memory_type": "REQUIREMENT",
            "content": "Maintain 250 mm slab thickness.",
        },
    ]
    context["memory_total_count"] = 2

    result = _service().generate(
        user_request="Design the slab reinforcement",
        context_summary=context,
    )

    assert any("C30 concrete" in item for item in result.preserved_constraints)
    assert "Preserve approved constraints" in result.generated_prompt
    assert result.constraints.get("preserve_approved_decisions") is True


def test_prompt_generation_includes_execution_plan_and_services() -> None:
    context = _empty_context()
    context["code_configuration"] = {
        "jurisdiction": "IR",
        "governing_building_code": "M2800",
        "loading_standard": "M2800",
        "concrete_standard": "ABA",
        "steel_standard": "M3400",
    }
    context["unit_configuration"] = {
        "system": "metric",
        "length_unit": "m",
        "force_unit": "kN",
        "stress_unit": "MPa",
    }
    context["pem_version"] = 2

    result = _service().generate(
        user_request="Run drift analysis for the lateral system",
        context_summary=context,
    )

    assert result.selected_agent_type == EngineeringAgentType.ANALYSIS_AGENT
    assert "engineering.analysis.run" in result.deterministic_services
    assert any(step["capability"] == EngineeringAgentType.ANALYSIS_AGENT.value for step in result.execution_plan)
    assert result.metadata["routing_method"] == "keyword_and_context"
