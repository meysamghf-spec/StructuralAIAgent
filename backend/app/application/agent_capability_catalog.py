"""Declarative capability contracts for engineering agent types."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.models.agent import EngineeringAgentType
from app.domain.models.platform_features import PlatformFeature


@dataclass(frozen=True)
class AgentCapabilityProfile:
    agent_type: EngineeringAgentType
    name: str
    version: str
    capabilities: tuple[str, ...]
    input_contract: tuple[str, ...]
    output_contract: tuple[str, ...]
    available_tools: tuple[str, ...]
    required_platform_features: tuple[PlatformFeature, ...]
    requires_human_approval: bool
    blocks_on_missing_inputs: bool = True


_AGENT_PROFILES: dict[EngineeringAgentType, AgentCapabilityProfile] = {
    EngineeringAgentType.STRUCTURAL_MODELING_AGENT: AgentCapabilityProfile(
        agent_type=EngineeringAgentType.STRUCTURAL_MODELING_AGENT,
        name="Structural Modeling Agent",
        version="1.0",
        capabilities=("model.authoring", "pem.revision"),
        input_contract=("user_objective", "project_context", "geometry_intent"),
        output_contract=("modeling_plan", "revision_recommendations", "validation_summary"),
        available_tools=("pem.revision", "project.validate", "project.memory"),
        required_platform_features=(),
        requires_human_approval=True,
    ),
    EngineeringAgentType.LOAD_ASSESSMENT_AGENT: AgentCapabilityProfile(
        agent_type=EngineeringAgentType.LOAD_ASSESSMENT_AGENT,
        name="Load Assessment Agent",
        version="1.0",
        capabilities=("loads.review", "code.lookup"),
        input_contract=("user_objective", "occupancy_assumptions", "code_configuration"),
        output_contract=("load_summary", "assumptions", "validation_summary"),
        available_tools=("code.lookup", "unit.convert", "project.memory"),
        required_platform_features=(),
        requires_human_approval=False,
    ),
    EngineeringAgentType.ANALYSIS_AGENT: AgentCapabilityProfile(
        agent_type=EngineeringAgentType.ANALYSIS_AGENT,
        name="Analysis Agent",
        version="1.0",
        capabilities=("analysis.plan", "analysis.run"),
        input_contract=("user_objective", "engineering_model", "load_cases"),
        output_contract=("analysis_plan", "run_recommendations", "validation_summary"),
        available_tools=("engineering.analysis.run", "project.validate", "project.memory"),
        required_platform_features=(),
        requires_human_approval=False,
    ),
    EngineeringAgentType.CONCRETE_DESIGN_AGENT: AgentCapabilityProfile(
        agent_type=EngineeringAgentType.CONCRETE_DESIGN_AGENT,
        name="Concrete Design Agent",
        version="1.0",
        capabilities=("design.concrete", "code.lookup"),
        input_contract=("user_objective", "member_forces", "material_properties"),
        output_contract=("design_recommendations", "validation_summary"),
        available_tools=("engineering.design.run", "code.lookup", "project.memory"),
        required_platform_features=(),
        requires_human_approval=True,
    ),
    EngineeringAgentType.STEEL_DESIGN_AGENT: AgentCapabilityProfile(
        agent_type=EngineeringAgentType.STEEL_DESIGN_AGENT,
        name="Steel Design Agent",
        version="1.0",
        capabilities=("design.steel", "code.lookup"),
        input_contract=("user_objective", "member_forces", "section_preferences"),
        output_contract=("design_recommendations", "validation_summary"),
        available_tools=("engineering.design.run", "code.lookup", "project.memory"),
        required_platform_features=(),
        requires_human_approval=True,
    ),
    EngineeringAgentType.OPTIMIZATION_AGENT: AgentCapabilityProfile(
        agent_type=EngineeringAgentType.OPTIMIZATION_AGENT,
        name="Optimization Agent",
        version="1.0",
        capabilities=("optimization.plan", "optimization.run"),
        input_contract=("user_objective", "analysis_results", "optimization_objective"),
        output_contract=("optimization_plan", "run_recommendations", "validation_summary"),
        available_tools=("engineering.optimization.run", "project.validate", "project.memory"),
        required_platform_features=(PlatformFeature.MULTI_MEMBER_OPTIMIZATION,),
        requires_human_approval=False,
        blocks_on_missing_inputs=True,
    ),
    EngineeringAgentType.SEISMIC_AGENT: AgentCapabilityProfile(
        agent_type=EngineeringAgentType.SEISMIC_AGENT,
        name="Seismic Agent",
        version="1.0",
        capabilities=("seismic.review", "code.lookup"),
        input_contract=("user_objective", "site_class", "lateral_system"),
        output_contract=("seismic_assessment", "validation_summary"),
        available_tools=("code.lookup", "engineering.analysis.run", "project.memory"),
        required_platform_features=(),
        requires_human_approval=True,
    ),
    EngineeringAgentType.VALIDATION_AGENT: AgentCapabilityProfile(
        agent_type=EngineeringAgentType.VALIDATION_AGENT,
        name="Validation Agent",
        version="1.0",
        capabilities=("project.validate", "code.validate"),
        input_contract=("user_objective", "project_configuration"),
        output_contract=("validation_report", "issues", "recommendations"),
        available_tools=("project.validate", "code.validate", "project.memory"),
        required_platform_features=(),
        requires_human_approval=False,
    ),
    EngineeringAgentType.CAD_AGENT: AgentCapabilityProfile(
        agent_type=EngineeringAgentType.CAD_AGENT,
        name="CAD Agent",
        version="1.0",
        capabilities=("cad.plan", "drawing.scope"),
        input_contract=("user_objective", "approved_model", "drawing_scope"),
        output_contract=("drawing_plan", "cad_recommendations", "validation_summary"),
        available_tools=("cad.generate", "integration.autocad", "project.memory"),
        required_platform_features=(PlatformFeature.CAD_PLAN_GENERATION,),
        requires_human_approval=False,
    ),
    EngineeringAgentType.REPORTING_AGENT: AgentCapabilityProfile(
        agent_type=EngineeringAgentType.REPORTING_AGENT,
        name="Reporting Agent",
        version="1.0",
        capabilities=("report.plan", "report.generate"),
        input_contract=("user_objective", "report_scope", "project_decisions"),
        output_contract=("report_outline", "generation_plan", "validation_summary"),
        available_tools=("report.generate", "traceability.graph", "project.memory"),
        required_platform_features=(),
        requires_human_approval=False,
    ),
    EngineeringAgentType.DOCUMENT_INTERPRETATION_AGENT: AgentCapabilityProfile(
        agent_type=EngineeringAgentType.DOCUMENT_INTERPRETATION_AGENT,
        name="Document Interpretation Agent",
        version="1.0",
        capabilities=("document.extract", "requirements.capture"),
        input_contract=("user_objective", "source_documents", "extraction_goals"),
        output_contract=("extracted_requirements", "memory_candidates", "validation_summary"),
        available_tools=("document.index", "document.extract", "project.memory"),
        required_platform_features=(),
        requires_human_approval=False,
    ),
    EngineeringAgentType.PROMPT_GENERATION_AGENT: AgentCapabilityProfile(
        agent_type=EngineeringAgentType.PROMPT_GENERATION_AGENT,
        name="Prompt Generation Agent",
        version="1.0",
        capabilities=("prompt.plan", "capability.route"),
        input_contract=("user_objective", "project_context"),
        output_contract=("structured_task", "selected_agent", "execution_plan"),
        available_tools=("project.context", "project.memory", "agent.capability_catalog"),
        required_platform_features=(),
        requires_human_approval=False,
        blocks_on_missing_inputs=False,
    ),
}


def get_agent_capability_profile(agent_type: EngineeringAgentType) -> AgentCapabilityProfile:
    profile = _AGENT_PROFILES.get(agent_type)
    if profile is None:
        return AgentCapabilityProfile(
            agent_type=agent_type,
            name=agent_type.value.replace("_", " ").title(),
            version="1.0",
            capabilities=(agent_type.value.lower(),),
            input_contract=("user_objective", "project_context"),
            output_contract=("structured_output", "validation_summary"),
            available_tools=("project.validate", "project.memory"),
            required_platform_features=(),
            requires_human_approval=False,
        )
    return profile


def list_agent_capability_profiles() -> list[AgentCapabilityProfile]:
    return list(_AGENT_PROFILES.values())
