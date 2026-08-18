"""Domain tests for approval policy extension points."""

from app.domain.approval_policy import requires_approval_for_target
from app.domain.models.human_approval import ApprovalTargetType


def test_agent_activation_requires_approval() -> None:
    assert requires_approval_for_target(
        ApprovalTargetType.AGENT_ACTION,
        "agent.activate",
    )


def test_unknown_agent_action_does_not_require_approval() -> None:
    assert not requires_approval_for_target(
        ApprovalTargetType.AGENT_ACTION,
        "agent.list",
    )


def test_pem_update_requires_approval() -> None:
    assert requires_approval_for_target(
        ApprovalTargetType.MODEL_CHANGE,
        "pem.update",
    )


def test_code_configuration_update_requires_approval() -> None:
    assert requires_approval_for_target(
        ApprovalTargetType.CONFIGURATION_CHANGE,
        "code.configuration.update",
    )
