"""Engineering agent runtime execution service."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.application.engineering_agent_handlers import (
    EngineeringAgentHandler,
    build_engineering_agent_handlers,
    new_trace_result_id,
)
from app.application.exceptions import (
    AgentExecutionNotFoundError,
    AgentHandlerNotFoundError,
    AgentNotFoundError,
)
from app.application.human_approval_service import HumanApprovalService
from app.application.project_context_assembly_service import ProjectContextAssemblyService
from app.application.prompt_generation_service import PromptGenerationService
from app.application.traceability_integration import (
    record_agent_execution_to_result,
    record_agent_result_to_approval,
    record_agent_result_to_validation,
    record_request_to_agent_execution,
)
from app.application.traceability_service import TraceabilityService
from app.domain.models.agent import AgentDefinition, EngineeringAgentType
from app.domain.models.agent_runtime import (
    AgentExecutionRecord,
    AgentExecutionRequest,
    AgentExecutionStatus,
    AgentResult,
    AgentValidationStatus,
    PromptGenerationResult,
)
from app.domain.models.human_approval import ApprovalTargetType
from app.domain.models.project_context import ProjectContextAssembly
from app.domain.repositories.agent_protocols import (
    AgentDefinitionRepository,
    AgentExecutionRepository,
    AgentVersionRepository,
)

AGENT_TYPES_REQUIRING_APPROVAL: frozenset[EngineeringAgentType] = frozenset(
    {
        EngineeringAgentType.STRUCTURAL_MODELING_AGENT,
        EngineeringAgentType.CONCRETE_DESIGN_AGENT,
        EngineeringAgentType.STEEL_DESIGN_AGENT,
        EngineeringAgentType.SEISMIC_AGENT,
    }
)


class AgentRuntimeService:
    def __init__(
        self,
        *,
        definition_repository: AgentDefinitionRepository,
        version_repository: AgentVersionRepository,
        execution_repository: AgentExecutionRepository,
        context_service: ProjectContextAssemblyService,
        prompt_generation_service: PromptGenerationService,
        traceability_service: TraceabilityService,
        approval_service: HumanApprovalService,
        handlers: dict[EngineeringAgentType, EngineeringAgentHandler] | None = None,
    ) -> None:
        self._definitions = definition_repository
        self._versions = version_repository
        self._executions = execution_repository
        self._context = context_service
        self._prompt_generation = prompt_generation_service
        self._traceability = traceability_service
        self._approval = approval_service
        self._handlers = handlers or build_engineering_agent_handlers()

    def execute(
        self,
        request: AgentExecutionRequest,
        *,
        actor_id: str,
    ) -> AgentExecutionRecord:
        context_assembly = self._context.assemble(request.project_id)
        context_snapshot = self._build_scoped_context(context_assembly)

        prompt_result: PromptGenerationResult | None = None
        if request.agent_definition_id is not None:
            definition = self._definitions.get_by_id(request.agent_definition_id)
            if definition is None:
                raise AgentNotFoundError(request.agent_definition_id)
            agent_definition = definition
        elif request.agent_type is not None:
            agent_definition = self._resolve_agent_by_type(request.agent_type)
        else:
            prompt_result = self._prompt_generation.generate(
                user_request=request.user_request,
                context_summary=context_snapshot,
            )
            agent_definition = self._resolve_agent_by_type(prompt_result.selected_agent_type)

        agent_version = self._resolve_agent_version(agent_definition)
        handler = self._resolve_handler(agent_definition)

        input_request = {
            "user_request": request.user_request,
            "parameters": request.parameters,
            "requested_by": request.requested_by or actor_id,
        }
        if prompt_result is not None:
            input_request["prompt_generation"] = prompt_result.model_dump()

        record = self._executions.create(
            project_id=request.project_id,
            agent_definition_id=agent_definition.id,
            agent_version=agent_version,
            input_request=input_request,
            context_snapshot=context_snapshot,
            created_by=actor_id,
        )

        if prompt_result is not None:
            record.prompt_generation = prompt_result.model_dump()

        record.execution_status = AgentExecutionStatus.RUNNING
        record.started_at = datetime.now(UTC)
        record = self._executions.update(record)

        try:
            agent_result = handler.execute(
                user_request=request.user_request,
                parameters=request.parameters,
                context=context_snapshot,
            )
            validation_status = self._validate_result(agent_result)
            requires_approval = self._requires_approval(
                request=request,
                agent_definition=agent_definition,
                agent_result=agent_result,
            )

            record.agent_result = agent_result
            record.output = agent_result.structured_output
            record.validation_status = validation_status

            request_trace_id = uuid4()
            result_trace_id = new_trace_result_id()
            record.traceability_metadata = {
                "request_trace_id": str(request_trace_id),
                "result_trace_id": str(result_trace_id),
            }

            record_request_to_agent_execution(
                self._traceability,
                project_id=request.project_id,
                request_id=request_trace_id,
                execution_id=record.id,
                metadata={"user_request": request.user_request},
            )
            record_agent_execution_to_result(
                self._traceability,
                project_id=request.project_id,
                execution_id=record.id,
                result_id=result_trace_id,
                metadata={"agent_type": agent_definition.agent_type.value if agent_definition.agent_type else None},
            )
            record_agent_result_to_validation(
                self._traceability,
                project_id=request.project_id,
                result_id=result_trace_id,
                validation_id=uuid4(),
                metadata={"validation_status": validation_status.value},
            )

            if requires_approval:
                approval = self._approval.create_request(
                    request.project_id,
                    requester=actor_id,
                    target_type=ApprovalTargetType.AGENT_ACTION,
                    target_action="agent.execute",
                    summary=f"Approve agent execution for {agent_definition.name}",
                    target_object_type="agent_execution",
                    target_object_id=record.id,
                    metadata={
                        "agent_definition_id": str(agent_definition.id),
                        "agent_type": agent_definition.agent_type.value if agent_definition.agent_type else None,
                        "user_request": request.user_request,
                    },
                )
                record.approval_request_id = approval.id
                record.execution_status = AgentExecutionStatus.WAITING_APPROVAL
                record_agent_result_to_approval(
                    self._traceability,
                    project_id=request.project_id,
                    result_id=result_trace_id,
                    approval_id=approval.id,
                )
            else:
                record.execution_status = AgentExecutionStatus.COMPLETED
                record.completed_at = datetime.now(UTC)

            return self._executions.update(record)
        except Exception as exc:
            record.execution_status = AgentExecutionStatus.FAILED
            record.completed_at = datetime.now(UTC)
            record.error_metadata = {"message": str(exc), "type": exc.__class__.__name__}
            self._executions.update(record)
            raise

    def get_execution(self, execution_id: UUID) -> AgentExecutionRecord:
        record = self._executions.get_by_id(execution_id)
        if record is None:
            raise AgentExecutionNotFoundError(execution_id)
        return record

    def list_executions(self, project_id: UUID, *, limit: int = 100) -> list[AgentExecutionRecord]:
        return self._executions.list_for_project(project_id, limit=limit)

    def _resolve_agent_by_type(self, agent_type: EngineeringAgentType) -> AgentDefinition:
        definition = self._definitions.get_by_agent_type(agent_type)
        if definition is not None:
            return definition
        return self._definitions.create(
            key=f"{agent_type.value.lower()}",
            name=agent_type.value.replace("_", " ").title(),
            description=f"Auto-provisioned handler for {agent_type.value}",
            agent_type=agent_type,
            configuration={"auto_provisioned": True},
        )

    def _resolve_agent_version(self, definition: AgentDefinition) -> int:
        if definition.current_version is not None:
            return definition.current_version
        active = self._versions.get_active_for_definition(definition.id)
        if active is not None:
            return active.version
        return 1

    def _resolve_handler(self, definition: AgentDefinition) -> EngineeringAgentHandler:
        if definition.agent_type is None:
            raise AgentHandlerNotFoundError("unknown")
        handler = self._handlers.get(definition.agent_type)
        if handler is None:
            raise AgentHandlerNotFoundError(definition.agent_type.value)
        return handler

    def _validate_result(self, agent_result: AgentResult) -> AgentValidationStatus:
        if agent_result.validation_information.get("stub"):
            return AgentValidationStatus.REQUIRES_ENGINEER_REVIEW
        if agent_result.confidence is not None and agent_result.confidence < 0.5:
            return AgentValidationStatus.WARNING
        return AgentValidationStatus.PASS

    def _requires_approval(
        self,
        *,
        request: AgentExecutionRequest,
        agent_definition: AgentDefinition,
        agent_result: AgentResult,
    ) -> bool:
        if request.requires_approval is True:
            return True
        if request.requires_approval is False:
            return False
        if agent_definition.agent_type in AGENT_TYPES_REQUIRING_APPROVAL:
            return True
        return bool(agent_result.validation_information.get("requires_approval"))

    def _build_scoped_context(self, assembly: ProjectContextAssembly) -> dict[str, Any]:
        return {
            "project_id": str(assembly.project_id),
            "project_name": assembly.project_name,
            "pem_version": assembly.pem_version,
            "code_configuration": (
                assembly.code_configuration.model_dump(mode="json")
                if assembly.code_configuration is not None
                else None
            ),
            "unit_configuration": (
                assembly.unit_configuration.model_dump(mode="json")
                if assembly.unit_configuration is not None
                else None
            ),
            "memory_total_count": assembly.memory_total_count,
            "memory_counts_by_type": assembly.memory_counts_by_type,
            "memories": [
                {
                    "id": str(memory.id),
                    "memory_type": memory.memory_type.value,
                    "content": memory.content[:500],
                }
                for memory in assembly.memories[:25]
            ],
            "files": [
                {
                    "id": str(file_item.id),
                    "filename": file_item.filename,
                    "file_type": file_item.file_type,
                    "parsing_status": file_item.parsing_status,
                    "extraction_status": file_item.extraction_status,
                }
                for file_item in assembly.files[:25]
            ],
        }
