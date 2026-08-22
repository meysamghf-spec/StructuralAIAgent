"""Advanced prompt generation — routes planning through AI Gateway."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.application.ai_gateway_service import AIGatewayService
from app.domain.models.agent import EngineeringAgentType
from app.domain.models.agent_runtime import PromptGenerationResult
from app.domain.models.ai_gateway import AIMessage, AIMessageRole, AICompletionRequest

_DEFAULT_MODEL = "stub-engineering-router"

_ROUTING: list[tuple[tuple[str, ...], EngineeringAgentType, str]] = [
    (
        ("model", "geometry", "structural model", "مدل", "هندسی"),
        EngineeringAgentType.STRUCTURAL_MODELING_AGENT,
        "Set up or revise the structural engineering model",
    ),
    (
        ("seismic", "earthquake", "spectral", "زلزله", "لرزه"),
        EngineeringAgentType.SEISMIC_AGENT,
        "Evaluate seismic design parameters and lateral system assumptions",
    ),
    (
        ("load", "loading", "dead load", "live load", "بار"),
        EngineeringAgentType.LOAD_ASSESSMENT_AGENT,
        "Review and organize project loading assumptions",
    ),
    (
        ("analyze", "analysis", "modal", "drift", "تحلیل"),
        EngineeringAgentType.ANALYSIS_AGENT,
        "Run or review structural analysis workflows",
    ),
    (
        ("concrete", "rebar", "slab", "بتن"),
        EngineeringAgentType.CONCRETE_DESIGN_AGENT,
        "Support concrete member and slab design checks",
    ),
    (
        ("steel", "beam", "column", "connection", "فولاد"),
        EngineeringAgentType.STEEL_DESIGN_AGENT,
        "Support steel member sizing and connection review",
    ),
    (
        ("validate", "validation", "code check", "بررسی", "کنترل"),
        EngineeringAgentType.VALIDATION_AGENT,
        "Validate configuration, assumptions, and code compliance",
    ),
    (
        ("cad", "drawing", "autocad", "dxf", "dwg", "نقشه", "اجرا"),
        EngineeringAgentType.CAD_AGENT,
        "Prepare or coordinate engineering drawings and CAD deliverables",
    ),
    (
        ("report", "summary", "deliverable", "گزارش"),
        EngineeringAgentType.REPORTING_AGENT,
        "Prepare engineering summaries and deliverable reports",
    ),
    (
        ("document", "spec", "interpret", "pdf", "سند", "مشخصات"),
        EngineeringAgentType.DOCUMENT_INTERPRETATION_AGENT,
        "Interpret uploaded documents and specifications",
    ),
]

_AGENT_DETERMINISTIC_SERVICES: dict[EngineeringAgentType, list[str]] = {
    EngineeringAgentType.STRUCTURAL_MODELING_AGENT: ["pem.revision", "project.validate"],
    EngineeringAgentType.LOAD_ASSESSMENT_AGENT: ["code.lookup", "unit.convert"],
    EngineeringAgentType.ANALYSIS_AGENT: ["engineering.analysis.run", "project.validate"],
    EngineeringAgentType.CONCRETE_DESIGN_AGENT: ["engineering.design.run", "code.lookup"],
    EngineeringAgentType.STEEL_DESIGN_AGENT: ["engineering.design.run", "code.lookup"],
    EngineeringAgentType.SEISMIC_AGENT: ["code.lookup", "engineering.analysis.run"],
    EngineeringAgentType.VALIDATION_AGENT: ["project.validate", "code.lookup"],
    EngineeringAgentType.CAD_AGENT: ["integration.autocad", "pem.revision"],
    EngineeringAgentType.REPORTING_AGENT: ["report.generate", "traceability.graph"],
    EngineeringAgentType.DOCUMENT_INTERPRETATION_AGENT: ["document.index", "document.extract"],
}

_BASE_REQUIRED_INPUTS: dict[EngineeringAgentType, list[str]] = {
    EngineeringAgentType.STRUCTURAL_MODELING_AGENT: [
        "Structural geometry or layout inputs",
        "Material and section assumptions",
    ],
    EngineeringAgentType.LOAD_ASSESSMENT_AGENT: [
        "Occupancy and usage assumptions",
        "Applicable loading standard",
    ],
    EngineeringAgentType.ANALYSIS_AGENT: [
        "Structural model definition",
        "Load cases and combinations",
    ],
    EngineeringAgentType.CONCRETE_DESIGN_AGENT: [
        "Member forces or analysis results",
        "Concrete material properties",
    ],
    EngineeringAgentType.STEEL_DESIGN_AGENT: [
        "Member forces or analysis results",
        "Steel section catalog preferences",
    ],
    EngineeringAgentType.SEISMIC_AGENT: [
        "Site class and seismic parameters",
        "Lateral force-resisting system definition",
    ],
    EngineeringAgentType.VALIDATION_AGENT: [
        "Project configuration",
        "Active code and unit settings",
    ],
    EngineeringAgentType.CAD_AGENT: [
        "Approved engineering model or design data",
        "Drawing scope and sheet requirements",
    ],
    EngineeringAgentType.REPORTING_AGENT: [
        "Project context and decisions to include",
        "Report scope and audience",
    ],
    EngineeringAgentType.DOCUMENT_INTERPRETATION_AGENT: [
        "Uploaded source documents",
        "Specific questions or extraction goals",
    ],
}


@dataclass(frozen=True)
class _IntentProfile:
    agent_type: EngineeringAgentType
    intent_label: str
    objectives: list[str]


class PromptGenerationService:
    def __init__(self, *, ai_gateway: AIGatewayService) -> None:
        self._ai_gateway = ai_gateway

    def generate(
        self,
        *,
        user_request: str,
        context_summary: dict[str, Any],
        selected_agent_type: EngineeringAgentType | None = None,
        capability_profile: Any | None = None,
    ) -> PromptGenerationResult:
        from app.application.agent_capability_catalog import (
            AgentCapabilityProfile,
            get_agent_capability_profile,
        )

        intent = self._analyze_intent(user_request)
        agent_type = selected_agent_type or intent.agent_type
        profile = capability_profile or get_agent_capability_profile(agent_type)
        if not isinstance(profile, AgentCapabilityProfile):
            profile = get_agent_capability_profile(agent_type)
        if selected_agent_type is not None and selected_agent_type != intent.agent_type:
            intent = _IntentProfile(
                agent_type=agent_type,
                intent_label=self._objectives_for_agent(agent_type, user_request)[0]
                if self._objectives_for_agent(agent_type, user_request)
                else agent_type.value.replace("_", " ").title(),
                objectives=self._objectives_for_agent(agent_type, user_request),
            )
        relevant_context = self._collect_relevant_context(context_summary, agent_type)
        missing_information = self._detect_missing_information(
            user_request=user_request,
            context_summary=context_summary,
            agent_type=agent_type,
            relevant_context=relevant_context,
        )
        preserved_constraints = self._extract_preserved_constraints(context_summary)
        required_inputs = list(_BASE_REQUIRED_INPUTS.get(agent_type, list(profile.input_contract)))
        deterministic_services = list(_AGENT_DETERMINISTIC_SERVICES.get(agent_type, list(profile.available_tools)))
        available_tools = list(profile.available_tools)
        expected_output = list(profile.output_contract)
        validation_requirements = [
            "Do not fabricate CSI or analysis results",
            "Use deterministic platform services for calculations",
            "Preserve approved PEM and project decisions",
            "Record traceability for consequential outputs",
        ]
        approval_requirements: list[str] = []
        if profile.requires_human_approval:
            approval_requirements.append("Human approval required before finalizing consequential changes")
        context_requirements = self._derive_context_requirements(
            agent_type,
            relevant_context,
            missing_information,
        )
        execution_plan = self._build_execution_plan(
            intent=intent,
            missing_information=missing_information,
            deterministic_services=deterministic_services,
            relevant_context=relevant_context,
        )
        constraints = {
            "no_direct_provider_calls": True,
            "preserve_approved_decisions": True,
            "deterministic_calculations_only_in_services": True,
        }
        if preserved_constraints:
            constraints["approved_project_constraints"] = preserved_constraints

        gateway_response = self._ai_gateway.complete(
            AICompletionRequest(
                model=_DEFAULT_MODEL,
                messages=[
                    AIMessage(
                        role=AIMessageRole.SYSTEM,
                        content=(
                            "You are a prompt generation agent for structural engineering workflows. "
                            "Produce a concise execution prompt for a specialist assistant. "
                            "Do not perform engineering calculations. "
                            "Reference only provided context and clearly note missing inputs."
                        ),
                    ),
                    AIMessage(
                        role=AIMessageRole.USER,
                        content=(
                            f"User request: {user_request.strip()}\n"
                            f"Intent: {intent.intent_label}\n"
                            f"Selected assistant: {agent_type.value}\n"
                            f"Objectives: {intent.objectives}\n"
                            f"Missing information: {missing_information}\n"
                            f"Preserved constraints: {preserved_constraints}\n"
                            f"Relevant context: {relevant_context}\n"
                            f"Execution plan: {execution_plan}"
                        ),
                    ),
                ],
                context={"phase": "prompt_generation"},
                metadata={"agent_type": EngineeringAgentType.PROMPT_GENERATION_AGENT.value},
            )
        )

        generated_prompt = self._compose_generated_prompt(
            user_request=user_request,
            intent=intent,
            gateway_note=gateway_response.content.strip(),
            missing_information=missing_information,
            preserved_constraints=preserved_constraints,
        )

        return PromptGenerationResult(
            selected_agent_type=agent_type,
            generated_prompt=generated_prompt,
            context_requirements=context_requirements,
            constraints=constraints,
            metadata={
                "provider": gateway_response.provider.value,
                "model": gateway_response.model,
                "routing_method": "keyword_and_context",
            },
            user_intent=intent.intent_label,
            engineering_objectives=intent.objectives,
            required_inputs=required_inputs,
            missing_information=missing_information,
            relevant_context=relevant_context,
            deterministic_services=deterministic_services,
            execution_plan=execution_plan,
            preserved_constraints=preserved_constraints,
            objective=user_request.strip(),
            project_context_summary={
                "project_id": context_summary.get("project_id"),
                "project_name": context_summary.get("project_name"),
                "pem_version": context_summary.get("pem_version"),
            },
            applicable_code_configuration=context_summary.get("code_configuration"),
            available_tools=available_tools,
            expected_output=expected_output,
            validation_requirements=validation_requirements,
            approval_requirements=approval_requirements,
            capability_profile={
                "name": profile.name,
                "version": profile.version,
                "capabilities": list(profile.capabilities),
                "requires_human_approval": profile.requires_human_approval,
            },
        )

    def _analyze_intent(self, user_request: str) -> _IntentProfile:
        normalized = user_request.lower()
        for keywords, agent_type, intent_label in _ROUTING:
            if any(keyword in normalized for keyword in keywords):
                return _IntentProfile(
                    agent_type=agent_type,
                    intent_label=intent_label,
                    objectives=self._objectives_for_agent(agent_type, user_request),
                )
        return _IntentProfile(
            agent_type=EngineeringAgentType.VALIDATION_AGENT,
            intent_label="Review project readiness and identify next engineering steps",
            objectives=[
                "Understand the engineer request",
                "Check project configuration and available context",
                "Recommend the next safe engineering action",
            ],
        )

    def _objectives_for_agent(
        self,
        agent_type: EngineeringAgentType,
        user_request: str,
    ) -> list[str]:
        base = {
            EngineeringAgentType.STRUCTURAL_MODELING_AGENT: [
                "Capture geometry and system layout intent",
                "Align model updates with project requirements",
            ],
            EngineeringAgentType.CAD_AGENT: [
                "Identify drawing deliverables requested by the engineer",
                "Prepare CAD workflow using approved model data",
            ],
            EngineeringAgentType.DOCUMENT_INTERPRETATION_AGENT: [
                "Extract actionable requirements from uploaded documents",
                "Link extracted information to project memory",
            ],
        }.get(agent_type, ["Fulfill the engineer request using project context"])

        if len(user_request.strip()) > 120:
            base.append("Preserve explicit constraints stated in the request")
        return base

    def _collect_relevant_context(
        self,
        context_summary: dict[str, Any],
        agent_type: EngineeringAgentType,
    ) -> dict[str, Any]:
        memories = context_summary.get("memories", [])
        files = context_summary.get("files", [])
        code_configuration = context_summary.get("code_configuration")
        unit_configuration = context_summary.get("unit_configuration")

        relevant_memory_types = {
            EngineeringAgentType.VALIDATION_AGENT: {"REQUIREMENT", "DECISION", "ASSUMPTION"},
            EngineeringAgentType.DOCUMENT_INTERPRETATION_AGENT: {"EXTRACTED_INFORMATION", "REQUIREMENT"},
            EngineeringAgentType.CAD_AGENT: {"DESIGN_CHOICE", "MODEL_VERSION", "DECISION"},
            EngineeringAgentType.ANALYSIS_AGENT: {"MODEL_VERSION", "ASSUMPTION", "DECISION"},
            EngineeringAgentType.REPORTING_AGENT: {"DECISION", "REVISION", "VALIDATION_RESULT"},
        }.get(agent_type, {"REQUIREMENT", "DECISION", "ASSUMPTION", "DESIGN_CHOICE"})

        selected_memories = [
            memory
            for memory in memories
            if memory.get("memory_type") in relevant_memory_types
        ][:8]

        selected_files = files[:8]
        if agent_type == EngineeringAgentType.DOCUMENT_INTERPRETATION_AGENT:
            selected_files = [
                file_item
                for file_item in files
                if str(file_item.get("extraction_status", "")).upper() in {"COMPLETED", "IN_PROGRESS", "PENDING"}
            ][:8]

        return {
            "project_id": context_summary.get("project_id"),
            "project_name": context_summary.get("project_name"),
            "pem_version": context_summary.get("pem_version"),
            "code_configuration": code_configuration,
            "unit_configuration": unit_configuration,
            "memories": selected_memories,
            "files": selected_files,
            "memory_total_count": context_summary.get("memory_total_count", 0),
            "file_count": len(files),
        }

    def _detect_missing_information(
        self,
        *,
        user_request: str,
        context_summary: dict[str, Any],
        agent_type: EngineeringAgentType,
        relevant_context: dict[str, Any],
    ) -> list[str]:
        missing: list[str] = []

        if context_summary.get("code_configuration") is None:
            missing.append("Project code configuration")
        if context_summary.get("unit_configuration") is None:
            missing.append("Project unit system")

        pem_version = context_summary.get("pem_version")
        if pem_version in (None, 0) and agent_type in {
            EngineeringAgentType.STRUCTURAL_MODELING_AGENT,
            EngineeringAgentType.ANALYSIS_AGENT,
            EngineeringAgentType.CAD_AGENT,
            EngineeringAgentType.CONCRETE_DESIGN_AGENT,
            EngineeringAgentType.STEEL_DESIGN_AGENT,
        }:
            missing.append("Engineering model baseline")

        files = relevant_context.get("files", [])
        if agent_type == EngineeringAgentType.DOCUMENT_INTERPRETATION_AGENT and not files:
            missing.append("Uploaded source documents")

        if agent_type == EngineeringAgentType.CAD_AGENT:
            if not files and pem_version in (None, 0):
                missing.append("Approved model or reference drawings")

        normalized = user_request.lower()
        if any(term in normalized for term in ("file", "upload", "pdf", "dwg", "dxf", "فایل")) and not files:
            missing.append("Referenced project files")

        if agent_type in {
            EngineeringAgentType.CONCRETE_DESIGN_AGENT,
            EngineeringAgentType.STEEL_DESIGN_AGENT,
            EngineeringAgentType.ANALYSIS_AGENT,
        }:
            has_model_memory = any(
                memory.get("memory_type") in {"MODEL_VERSION", "DECISION"}
                for memory in relevant_context.get("memories", [])
            )
            if pem_version in (None, 0) and not has_model_memory:
                missing.append("Analysis-ready structural model")

        return missing

    def _extract_preserved_constraints(self, context_summary: dict[str, Any]) -> list[str]:
        preserved: list[str] = []
        for memory in context_summary.get("memories", []):
            memory_type = memory.get("memory_type")
            content = memory.get("content")
            if memory_type not in {"DECISION", "REQUIREMENT", "DESIGN_CHOICE"}:
                continue
            if isinstance(content, str) and content.strip():
                preserved.append(content.strip()[:240])
        return preserved[:10]

    def _derive_context_requirements(
        self,
        agent_type: EngineeringAgentType,
        relevant_context: dict[str, Any],
        missing_information: list[str],
    ) -> list[str]:
        requirements = [
            "project_requirements",
            "project_memory",
            "code_configuration",
            "units",
        ]
        if relevant_context.get("files"):
            requirements.append("uploaded_files")
        if agent_type in {
            EngineeringAgentType.STRUCTURAL_MODELING_AGENT,
            EngineeringAgentType.ANALYSIS_AGENT,
            EngineeringAgentType.CONCRETE_DESIGN_AGENT,
            EngineeringAgentType.STEEL_DESIGN_AGENT,
            EngineeringAgentType.CAD_AGENT,
        }:
            requirements.append("engineering_model")
        if missing_information:
            requirements.append("missing_information_resolution")
        return requirements

    def _build_execution_plan(
        self,
        *,
        intent: _IntentProfile,
        missing_information: list[str],
        deterministic_services: list[str],
        relevant_context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        steps: list[dict[str, Any]] = []
        step_number = 1

        steps.append(
            {
                "step_number": step_number,
                "title": "Understand engineer goal",
                "description": intent.intent_label,
                "capability": EngineeringAgentType.PROMPT_GENERATION_AGENT.value,
                "capability_kind": "agent",
            }
        )
        step_number += 1

        if missing_information:
            steps.append(
                {
                    "step_number": step_number,
                    "title": "Identify missing inputs",
                    "description": "; ".join(missing_information),
                    "capability": "project.context",
                    "capability_kind": "deterministic_service",
                }
            )
            step_number += 1

        if relevant_context.get("files"):
            steps.append(
                {
                    "step_number": step_number,
                    "title": "Review relevant project files",
                    "description": "Use indexed files linked to the request",
                    "capability": "document.index",
                    "capability_kind": "deterministic_service",
                }
            )
            step_number += 1

        for service in deterministic_services[:2]:
            steps.append(
                {
                    "step_number": step_number,
                    "title": "Run supporting engineering service",
                    "description": service,
                    "capability": service,
                    "capability_kind": "deterministic_service",
                }
            )
            step_number += 1

        steps.append(
            {
                "step_number": step_number,
                "title": "Execute specialist assistant work",
                "description": intent.objectives[0] if intent.objectives else intent.intent_label,
                "capability": intent.agent_type.value,
                "capability_kind": "agent",
            }
        )
        step_number += 1

        steps.append(
            {
                "step_number": step_number,
                "title": "Validate and record results",
                "description": "Apply validation checks and traceability links",
                "capability": "project.validate",
                "capability_kind": "deterministic_service",
            }
        )
        return steps

    def _compose_generated_prompt(
        self,
        *,
        user_request: str,
        intent: _IntentProfile,
        gateway_note: str,
        missing_information: list[str],
        preserved_constraints: list[str],
    ) -> str:
        lines = [
            f"Assistant route: {intent.agent_type.value}",
            f"Engineer request: {user_request.strip()}",
            f"Primary objective: {intent.intent_label}",
        ]
        if intent.objectives:
            lines.append(f"Objectives: {'; '.join(intent.objectives)}")
        if preserved_constraints:
            lines.append(f"Preserve approved constraints: {' | '.join(preserved_constraints[:5])}")
        if missing_information:
            lines.append(
                "Missing information to resolve before final engineering decisions: "
                + "; ".join(missing_information)
            )
        lines.append(f"Planning note: {gateway_note}")
        lines.append("Do not perform calculations outside deterministic platform services.")
        return "\n".join(lines)
