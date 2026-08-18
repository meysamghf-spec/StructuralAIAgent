"""Prompt generation for agent selection — routes through AI Gateway."""

from __future__ import annotations

from app.application.ai_gateway_service import AIGatewayService
from app.domain.models.agent import EngineeringAgentType
from app.domain.models.agent_runtime import PromptGenerationResult
from app.domain.models.ai_gateway import AIMessage, AIMessageRole, AICompletionRequest

_DEFAULT_MODEL = "stub-engineering-router"

_KEYWORD_ROUTING: list[tuple[tuple[str, ...], EngineeringAgentType]] = [
    (("model", "geometry", "structural model"), EngineeringAgentType.STRUCTURAL_MODELING_AGENT),
    (("seismic", "earthquake", "spectral"), EngineeringAgentType.SEISMIC_AGENT),
    (("load", "loading", "dead load", "live load"), EngineeringAgentType.LOAD_ASSESSMENT_AGENT),
    (("analyze", "analysis", "modal", "drift"), EngineeringAgentType.ANALYSIS_AGENT),
    (("concrete", "rebar", "slab"), EngineeringAgentType.CONCRETE_DESIGN_AGENT),
    (("steel", "beam", "column", "connection"), EngineeringAgentType.STEEL_DESIGN_AGENT),
    (("validate", "validation", "code check"), EngineeringAgentType.VALIDATION_AGENT),
    (("cad", "drawing", "autocad", "dxf"), EngineeringAgentType.CAD_AGENT),
    (("report", "summary", "deliverable"), EngineeringAgentType.REPORTING_AGENT),
    (("document", "spec", "interpret", "pdf"), EngineeringAgentType.DOCUMENT_INTERPRETATION_AGENT),
]


class PromptGenerationService:
    def __init__(self, *, ai_gateway: AIGatewayService) -> None:
        self._ai_gateway = ai_gateway

    def generate(
        self,
        *,
        user_request: str,
        context_summary: dict,
    ) -> PromptGenerationResult:
        selected_type = self._select_agent_type(user_request)
        gateway_response = self._ai_gateway.complete(
            AICompletionRequest(
                model=_DEFAULT_MODEL,
                messages=[
                    AIMessage(
                        role=AIMessageRole.SYSTEM,
                        content=(
                            "You are a prompt generation agent for structural engineering workflows. "
                            "Produce concise execution prompts without performing engineering calculations."
                        ),
                    ),
                    AIMessage(
                        role=AIMessageRole.USER,
                        content=(
                            f"User request: {user_request}\n"
                            f"Selected agent type: {selected_type.value}\n"
                            f"Context summary: {context_summary}"
                        ),
                    ),
                ],
                context={"phase": "prompt_generation"},
                metadata={"agent_type": EngineeringAgentType.PROMPT_GENERATION_AGENT.value},
            )
        )
        generated_prompt = (
            f"Execute as {selected_type.value}: {user_request.strip()}\n"
            f"Gateway note: {gateway_response.content.strip()}"
        )
        return PromptGenerationResult(
            selected_agent_type=selected_type,
            generated_prompt=generated_prompt,
            context_requirements=[
                "project_requirements",
                "project_memory",
                "uploaded_files",
                "code_configuration",
                "units",
            ],
            constraints={"no_direct_provider_calls": True},
            metadata={"provider": gateway_response.provider.value, "model": gateway_response.model},
        )

    def _select_agent_type(self, user_request: str) -> EngineeringAgentType:
        normalized = user_request.lower()
        for keywords, agent_type in _KEYWORD_ROUTING:
            if any(keyword in normalized for keyword in keywords):
                return agent_type
        return EngineeringAgentType.VALIDATION_AGENT
