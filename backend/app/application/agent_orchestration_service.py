"""Unified Structural AI Agent orchestration pipeline."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.application.agent_capability_catalog import AgentCapabilityProfile, get_agent_capability_profile
from app.application.engineering_agent_handlers import (
    EngineeringAgentHandler,
    build_engineering_agent_handlers,
    new_trace_result_id,
)
from app.application.entitlement_authorization_service import EntitlementAuthorizationService
from app.application.exceptions import (
    AgentHandlerNotFoundError,
    AgentNotFoundError,
    FeatureAccessDeniedError,
)
from app.application.human_approval_service import HumanApprovalService
from app.application.hybrid_orchestration_service import HybridOrchestrationService
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
    is_awaiting_human_approval,
)
from app.domain.models.human_approval import ApprovalTargetType
from app.domain.models.orchestration import OrchestrationTask
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


class AgentOrchestrationService:
    """Production-safe agent execution layer coordinating context, prompts, tools, and traceability."""

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
        entitlement_service: EntitlementAuthorizationService,
        orchestration_service: HybridOrchestrationService | None = None,
        handlers: dict[EngineeringAgentType, EngineeringAgentHandler] | None = None,
    ) -> None:
        self._definitions = definition_repository
        self._versions = version_repository
        self._executions = execution_repository
        self._context = context_service
        self._prompt_generation = prompt_generation_service
        self._traceability = traceability_service
        self._approval = approval_service
        self._entitlements = entitlement_service
        self._orchestration = orchestration_service
        self._handlers = handlers or build_engineering_agent_handlers()

    def orchestrate(
        self,
        request: AgentExecutionRequest,
        *,
        actor_id: str,
        account_id: str,
    ) -> AgentExecutionRecord:
        context_assembly = self._context.assemble(request.project_id)
        context_snapshot = self._build_scoped_context(context_assembly)

        prompt_result: PromptGenerationResult | None = None
        if request.agent_definition_id is not None:
            definition = self._definitions.get_by_id(request.agent_definition_id)
            if definition is None:
                raise AgentNotFoundError(request.agent_definition_id)
            agent_definition = definition
            selected_type = definition.agent_type
        elif request.agent_type is not None:
            selected_type = request.agent_type
            agent_definition = self._resolve_agent_by_type(selected_type)
        else:
            prompt_result = self._prompt_generation.generate(
                user_request=request.user_request,
                context_summary=context_snapshot,
            )
            selected_type = prompt_result.selected_agent_type
            agent_definition = self._resolve_agent_by_type(selected_type)

        if selected_type is None:
            raise AgentHandlerNotFoundError("unknown")

        capability_profile = get_agent_capability_profile(selected_type)
        self._enforce_entitlements(account_id, capability_profile)

        if prompt_result is None:
            prompt_result = self._prompt_generation.generate(
                user_request=request.user_request,
                context_summary=context_snapshot,
                selected_agent_type=selected_type,
                capability_profile=capability_profile,
            )

        orchestration_trace = self._build_orchestration_trace(
            request=request,
            context_snapshot=context_snapshot,
            prompt_result=prompt_result,
            capability_profile=capability_profile,
        )

        if self._should_block_execution(
            request=request,
            prompt_result=prompt_result,
            capability_profile=capability_profile,
        ):
            return self._create_blocked_execution(
                request=request,
                actor_id=actor_id,
                agent_definition=agent_definition,
                prompt_result=prompt_result,
                context_snapshot=context_snapshot,
                orchestration_trace=orchestration_trace,
            )

        agent_version = self._resolve_agent_version(agent_definition, request)
        handler = self._resolve_handler(agent_definition)

        input_request = {
            "user_request": request.user_request,
            "parameters": request.parameters,
            "requested_by": request.requested_by or actor_id,
            "orchestration_trace": orchestration_trace,
        }
        input_request["prompt_generation"] = prompt_result.model_dump()

        record = self._executions.create(
            project_id=request.project_id,
            agent_definition_id=agent_definition.id,
            agent_version=agent_version,
            input_request=input_request,
            context_snapshot=context_snapshot,
            created_by=actor_id,
        )
        record.prompt_generation = prompt_result.model_dump()
        record.execution_status = AgentExecutionStatus.QUEUED
        record.traceability_metadata = {"orchestration_trace": orchestration_trace}
        record = self._executions.update(record)

        record.execution_status = AgentExecutionStatus.RUNNING
        record.started_at = datetime.now(UTC)
        record = self._executions.update(record)

        try:
            agent_result = handler.execute(
                user_request=request.user_request,
                parameters=request.parameters,
                context=context_snapshot,
            )
            agent_result = self._apply_orchestration(
                project_id=request.project_id,
                request=request,
                agent_result=agent_result,
            )
            validation_status = self._validate_result(agent_result)
            requires_approval = self._requires_approval(
                request=request,
                agent_definition=agent_definition,
                capability_profile=capability_profile,
                agent_result=agent_result,
            )

            record.agent_result = agent_result
            record.output = agent_result.structured_output
            record.validation_status = validation_status

            request_trace_id = uuid4()
            result_trace_id = new_trace_result_id()
            record.traceability_metadata = {
                **record.traceability_metadata,
                "request_trace_id": str(request_trace_id),
                "result_trace_id": str(result_trace_id),
                "selected_agent_type": selected_type.value,
                "pem_version": context_snapshot.get("pem_version"),
            }

            record_request_to_agent_execution(
                self._traceability,
                project_id=request.project_id,
                request_id=request_trace_id,
                execution_id=record.id,
                metadata={
                    "user_request": request.user_request,
                    "generated_prompt": prompt_result.generated_prompt,
                },
            )
            record_agent_execution_to_result(
                self._traceability,
                project_id=request.project_id,
                execution_id=record.id,
                result_id=result_trace_id,
                metadata={"agent_type": selected_type.value},
            )
            record_agent_result_to_validation(
                self._traceability,
                project_id=request.project_id,
                result_id=result_trace_id,
                validation_id=uuid4(),
                metadata={"validation_status": validation_status.value},
            )

            if validation_status == AgentValidationStatus.ERROR and request.parameters.get(
                "fail_on_validation_error", False
            ):
                record.execution_status = AgentExecutionStatus.FAILED
                record.completed_at = datetime.now(UTC)
                record.error_metadata = {
                    "message": "Agent output failed validation checks",
                    "validation_status": validation_status.value,
                }
                return self._executions.update(record)

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
                        "agent_type": selected_type.value,
                        "user_request": request.user_request,
                    },
                )
                record.approval_request_id = approval.id
                record.execution_status = AgentExecutionStatus.REQUIRES_HUMAN_APPROVAL
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
        except FeatureAccessDeniedError:
            record.execution_status = AgentExecutionStatus.FAILED
            record.completed_at = datetime.now(UTC)
            record.error_metadata = {"message": "Upgrade entitlement required", "type": "FeatureAccessDeniedError"}
            self._executions.update(record)
            raise
        except Exception as exc:
            record.execution_status = AgentExecutionStatus.FAILED
            record.completed_at = datetime.now(UTC)
            record.error_metadata = {"message": str(exc), "type": exc.__class__.__name__}
            self._executions.update(record)
            raise

    def _enforce_entitlements(self, account_id: str, profile: AgentCapabilityProfile) -> None:
        for feature in profile.required_platform_features:
            self._entitlements.require_feature(account_id, feature)

    def _should_block_execution(
        self,
        *,
        request: AgentExecutionRequest,
        prompt_result: PromptGenerationResult,
        capability_profile: AgentCapabilityProfile,
    ) -> bool:
        if request.parameters.get("allow_missing_inputs"):
            return False
        if not capability_profile.blocks_on_missing_inputs:
            return False
        return bool(prompt_result.missing_information)

    def _create_blocked_execution(
        self,
        *,
        request: AgentExecutionRequest,
        actor_id: str,
        agent_definition: AgentDefinition,
        prompt_result: PromptGenerationResult,
        context_snapshot: dict[str, Any],
        orchestration_trace: list[dict[str, Any]],
    ) -> AgentExecutionRecord:
        agent_version = self._resolve_agent_version(agent_definition, request)
        record = self._executions.create(
            project_id=request.project_id,
            agent_definition_id=agent_definition.id,
            agent_version=agent_version,
            input_request={
                "user_request": request.user_request,
                "parameters": request.parameters,
                "prompt_generation": prompt_result.model_dump(),
                "orchestration_trace": orchestration_trace,
            },
            context_snapshot=context_snapshot,
            created_by=actor_id,
        )
        record.prompt_generation = prompt_result.model_dump()
        record.execution_status = AgentExecutionStatus.BLOCKED
        record.completed_at = datetime.now(UTC)
        record.error_metadata = {
            "message": "Required inputs are missing before execution can proceed",
            "missing_inputs": prompt_result.missing_information,
            "reason": "missing_required_input",
        }
        record.traceability_metadata = {
            "orchestration_trace": orchestration_trace,
            "blocked": True,
        }
        return self._executions.update(record)

    def _build_orchestration_trace(
        self,
        *,
        request: AgentExecutionRequest,
        context_snapshot: dict[str, Any],
        prompt_result: PromptGenerationResult,
        capability_profile: AgentCapabilityProfile,
    ) -> list[dict[str, Any]]:
        return [
            {"step": 1, "action": "receive_objective", "detail": request.user_request.strip()},
            {"step": 2, "action": "resolve_project_context", "detail": context_snapshot.get("project_name")},
            {
                "step": 3,
                "action": "retrieve_project_memory",
                "detail": context_snapshot.get("memory_total_count", 0),
            },
            {
                "step": 4,
                "action": "determine_capabilities",
                "detail": list(capability_profile.capabilities),
            },
            {
                "step": 5,
                "action": "construct_structured_task",
                "detail": prompt_result.generated_prompt[:500],
            },
            {
                "step": 6,
                "action": "select_agent",
                "detail": capability_profile.agent_type.value,
            },
            {
                "step": 7,
                "action": "planned_tools",
                "detail": prompt_result.available_tools,
            },
        ]

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

    def _resolve_agent_version(
        self,
        definition: AgentDefinition,
        request: AgentExecutionRequest,
    ) -> int:
        override = request.parameters.get("agent_version_override")
        if request.parameters.get("builder_test_mode") and isinstance(override, int):
            return override
        if request.parameters.get("builder_test_mode") and isinstance(override, str) and override.isdigit():
            return int(override)
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
        orchestration_status = agent_result.validation_information.get("orchestration_status")
        if orchestration_status in {"ERROR", "FAIL", "FAILED"}:
            return AgentValidationStatus.ERROR
        if orchestration_status in {"WARNING", "WARN"}:
            return AgentValidationStatus.WARNING

        capability_status = str(agent_result.validation_information.get("capability_status", "")).upper()
        if capability_status in {"NOT_IMPLEMENTED", "NOT_AVAILABLE", "REQUIRES_LOCAL_SOFTWARE", "FAILED"}:
            return AgentValidationStatus.REQUIRES_ENGINEER_REVIEW
        if capability_status in {"ERROR", "FAIL"}:
            return AgentValidationStatus.ERROR
        if capability_status in {"WARNING", "WARN"}:
            return AgentValidationStatus.WARNING

        validation_status = agent_result.validation_information.get("validation_status")
        if validation_status == "ERROR":
            return AgentValidationStatus.ERROR
        if validation_status in {"WARNING", "REQUIRES_ENGINEER_REVIEW"}:
            return AgentValidationStatus.WARNING
        if validation_status == "PASS":
            return AgentValidationStatus.PASS

        if agent_result.validation_information.get("stub"):
            return AgentValidationStatus.REQUIRES_ENGINEER_REVIEW
        if agent_result.validation_information.get("fabricated_results"):
            return AgentValidationStatus.ERROR
        if agent_result.confidence is not None and agent_result.confidence < 0.5:
            return AgentValidationStatus.WARNING
        return AgentValidationStatus.PASS

    def _apply_orchestration(
        self,
        *,
        project_id: UUID,
        request: AgentExecutionRequest,
        agent_result: AgentResult,
    ) -> AgentResult:
        if self._orchestration is None:
            return agent_result

        orchestration_result = self._orchestration.execute(
            OrchestrationTask(
                task_type="project.validate",
                project_id=project_id,
                payload={},
            )
        )
        validation_information = dict(agent_result.validation_information)
        validation_information["orchestration"] = orchestration_result.model_dump(mode="json")
        validation_information["orchestration_status"] = orchestration_result.status
        validation_information["orchestration_route"] = orchestration_result.route.value
        return agent_result.model_copy(update={"validation_information": validation_information})

    def _requires_approval(
        self,
        *,
        request: AgentExecutionRequest,
        agent_definition: AgentDefinition,
        capability_profile: AgentCapabilityProfile,
        agent_result: AgentResult,
    ) -> bool:
        if request.requires_approval is True:
            return True
        if capability_profile.requires_human_approval:
            return True
        if agent_definition.agent_type in AGENT_TYPES_REQUIRING_APPROVAL:
            return True
        return bool(agent_result.validation_information.get("requires_approval"))

    def build_context_snapshot(self, assembly: ProjectContextAssembly) -> dict[str, Any]:
        return self._build_scoped_context(assembly)

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
