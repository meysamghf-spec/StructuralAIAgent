"""Validation rules for Agent Builder configurations."""

from __future__ import annotations

from app.domain.models.agent import AgentDefinition, AgentVersion
from app.domain.models.agent_builder import AgentBuilderValidationIssue, AgentBuilderValidationResult
from app.domain.models.agent import EngineeringAgentType

SUPPORTED_AGENT_TYPES = frozenset(item.value for item in EngineeringAgentType if item != EngineeringAgentType.PROMPT_GENERATION_AGENT)

_AUTHORITY_BYPASS_FLAGS = frozenset(
    {
        "allow_direct_calculations",
        "overrides_pem",
        "override_pem",
        "pem_override",
        "overrides_geometry",
        "overrides_loads",
        "overrides_analysis",
        "overrides_design",
        "overrides_code",
        "overrides_qa",
        "learning_overrides_pem",
        "learning_overrides_rules",
        "learning_overrides_qa",
    }
)

ALLOWED_TOOLS_BY_AGENT_TYPE: dict[str, frozenset[str]] = {
    EngineeringAgentType.STRUCTURAL_MODELING_AGENT.value: frozenset(
        {"pem.revision", "project.validate", "project.context"}
    ),
    EngineeringAgentType.LOAD_ASSESSMENT_AGENT.value: frozenset(
        {"code.lookup", "unit.convert", "project.context"}
    ),
    EngineeringAgentType.ANALYSIS_AGENT.value: frozenset(
        {"engineering.analysis.run", "project.validate", "project.context"}
    ),
    EngineeringAgentType.CONCRETE_DESIGN_AGENT.value: frozenset(
        {"engineering.design.run", "code.lookup", "unit.convert", "project.validate"}
    ),
    EngineeringAgentType.STEEL_DESIGN_AGENT.value: frozenset(
        {"engineering.design.run", "code.lookup", "unit.convert", "project.validate"}
    ),
    EngineeringAgentType.SEISMIC_AGENT.value: frozenset(
        {"code.lookup", "engineering.analysis.run", "project.context"}
    ),
    EngineeringAgentType.VALIDATION_AGENT.value: frozenset(
        {"project.validate", "code.lookup", "traceability.graph"}
    ),
    EngineeringAgentType.CAD_AGENT.value: frozenset(
        {"integration.autocad", "pem.revision", "integration.dxf"}
    ),
    EngineeringAgentType.REPORTING_AGENT.value: frozenset(
        {"report.generate", "traceability.graph", "project.context"}
    ),
    EngineeringAgentType.DOCUMENT_INTERPRETATION_AGENT.value: frozenset(
        {"document.index", "document.extract", "project.context"}
    ),
}


def validate_agent_configuration(
    *,
    definition: AgentDefinition,
    version: AgentVersion,
    capability_keys: list[str],
) -> AgentBuilderValidationResult:
    issues: list[AgentBuilderValidationIssue] = []

    if not definition.name.strip():
        issues.append(
            AgentBuilderValidationIssue(
                code="MISSING_NAME",
                message="Assistant name is required.",
            )
        )

    if definition.agent_type is None:
        issues.append(
            AgentBuilderValidationIssue(
                code="MISSING_AGENT_TYPE",
                message="Assistant type is required before publication.",
            )
        )
    elif definition.agent_type.value not in SUPPORTED_AGENT_TYPES:
        issues.append(
            AgentBuilderValidationIssue(
                code="UNSUPPORTED_AGENT_TYPE",
                message="Selected assistant type is not supported for custom builder agents.",
            )
        )

    if not (version.instructions and version.instructions.strip()):
        issues.append(
            AgentBuilderValidationIssue(
                code="MISSING_INSTRUCTIONS",
                message="Instructions are required before publication.",
            )
        )

    metadata = version.configuration_metadata or {}
    tools = metadata.get("allowed_tools", [])
    if not isinstance(tools, list):
        issues.append(
            AgentBuilderValidationIssue(
                code="INVALID_TOOLS",
                message="Allowed tools must be provided as a list.",
            )
        )
        tools = []

    model_config = metadata.get("model_configuration", {})
    if model_config is not None and not isinstance(model_config, dict):
        issues.append(
            AgentBuilderValidationIssue(
                code="INVALID_MODEL_CONFIGURATION",
                message="Model configuration must be an object.",
            )
        )
        model_config = {}

    if definition.agent_type is not None:
        allowed_tools = ALLOWED_TOOLS_BY_AGENT_TYPE.get(definition.agent_type.value, frozenset())
        unsupported_tools = [tool for tool in tools if tool not in allowed_tools]
        if unsupported_tools:
            issues.append(
                AgentBuilderValidationIssue(
                    code="UNSUPPORTED_TOOLS",
                    message=(
                        "One or more tools are not available for this assistant type: "
                        + ", ".join(unsupported_tools)
                    ),
                    severity="ERROR",
                )
            )

        bypasses = [
            flag
            for flag in _AUTHORITY_BYPASS_FLAGS
            if metadata.get(flag) is True or (definition.configuration or {}).get(flag) is True
        ]
        if bypasses:
            issues.append(
                AgentBuilderValidationIssue(
                    code="UNSAFE_CONFIGURATION",
                    message=(
                        "Assistant configuration cannot override PEM, current engineering data, "
                        "code checks, QA, or learning authority: " + ", ".join(sorted(bypasses))
                    ),
                    severity="ERROR",
                )
            )

        learning_authority = metadata.get("learning_authority")
        if learning_authority not in {None, "CONTEXT_ONLY"}:
            issues.append(
                AgentBuilderValidationIssue(
                    code="UNSAFE_CONFIGURATION",
                    message="Approved learning remains context only and cannot become engineering authority.",
                    severity="ERROR",
                )
            )

        for field_name in ("task_types", "element_types", "supported_codes"):
            value = metadata.get(field_name, [])
            if value is None:
                continue
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                issues.append(
                    AgentBuilderValidationIssue(
                        code="INVALID_CONFIGURATION",
                        message=f"{field_name} must be a list of strings.",
                    )
                )

        for field_name in ("input_contract", "output_contract"):
            value = metadata.get(field_name, {})
            if value is None:
                continue
            if not isinstance(value, dict):
                issues.append(
                    AgentBuilderValidationIssue(
                        code="INVALID_CONFIGURATION",
                        message=f"{field_name} must be an object.",
                    )
                )

    if not capability_keys:
        issues.append(
            AgentBuilderValidationIssue(
                code="MISSING_CAPABILITIES",
                message="At least one capability should be defined for the assistant.",
                severity="WARNING",
            )
        )

    error_count = sum(1 for issue in issues if issue.severity == "ERROR")
    return AgentBuilderValidationResult(valid=error_count == 0, issues=issues)
