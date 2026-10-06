"""Scored, word-boundary engineering intent routing."""

from __future__ import annotations

from app.application.agent_intent_routing import (
    keyword_matches,
    resolve_agent_intent,
    resolve_primary_agent_type,
    split_user_request_and_attachment_context,
)
from app.application.prompt_generation_service import PromptGenerationService
from app.application.service_factory import build_ai_gateway_service
from app.domain.models.agent import EngineeringAgentType


def _prompt(user_request: str, context: dict | None = None):
    return PromptGenerationService(ai_gateway=build_ai_gateway_service()).generate(
        user_request=user_request,
        context_summary=context
        or {
            "project_id": "00000000-0000-0000-0000-000000000001",
            "project_name": "Route Test",
            "pem_version": None,
            "code_configuration": None,
            "unit_configuration": None,
            "memory_total_count": 0,
            "memory_counts_by_type": {},
            "memories": [],
            "files": [],
        },
    )


def test_upload_does_not_match_load_keyword() -> None:
    assert not keyword_matches("load", "please upload the etabs model")
    agent_type, _ = resolve_primary_agent_type("Please upload the ETABS model")
    assert agent_type == EngineeringAgentType.STRUCTURAL_MODELING_AGENT


def test_analyze_model_for_drift_routes_to_analysis() -> None:
    agent_type, _ = resolve_primary_agent_type("Analyze this model for drift issues.")
    assert agent_type == EngineeringAgentType.ANALYSIS_AGENT


def test_seismic_analysis_prefers_seismic_over_generic_analysis() -> None:
    agent_type, _ = resolve_primary_agent_type("Run seismic analysis for this structure")
    assert agent_type == EngineeringAgentType.SEISMIC_AGENT


def test_seismic_load_assessment_still_routes_to_seismic() -> None:
    agent_type, _ = resolve_primary_agent_type("Prepare a seismic load assessment")
    assert agent_type == EngineeringAgentType.SEISMIC_AGENT


def test_loading_assumptions_route_to_load_assessment() -> None:
    agent_type, _ = resolve_primary_agent_type("Review the loading assumptions for occupancy")
    assert agent_type == EngineeringAgentType.LOAD_ASSESSMENT_AGENT


def test_rc_beam_with_dead_load_does_not_select_load_agent() -> None:
    agent_type, _ = resolve_primary_agent_type(
        "Analyze this reinforced concrete beam and determine the governing design checks. "
        "Dead load is 5 kPa."
    )
    assert agent_type != EngineeringAgentType.LOAD_ASSESSMENT_AGENT
    assert agent_type in {
        EngineeringAgentType.ANALYSIS_AGENT,
        EngineeringAgentType.CONCRETE_DESIGN_AGENT,
    }


def test_reinforcement_column_routes_to_concrete_not_steel() -> None:
    agent_type, _ = resolve_primary_agent_type(
        "Calculate the required reinforcement for this column."
    )
    assert agent_type == EngineeringAgentType.CONCRETE_DESIGN_AGENT


def test_attachment_load_text_does_not_override_analysis_intent() -> None:
    user_request = (
        "Analyze this reinforced concrete beam and determine the governing design checks.\n\n"
        "Attached files (engineering context):\n"
        "### loads.txt (TEXT, id=abc)\n"
        "Extracted content:\n"
        "dead load: 5 kPa\nlive load: 3 kPa\n"
    )
    intent = resolve_agent_intent(user_request)
    assert intent.agent_type != EngineeringAgentType.LOAD_ASSESSMENT_AGENT
    assert intent.agent_type in {
        EngineeringAgentType.ANALYSIS_AGENT,
        EngineeringAgentType.CONCRETE_DESIGN_AGENT,
    }


def test_split_keeps_user_text_separate_from_attachment_appendix() -> None:
    user_part, attachment_part = split_user_request_and_attachment_context(
        "Analyze drift.\n\nAttached files (engineering context):\ndead load: 5 kPa"
    )
    assert user_part == "Analyze drift."
    assert "dead load" in attachment_part


def test_empty_request_falls_back_to_validation() -> None:
    agent_type, label = resolve_primary_agent_type("hello")
    assert agent_type == EngineeringAgentType.VALIDATION_AGENT
    assert "readiness" in label.lower()


def test_prompt_generation_uses_scored_routing_for_chat_example() -> None:
    result = _prompt(
        "Analyze this reinforced concrete beam and determine the governing design checks."
    )
    assert result.selected_agent_type != EngineeringAgentType.LOAD_ASSESSMENT_AGENT
    assert result.metadata["routing_method"] == "scored_keyword_and_context"
    assert result.metadata["routing_score"] > 0


def test_prompt_generation_upload_model_is_not_load_assessment() -> None:
    result = _prompt("Please upload the ETABS model and update geometry.")
    assert result.selected_agent_type == EngineeringAgentType.STRUCTURAL_MODELING_AGENT


def test_extract_loads_from_file_routes_to_load_assessment() -> None:
    agent_type, _ = resolve_primary_agent_type("Extract loads from the attached file.")
    assert agent_type == EngineeringAgentType.LOAD_ASSESSMENT_AGENT
