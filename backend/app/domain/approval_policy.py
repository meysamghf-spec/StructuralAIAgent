"""Approval policy extension points for high-impact platform operations."""

from __future__ import annotations

from app.domain.models.human_approval import ApprovalTargetType

HIGH_IMPACT_TARGET_TYPES: frozenset[ApprovalTargetType] = frozenset(
    {
        ApprovalTargetType.AGENT_ACTION,
        ApprovalTargetType.DESIGN_DECISION,
        ApprovalTargetType.CONFIGURATION_CHANGE,
        ApprovalTargetType.MODEL_CHANGE,
    }
)

AGENT_ACTIONS_REQUIRING_APPROVAL: frozenset[str] = frozenset(
    {
        "agent.activate",
        "agent.version.publish",
        "agent.rollback",
        "agent.create",
    }
)

DESIGN_DECISIONS_REQUIRING_APPROVAL: frozenset[str] = frozenset(
    {
        "design.assumption.approve",
        "design.member.override",
    }
)

CONFIGURATION_CHANGES_REQUIRING_APPROVAL: frozenset[str] = frozenset(
    {
        "code.configuration.update",
        "unit.configuration.update",
    }
)

MODEL_CHANGES_REQUIRING_APPROVAL: frozenset[str] = frozenset(
    {
        "pem.update",
        "pem.snapshot.publish",
    }
)


def requires_approval_for_target(
    target_type: ApprovalTargetType,
    target_action: str,
) -> bool:
    if target_type not in HIGH_IMPACT_TARGET_TYPES:
        return False

    action_sets = {
        ApprovalTargetType.AGENT_ACTION: AGENT_ACTIONS_REQUIRING_APPROVAL,
        ApprovalTargetType.DESIGN_DECISION: DESIGN_DECISIONS_REQUIRING_APPROVAL,
        ApprovalTargetType.CONFIGURATION_CHANGE: CONFIGURATION_CHANGES_REQUIRING_APPROVAL,
        ApprovalTargetType.MODEL_CHANGE: MODEL_CHANGES_REQUIRING_APPROVAL,
    }
    return target_action in action_sets.get(target_type, frozenset())
