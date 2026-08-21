"""Dispatches approval resolution to platform completion handlers."""

from __future__ import annotations

from uuid import UUID

from app.application.agent_approval_completion_service import AgentApprovalCompletionService
from app.application.agent_builder_approval_completion_service import AgentBuilderApprovalCompletionService
from app.domain.models.human_approval import HumanApprovalRequest


class CompositeApprovalCompletionService:
    def __init__(
        self,
        *,
        agent_execution_completion: AgentApprovalCompletionService,
        agent_builder_completion: AgentBuilderApprovalCompletionService,
    ) -> None:
        self._execution_completion = agent_execution_completion
        self._builder_completion = agent_builder_completion

    def handle_approval_resolved(
        self,
        project_id: UUID,
        request: HumanApprovalRequest,
    ):
        execution_result = self._execution_completion.handle_approval_resolved(project_id, request)
        self._builder_completion.handle_approval_resolved(project_id, request)
        return execution_result
