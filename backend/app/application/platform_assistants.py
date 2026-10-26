"""Built-in platform assistants: every assistant is provisioned ACTIVE with a real description.

Previously a definition was auto-created (status DRAFT, description "Auto-provisioned handler for ...") the first
time a chat run was routed to that agent type, so the Assistants page showed it as "In setup" with a disabled
button. All of these types have real handlers (engineering_agent_handlers) and chat summarisers
(assistant_chat), so they are provisioned as ACTIVE up front and kept that way.
"""

from __future__ import annotations

import logging
from typing import Any

from app.domain.models.agent import AgentDefinition, AgentDefinitionStatus, EngineeringAgentType

logger = logging.getLogger(__name__)

T = EngineeringAgentType

# agent_type -> (name, description, capabilities)
PLATFORM_ASSISTANTS: dict[EngineeringAgentType, tuple[str, str, list[str]]] = {
    T.STRUCTURAL_MODELING_AGENT: (
        "Structural Modeling Assistant",
        "Build and revise structural models from project requirements and geometry inputs.",
        ["Model setup", "Geometry updates", "System layout"],
    ),
    T.LOAD_ASSESSMENT_AGENT: (
        "Load Assessment Assistant",
        "Review dead, live, and environmental loading assumptions for your project.",
        ["Load combinations", "Code-based loading", "Load summaries"],
    ),
    T.ANALYSIS_AGENT: (
        "Structural Analysis Assistant",
        "Run and interpret structural analysis workflows for frames, shells, and foundations.",
        ["Analysis review", "Drift and stability", "Result summaries"],
    ),
    T.CONCRETE_DESIGN_AGENT: (
        "Concrete Design Assistant",
        "Support concrete member and slab design checks aligned with project codes.",
        ["Slab design", "Reinforcement review", "Concrete detailing"],
    ),
    T.STEEL_DESIGN_AGENT: (
        "Steel Design Assistant",
        "Assist with steel member sizing, connections, and design decision documentation.",
        ["Beam and column design", "Connection review", "Steel detailing"],
    ),
    T.OPTIMIZATION_AGENT: (
        "Optimization Assistant",
        "Find lighter, cheaper member sections that still satisfy the design checks.",
        ["Section optimization", "Cost comparison", "Prerequisite checklist"],
    ),
    T.SEISMIC_AGENT: (
        "Seismic Design Assistant",
        "Evaluate seismic parameters, lateral systems, and earthquake design assumptions.",
        ["Seismic loads", "Lateral system review", "Spectral considerations"],
    ),
    T.VALIDATION_AGENT: (
        "Design Validation Assistant",
        "Validate project configuration, assumptions, and code compliance checkpoints.",
        ["Code checks", "Assumption review", "Compliance summary"],
    ),
    T.CAD_AGENT: (
        "CAD Coordination Assistant",
        "Coordinate drawing deliverables and CAD-related engineering documentation.",
        ["Drawing review", "CAD coordination", "Deliverable tracking"],
    ),
    T.REPORTING_AGENT: (
        "Engineering Report Assistant",
        "Prepare engineering summaries, decision history, and project deliverable reports.",
        ["Report drafting", "Decision history", "Project summaries"],
    ),
    T.DOCUMENT_INTERPRETATION_AGENT: (
        "Document Interpretation Assistant",
        "Interpret specifications, PDFs, and uploaded documents into actionable engineering context.",
        ["Spec review", "Document extraction", "Requirement capture"],
    ),
    T.PROMPT_GENERATION_AGENT: (
        "Request Planning Assistant",
        "Understand engineer requests and route work to the right specialist assistant.",
        ["Request understanding", "Task routing", "Context planning"],
    ),
    T.STRUCTURAL_ENGINEERING_AGENT: (
        "Structural Engineering Agent",
        "Runs the project workflow from the engineering brief through the current PEM, analysis, design checks, "
        "QA, drawings, and report.",
        ["Brief and readiness", "Internal analysis", "Beam checks", "Schedules and report"],
    ),
}


def _config_for(agent_type: EngineeringAgentType, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = dict(existing or {})
    cfg.pop("auto_provisioned", None)
    cfg["platform_assistant"] = True
    cfg["enabled"] = True
    cfg["capabilities"] = PLATFORM_ASSISTANTS[agent_type][2]
    return cfg


def provision_platform_assistant(definitions, agent_type: EngineeringAgentType) -> AgentDefinition:
    """Create (ACTIVE) or repair the global definition for one platform agent type."""
    name, description, _caps = PLATFORM_ASSISTANTS.get(
        agent_type, (agent_type.value.replace("_", " ").title(), f"Built-in {agent_type.value} assistant.", [])
    )
    if agent_type not in PLATFORM_ASSISTANTS:
        PLATFORM_ASSISTANTS[agent_type] = (name, description, [])
    existing = [d for d in definitions.list_by_agent_type(agent_type) if d.project_id is None]
    if not existing:
        created = definitions.create(
            key=agent_type.value.lower(), name=name, description=description, agent_type=agent_type,
            configuration=_config_for(agent_type),
        )
        activated = definitions.update_status(created.id, AgentDefinitionStatus.ACTIVE)
        return activated or created
    definition = next((d for d in existing if d.status == AgentDefinitionStatus.ACTIVE), existing[0])
    placeholder = (definition.description or "").startswith("Auto-provisioned") or definition.configuration.get("auto_provisioned")
    if placeholder or definition.status == AgentDefinitionStatus.DRAFT:
        updated = definitions.update(
            definition.id, name=name, description=description if placeholder else None,
            configuration=_config_for(agent_type, definition.configuration),
        )
        definition = updated or definition
        if definition.status != AgentDefinitionStatus.ACTIVE:
            definition = definitions.update_status(definition.id, AgentDefinitionStatus.ACTIVE) or definition
    return definition


def ensure_platform_assistants(definitions) -> int:
    """Idempotent: make every built-in assistant a real, ACTIVE one. Returns how many rows were created/repaired."""
    changed = 0
    try:
        by_type: dict[EngineeringAgentType, list[AgentDefinition]] = {}
        for d in definitions.list_global():
            if d.agent_type is not None:
                by_type.setdefault(d.agent_type, []).append(d)
        for agent_type in PLATFORM_ASSISTANTS:
            rows = by_type.get(agent_type, [])
            healthy = any(
                r.status == AgentDefinitionStatus.ACTIVE
                and not (r.description or "").startswith("Auto-provisioned")
                and not r.configuration.get("auto_provisioned")
                for r in rows
            )
            if not healthy:
                provision_platform_assistant(definitions, agent_type)
                changed += 1
    except Exception:  # noqa: BLE001 - never break the listing because of provisioning
        logger.exception("could not provision platform assistants")
    return changed
