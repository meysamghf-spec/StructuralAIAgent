"""Engineering agent runtime execution service."""

from __future__ import annotations

from uuid import UUID

from app.application.agent_orchestration_service import AgentOrchestrationService
from app.application.agent_run_events import AgentRunProgressSink
from app.application.exceptions import AgentExecutionNotFoundError
from app.application.project_context_assembly_service import ProjectContextAssemblyService
from app.application.prompt_generation_service import PromptGenerationService
from app.domain.models.agent_runtime import (
    AgentExecutionRecord,
    AgentExecutionRequest,
    PromptGenerationResult,
)
from app.domain.repositories.agent_protocols import AgentExecutionRepository


class AgentRuntimeService:
    def __init__(
        self,
        *,
        execution_repository: AgentExecutionRepository,
        context_service: ProjectContextAssemblyService,
        prompt_generation_service: PromptGenerationService,
        orchestration_service: AgentOrchestrationService,
    ) -> None:
        self._executions = execution_repository
        self._context = context_service
        self._prompt_generation = prompt_generation_service
        self._orchestration = orchestration_service

    def execute(
        self,
        request: AgentExecutionRequest,
        *,
        actor_id: str,
        account_id: str | None = None,
        progress_sink: AgentRunProgressSink | None = None,
    ) -> AgentExecutionRecord:
        resolved_account_id = account_id or actor_id
        return self._orchestration.orchestrate(
            request,
            actor_id=actor_id,
            account_id=resolved_account_id,
            progress_sink=progress_sink,
        )

    def get_execution(self, execution_id: UUID) -> AgentExecutionRecord:
        record = self._executions.get_by_id(execution_id)
        if record is None:
            raise AgentExecutionNotFoundError(execution_id)
        return record

    def list_executions(self, project_id: UUID, *, limit: int = 100) -> list[AgentExecutionRecord]:
        return self._executions.list_for_project(project_id, limit=limit)

    def plan_request(self, *, project_id: UUID, user_request: str) -> PromptGenerationResult:
        context_assembly = self._context.assemble(project_id)
        context_snapshot = self._orchestration.build_context_snapshot(context_assembly)
        return self._prompt_generation.generate(
            user_request=user_request,
            context_summary=context_snapshot,
        )
