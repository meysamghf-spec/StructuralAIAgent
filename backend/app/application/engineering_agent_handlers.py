"""Engineering agent handler extension points — stub implementations only."""

from __future__ import annotations

from typing import Any, Protocol
from uuid import uuid4

from app.domain.models.agent import EngineeringAgentType
from app.domain.models.agent_runtime import AgentResult


class EngineeringAgentHandler(Protocol):
    agent_type: EngineeringAgentType

    def execute(
        self,
        *,
        user_request: str,
        parameters: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentResult: ...


def _stub_result(
    *,
    agent_type: EngineeringAgentType,
    user_request: str,
    parameters: dict[str, Any],
    context: dict[str, Any],
    action: str,
) -> AgentResult:
    return AgentResult(
        structured_output={
            "agent_type": agent_type.value,
            "action": action,
            "status": "stub_completed",
            "user_request": user_request,
            "parameters": parameters,
            "context_summary": {
                "project_id": context.get("project_id"),
                "project_name": context.get("project_name"),
                "memory_total_count": context.get("memory_total_count"),
                "file_count": len(context.get("files", [])),
            },
        },
        confidence=0.0,
        generated_artifacts=[],
        recommendations=[
            f"Stub handler for {agent_type.value}; replace with domain logic in a future milestone."
        ],
        validation_information={"stub": True},
    )


class StructuralModelingAgentHandler:
    agent_type = EngineeringAgentType.STRUCTURAL_MODELING_AGENT

    def execute(
        self,
        *,
        user_request: str,
        parameters: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentResult:
        return _stub_result(
            agent_type=self.agent_type,
            user_request=user_request,
            parameters=parameters,
            context=context,
            action="structural_modeling",
        )


class LoadAssessmentAgentHandler:
    agent_type = EngineeringAgentType.LOAD_ASSESSMENT_AGENT

    def execute(
        self,
        *,
        user_request: str,
        parameters: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentResult:
        return _stub_result(
            agent_type=self.agent_type,
            user_request=user_request,
            parameters=parameters,
            context=context,
            action="load_assessment",
        )


class AnalysisAgentHandler:
    agent_type = EngineeringAgentType.ANALYSIS_AGENT

    def execute(
        self,
        *,
        user_request: str,
        parameters: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentResult:
        return _stub_result(
            agent_type=self.agent_type,
            user_request=user_request,
            parameters=parameters,
            context=context,
            action="analysis",
        )


class ConcreteDesignAgentHandler:
    agent_type = EngineeringAgentType.CONCRETE_DESIGN_AGENT

    def execute(
        self,
        *,
        user_request: str,
        parameters: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentResult:
        return _stub_result(
            agent_type=self.agent_type,
            user_request=user_request,
            parameters=parameters,
            context=context,
            action="concrete_design",
        )


class SteelDesignAgentHandler:
    agent_type = EngineeringAgentType.STEEL_DESIGN_AGENT

    def execute(
        self,
        *,
        user_request: str,
        parameters: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentResult:
        return _stub_result(
            agent_type=self.agent_type,
            user_request=user_request,
            parameters=parameters,
            context=context,
            action="steel_design",
        )


class SeismicAgentHandler:
    agent_type = EngineeringAgentType.SEISMIC_AGENT

    def execute(
        self,
        *,
        user_request: str,
        parameters: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentResult:
        return _stub_result(
            agent_type=self.agent_type,
            user_request=user_request,
            parameters=parameters,
            context=context,
            action="seismic",
        )


class ValidationAgentHandler:
    agent_type = EngineeringAgentType.VALIDATION_AGENT

    def execute(
        self,
        *,
        user_request: str,
        parameters: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentResult:
        return _stub_result(
            agent_type=self.agent_type,
            user_request=user_request,
            parameters=parameters,
            context=context,
            action="validation",
        )


class CadAgentHandler:
    agent_type = EngineeringAgentType.CAD_AGENT

    def execute(
        self,
        *,
        user_request: str,
        parameters: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentResult:
        return _stub_result(
            agent_type=self.agent_type,
            user_request=user_request,
            parameters=parameters,
            context=context,
            action="cad",
        )


class ReportingAgentHandler:
    agent_type = EngineeringAgentType.REPORTING_AGENT

    def execute(
        self,
        *,
        user_request: str,
        parameters: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentResult:
        return _stub_result(
            agent_type=self.agent_type,
            user_request=user_request,
            parameters=parameters,
            context=context,
            action="reporting",
        )


class DocumentInterpretationAgentHandler:
    agent_type = EngineeringAgentType.DOCUMENT_INTERPRETATION_AGENT

    def execute(
        self,
        *,
        user_request: str,
        parameters: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentResult:
        return _stub_result(
            agent_type=self.agent_type,
            user_request=user_request,
            parameters=parameters,
            context=context,
            action="document_interpretation",
        )


def build_engineering_agent_handlers() -> dict[EngineeringAgentType, EngineeringAgentHandler]:
    handlers: list[EngineeringAgentHandler] = [
        StructuralModelingAgentHandler(),
        LoadAssessmentAgentHandler(),
        AnalysisAgentHandler(),
        ConcreteDesignAgentHandler(),
        SteelDesignAgentHandler(),
        SeismicAgentHandler(),
        ValidationAgentHandler(),
        CadAgentHandler(),
        ReportingAgentHandler(),
        DocumentInterpretationAgentHandler(),
    ]
    return {handler.agent_type: handler for handler in handlers}


def new_trace_result_id() -> Any:
    return uuid4()
