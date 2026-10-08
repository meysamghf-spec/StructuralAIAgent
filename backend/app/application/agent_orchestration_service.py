"""Unified Structural AI Agent orchestration pipeline."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.application.agent_capability_catalog import AgentCapabilityProfile, get_agent_capability_profile
from app.application.agent_run_tool_payloads import (
    capability_tool_payload,
    iter_document_tool_events,
)
from app.application.agent_run_events import (
    EVENT_APPROVAL_REQUIRED,
    EVENT_CONTEXT,
    EVENT_FAILED,
    EVENT_STEP,
    EVENT_TOOL,
    EVENT_VALIDATION,
    AgentRunProgressSink,
    emit_progress,
    safe_stream_error,
)
from app.application.engineering_agent_handlers import (
    EngineeringAgentHandler,
    build_engineering_agent_handlers,
    new_trace_result_id,
)
from app.application.engineering_learning_service import EngineeringLearningService
from app.application.engineering_workflow_trace import engineering_workflow_trace
from app.application.engineering_task_workflow_service import EngineeringTaskWorkflowService
from app.application.engineering_task_execution_service import EngineeringTaskExecutionService
from app.application.entitlement_authorization_service import EntitlementAuthorizationService
from app.application.exceptions import (
    AgentHandlerNotFoundError,
    AgentNotExecutableError,
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
from app.domain.models.agent import (
    AgentDefinition,
    AgentDefinitionStatus,
    AgentVersion,
    AgentVersionStatus,
    EngineeringAgentType,
)
from app.domain.models.agent_runtime import (
    AgentExecutionRecord,
    AgentExecutionRequest,
    AgentExecutionStatus,
    AgentResult,
    AgentValidationStatus,
    PromptGenerationResult,
    is_awaiting_human_approval,
)
from app.domain.models.engineering_learning import (
    LEARNING_AUTHORITY,
    LearningRetrieval,
    agent_learning_query,
    approved_experience_block,
    attach_approved_experience,
    experience_context,
)
from app.domain.models.human_approval import ApprovalTargetType
from app.domain.models.engineering_task import EngineeringTask, EngineeringTaskStatus
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
        task_workflow_service: EngineeringTaskWorkflowService | None = None,
        task_execution_service: EngineeringTaskExecutionService | None = None,
        handlers: dict[EngineeringAgentType, EngineeringAgentHandler] | None = None,
        learning_service: EngineeringLearningService | None = None,
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
        self._task_workflow = task_workflow_service
        self._task_execution = task_execution_service
        self._handlers = handlers or build_engineering_agent_handlers()
        self._learning = learning_service

    def orchestrate(
        self,
        request: AgentExecutionRequest,
        *,
        actor_id: str,
        account_id: str,
        progress_sink: AgentRunProgressSink | None = None,
    ) -> AgentExecutionRecord:
        conversation_id = request.parameters.get("conversation_id")
        base = {"conversation_id": str(conversation_id) if conversation_id else None}
        emit_progress(
            progress_sink,
            EVENT_STEP,
            {**base, "step_id": "project_context", "name": "Loading project context", "status": "current"},
        )
        context_assembly = self._context.assemble(request.project_id)
        context_snapshot = self._build_scoped_context(context_assembly)
        attachment_context = request.parameters.get("attachment_context")
        if isinstance(attachment_context, dict):
            context_snapshot["chat_attachments"] = attachment_context
        emit_progress(
            progress_sink,
            EVENT_STEP,
            {**base, "step_id": "project_context", "name": "Loading project context", "status": "complete"},
        )
        emit_progress(
            progress_sink,
            EVENT_CONTEXT,
            {
                **base,
                "context": {
                    "conversation": conversation_id is not None,
                    "project": True,
                    "project_id": str(request.project_id),
                    "conversation_id": str(conversation_id) if conversation_id else None,
                },
            },
        )
        attachments = _attachment_entries(attachment_context)
        if attachments:
            emit_progress(
                progress_sink,
                EVENT_STEP,
                {**base, "step_id": "documents", "name": "Reading documents", "status": "current"},
            )
            emit_progress(
                progress_sink,
                EVENT_CONTEXT,
                {
                    **base,
                    "context": {
                        "conversation": conversation_id is not None,
                        "project": True,
                        "project_id": str(request.project_id),
                        "conversation_id": str(conversation_id) if conversation_id else None,
                        "files": [
                            {
                                "filename": item["filename"],
                                "file_type": item.get("file_type"),
                                "availability": item.get("availability"),
                            }
                            for item in attachments
                        ],
                        "indexed_document_count": sum(
                            1 for item in attachments if item.get("availability") == "indexed"
                        ),
                    },
                },
            )
            for tool_payload in iter_document_tool_events(attachments):
                emit_progress(progress_sink, EVENT_TOOL, {**base, "tool": tool_payload})
            emit_progress(
                progress_sink,
                EVENT_STEP,
                {**base, "step_id": "documents", "name": "Reading documents", "status": "complete"},
            )

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

        learning_retrieval = self._attach_approved_learning(
            request=request,
            account_id=account_id,
            agent_id=selected_type.value,
            context_snapshot=context_snapshot,
        )

        capability_profile = get_agent_capability_profile(selected_type)
        self._enforce_entitlements(account_id, capability_profile)
        emit_progress(
            progress_sink,
            EVENT_TOOL,
            {
                **base,
                "tool": capability_tool_payload(
                    agent_type=selected_type.value,
                    status="current",
                ),
            },
        )

        if prompt_result is None or (
            learning_retrieval is not None and learning_retrieval.records
        ):
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

        engineering_task: EngineeringTask | None = None
        resume_execution_id = request.parameters.get("resume_execution_id")
        if self._task_workflow is not None:
            if resume_execution_id:
                prior = self._executions.get_by_id(UUID(str(resume_execution_id)))
                prior_task = (
                    prior.traceability_metadata.get("engineering_task")
                    if prior is not None
                    else None
                )
                if isinstance(prior_task, dict):
                    engineering_task = EngineeringTask.model_validate(prior_task)
                    engineering_task = self._task_workflow.refresh_task_for_resume(
                        engineering_task,
                        supplemental_request=request.user_request,
                        context_snapshot=context_snapshot,
                        prompt_result=prompt_result,
                        attachment_context=(
                            attachment_context if isinstance(attachment_context, dict) else None
                        ),
                    )
            if engineering_task is None:
                engineering_task = self._task_workflow.build_task(
                    user_request=request.user_request,
                    project_id=request.project_id,
                    context_snapshot=context_snapshot,
                    prompt_result=prompt_result,
                    conversation_id=str(request.parameters.get("conversation_id"))
                    if request.parameters.get("conversation_id")
                    else None,
                    account_id=account_id,
                    attachment_context=(
                        attachment_context if isinstance(attachment_context, dict) else None
                    ),
                )

            use_multi_step = (
                self._task_execution is not None
                and self._task_execution.should_execute_multi_step(engineering_task)
            )
            if not use_multi_step:
                engineering_task = self._task_workflow.execute_preparatory_steps(
                    engineering_task,
                    project_id=request.project_id,
                    context_snapshot=context_snapshot,
                )
            orchestration_trace.append(
                {
                    "step": 8,
                    "action": "construct_engineering_task",
                    "detail": {
                        "task_id": str(engineering_task.id),
                        "status": engineering_task.status.value,
                        "step_count": len(engineering_task.steps),
                        "multi_step_execution": use_multi_step,
                    },
                }
            )
        else:
            use_multi_step = False

        if self._should_block_execution(
            request=request,
            prompt_result=prompt_result,
            capability_profile=capability_profile,
        ):
            record = self._create_blocked_execution(
                request=request,
                actor_id=actor_id,
                agent_definition=agent_definition,
                prompt_result=prompt_result,
                context_snapshot=context_snapshot,
                orchestration_trace=orchestration_trace,
                engineering_task=engineering_task,
            )
            emit_progress(
                progress_sink,
                EVENT_FAILED,
                {
                    **base,
                    "run_id": str(record.id),
                    "error": safe_stream_error(
                        title="Additional input is required",
                        reason=record.error_metadata.get(
                            "message",
                            "Required inputs are missing before execution can proceed",
                        )
                        if isinstance(record.error_metadata, dict)
                        else "Required inputs are missing before execution can proceed",
                    ),
                },
            )
            return record

        agent_version, agent_version_row = self._resolve_executable_version(agent_definition, request)
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
        record.traceability_metadata = {
            "orchestration_trace": orchestration_trace,
            **_execution_provenance(
                definition=agent_definition,
                version_number=agent_version,
                version_row=agent_version_row,
                project_id=request.project_id,
                context_snapshot=context_snapshot,
                run_id=record.id,
                qa_status=None,
                learning_record_ids=_learning_record_ids(learning_retrieval),
                attachment_file_ids=_bound_attachment_ids(request.parameters),
            ),
        }
        record = self._executions.update(record)

        record.execution_status = AgentExecutionStatus.RUNNING
        record.started_at = datetime.now(UTC)
        record = self._executions.update(record)
        base["run_id"] = str(record.id)
        emit_progress(
            progress_sink,
            EVENT_STEP,
            {**base, "step_id": "execute", "name": "Running engineering workflow", "status": "current"},
        )

        try:
            if use_multi_step and engineering_task is not None and self._task_execution is not None:
                outcome = self._task_execution.execute_workflow(
                    task=engineering_task,
                    project_id=request.project_id,
                    user_request=request.user_request,
                    context_snapshot=context_snapshot,
                    parameters=request.parameters,
                    agent_definition=agent_definition,
                    actor_id=actor_id,
                    execution_id=record.id,
                    resume=bool(resume_execution_id),
                )
                agent_result = self._apply_orchestration(
                    project_id=request.project_id,
                    request=request,
                    agent_result=outcome.agent_result,
                )
                engineering_task = outcome.task
                if outcome.selected_agent_type is not None:
                    selected_type = outcome.selected_agent_type
            else:
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
            emit_progress(
                progress_sink,
                EVENT_STEP,
                {**base, "step_id": "execute", "name": "Running engineering workflow", "status": "complete"},
            )
            emit_progress(
                progress_sink,
                EVENT_STEP,
                {**base, "step_id": "validate", "name": "Validating results", "status": "current"},
            )
            validation_status = self._validate_result(agent_result)
            emit_progress(
                progress_sink,
                EVENT_VALIDATION,
                {**base, "validation_status": validation_status.value},
            )
            emit_progress(
                progress_sink,
                EVENT_STEP,
                {**base, "step_id": "validate", "name": "Validating results", "status": "complete"},
            )
            emit_progress(
                progress_sink,
                EVENT_TOOL,
                {
                    **base,
                    "tool": capability_tool_payload(
                        agent_type=selected_type.value,
                        status="complete",
                        agent_result=agent_result,
                        validation_status=validation_status.value,
                    ),
                },
            )
            requires_approval = self._requires_approval(
                request=request,
                agent_definition=agent_definition,
                capability_profile=capability_profile,
                agent_result=agent_result,
            )
            if use_multi_step and engineering_task is not None and self._task_execution is not None:
                requires_approval = requires_approval or (
                    engineering_task.status == EngineeringTaskStatus.WAITING_FOR_APPROVAL
                )

            agent_result = self._annotate_with_learning(agent_result, learning_retrieval)
            if (
                self._learning is not None
                and learning_retrieval is not None
                and learning_retrieval.records
            ):
                self._learning.record_use(
                    project_id=request.project_id,
                    task_id=record.id,
                    retrieval=learning_retrieval,
                )

            record.agent_result = agent_result
            record.output = agent_result.structured_output
            record.validation_status = validation_status

            request_trace_id = uuid4()
            result_trace_id = new_trace_result_id()
            learning_trace: dict[str, Any] = {}
            if learning_retrieval is not None and learning_retrieval.records:
                learning_trace = {
                    "learning_record_ids": [str(item.id) for item in learning_retrieval.records],
                    "learning_explanation": learning_retrieval.explanation,
                    "learning_authority": LEARNING_AUTHORITY,
                    "approved_engineering_experience": approved_experience_block(
                        learning_retrieval.records
                    ),
                }
            record.traceability_metadata = {
                **record.traceability_metadata,
                "request_trace_id": str(request_trace_id),
                "result_trace_id": str(result_trace_id),
                "selected_agent_type": selected_type.value,
                "pem_version": context_snapshot.get("pem_version"),
                "pem_snapshot_id": context_snapshot.get("pem_snapshot_id"),
                "qa_status": validation_status.value,
                "run_id": str(record.id),
                **learning_trace,
                **engineering_workflow_trace(agent_result.structured_output),
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
                updated = self._executions.update(record)
                emit_progress(
                    progress_sink,
                    EVENT_FAILED,
                    {
                        **base,
                        "run_id": str(updated.id),
                        "error": safe_stream_error(
                            title="Engineering workflow failed",
                            reason="Agent output failed validation checks",
                        ),
                    },
                )
                return updated

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
                emit_progress(
                    progress_sink,
                    EVENT_APPROVAL_REQUIRED,
                    {
                        **base,
                        "run_id": str(record.id),
                        "approval_request_id": str(approval.id),
                    },
                )
                record_agent_result_to_approval(
                    self._traceability,
                    project_id=request.project_id,
                    result_id=result_trace_id,
                    approval_id=approval.id,
                )
            else:
                if use_multi_step and engineering_task is not None and self._task_execution is not None:
                    record.execution_status = outcome.execution_status
                    if record.execution_status == AgentExecutionStatus.COMPLETED:
                        record.completed_at = datetime.now(UTC)
                else:
                    record.execution_status = AgentExecutionStatus.COMPLETED
                    record.completed_at = datetime.now(UTC)

            if engineering_task is not None and self._task_workflow is not None:
                if use_multi_step:
                    record.traceability_metadata = {
                        **record.traceability_metadata,
                        "engineering_task": engineering_task.model_dump(mode="json"),
                    }
                else:
                    engineering_task = self._task_workflow.finalize_with_handler_result(
                        engineering_task,
                        agent_type=selected_type,
                        agent_result=record.agent_result,
                        execution_status=record.execution_status,
                        requires_approval=requires_approval,
                        execution_id=record.id,
                    )
                    record.traceability_metadata = {
                        **record.traceability_metadata,
                        "engineering_task": engineering_task.model_dump(mode="json"),
                    }
                if engineering_task.artifacts and record.agent_result is not None:
                    merged = list(record.agent_result.generated_artifacts)
                    for artifact in engineering_task.artifacts:
                        if artifact.generation_status == "generated":
                            merged.append(artifact.model_dump(mode="json"))
                    record.agent_result = record.agent_result.model_copy(
                        update={"generated_artifacts": merged[:10]}
                    )

            return self._executions.update(record)
        except FeatureAccessDeniedError:
            record.execution_status = AgentExecutionStatus.FAILED
            record.completed_at = datetime.now(UTC)
            record.error_metadata = {"message": "Upgrade entitlement required", "type": "FeatureAccessDeniedError"}
            self._executions.update(record)
            emit_progress(
                progress_sink,
                EVENT_TOOL,
                {
                    **base,
                    "tool": capability_tool_payload(
                        agent_type=selected_type.value,
                        status="error",
                        error_message="This capability is not available for this account.",
                    ),
                },
            )
            emit_progress(
                progress_sink,
                EVENT_FAILED,
                {
                    **base,
                    "run_id": str(record.id),
                    "error": safe_stream_error(
                        title="Engineering workflow failed",
                        reason="This capability is not available for this account.",
                    ),
                },
            )
            raise
        except Exception as exc:
            record.execution_status = AgentExecutionStatus.FAILED
            record.completed_at = datetime.now(UTC)
            record.error_metadata = {"message": str(exc), "type": exc.__class__.__name__}
            self._executions.update(record)
            emit_progress(
                progress_sink,
                EVENT_TOOL,
                {
                    **base,
                    "tool": capability_tool_payload(
                        agent_type=selected_type.value,
                        status="error",
                        error_message="The agent could not complete this engineering step.",
                    ),
                },
            )
            emit_progress(
                progress_sink,
                EVENT_FAILED,
                {
                    **base,
                    "run_id": str(record.id),
                    "error": safe_stream_error(
                        title="Engineering workflow failed",
                        reason="The agent could not complete this engineering step.",
                    ),
                },
            )
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
        engineering_task=None,
    ) -> AgentExecutionRecord:
        agent_version, agent_version_row = self._resolve_executable_version(agent_definition, request)
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
        if engineering_task is not None and self._task_workflow is not None:
            engineering_task = self._task_workflow.finalize_with_handler_result(
                engineering_task,
                agent_type=prompt_result.selected_agent_type,
                agent_result=None,
                execution_status=AgentExecutionStatus.BLOCKED,
                requires_approval=False,
            )
        record.error_metadata = {
            "message": "Required inputs are missing before execution can proceed",
            "missing_inputs": (
                engineering_task.missing_required_inputs
                if engineering_task is not None
                else prompt_result.missing_information
            ),
            "reason": "missing_required_input",
        }
        trace_metadata = {
            "orchestration_trace": orchestration_trace,
            "blocked": True,
            **_execution_provenance(
                definition=agent_definition,
                version_number=agent_version,
                version_row=agent_version_row,
                project_id=request.project_id,
                context_snapshot=context_snapshot,
                run_id=record.id,
                qa_status=None,
                learning_record_ids=[],
                attachment_file_ids=_bound_attachment_ids(request.parameters),
            ),
        }
        if engineering_task is not None:
            trace_metadata["engineering_task"] = engineering_task.model_dump(mode="json")
        record.traceability_metadata = trace_metadata
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

    def _resolve_executable_version(
        self,
        definition: AgentDefinition,
        request: AgentExecutionRequest,
    ) -> tuple[int, AgentVersion | None]:
        version_number = self._resolve_agent_version(definition, request)
        version_row = self._versions.get_by_definition_and_version(definition.id, version_number)
        self._ensure_project_agent_executable(definition, request, version_row)
        return version_number, version_row

    def _ensure_project_agent_executable(
        self,
        definition: AgentDefinition,
        request: AgentExecutionRequest,
        version_row: AgentVersion | None,
    ) -> None:
        """Project assistants run in production only from the published version.

        Platform agents without a project stay on the existing handler path.
        Builder tests may execute a draft without publishing it.
        """

        if definition.project_id is None:
            return
        if definition.status == AgentDefinitionStatus.ARCHIVED:
            raise AgentNotExecutableError(
                definition.id,
                "Archived assistants cannot start new executions. Historical runs remain available.",
            )
        if definition.status == AgentDefinitionStatus.DISABLED or definition.configuration.get("enabled") is False:
            raise AgentNotExecutableError(
                definition.id,
                "This assistant is disabled and cannot start a new execution.",
            )
        parameters = request.parameters if isinstance(request.parameters, dict) else {}
        if parameters.get("builder_test_mode") is True:
            if version_row is None or version_row.status not in {
                AgentVersionStatus.DRAFT,
                AgentVersionStatus.INACTIVE,
            }:
                raise AgentNotExecutableError(
                    definition.id,
                    "Only a draft or inactive version can be tested.",
                    details={"agent_version": version_row.version if version_row else None},
                )
            return
        if version_row is None or version_row.status != AgentVersionStatus.ACTIVE:
            raise AgentNotExecutableError(
                definition.id,
                "A draft assistant version cannot execute as a published production agent.",
                details={
                    "agent_version": version_row.version if version_row else None,
                    "version_status": version_row.status.value if version_row else None,
                },
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
        if capability_status in {"MISSING_REQUIRED_INPUT", "INVALID_INPUT", "UNSUPPORTED_CODE"}:
            return AgentValidationStatus.WARNING
        if capability_status in {"ERROR", "FAIL"}:
            return AgentValidationStatus.ERROR
        if capability_status in {"WARNING", "WARN"}:
            return AgentValidationStatus.WARNING

        validation_status = agent_result.validation_information.get("validation_status")
        if validation_status == "ERROR":
            return AgentValidationStatus.ERROR
        if validation_status == "FAIL":
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
        explicit = agent_result.validation_information.get("requires_approval")
        if explicit is False:
            return False
        if capability_profile.requires_human_approval:
            return True
        if agent_definition.agent_type in AGENT_TYPES_REQUIRING_APPROVAL:
            return True
        return bool(explicit)

    def build_context_snapshot(self, assembly: ProjectContextAssembly) -> dict[str, Any]:
        return self._build_scoped_context(assembly)

    def _attach_approved_learning(
        self,
        *,
        request: AgentExecutionRequest,
        account_id: str,
        agent_id: str,
        context_snapshot: dict[str, Any],
    ) -> LearningRetrieval | None:
        if self._learning is None:
            return None
        parameters = request.parameters if isinstance(request.parameters, dict) else {}
        query = agent_learning_query(agent_id, parameters)
        retrieval = self._learning.retrieve(
            project_id=request.project_id,
            account_id=account_id,
            agent_id=agent_id,
            task_type=query["task_type"],
            element_type=query["element_type"],
            analysis_type=query["analysis_type"],
            design_type=query["design_type"],
            apply_operation=query["apply_operation"],
        )
        if not retrieval.records:
            return retrieval
        context_snapshot["approved_engineering_experience"] = approved_experience_block(
            retrieval.records
        )
        context_snapshot["approved_learning"] = [
            experience_context(record) for record in retrieval.records
        ]
        context_snapshot["learning_explanation"] = retrieval.explanation
        context_snapshot["learning_authority"] = retrieval.authority
        context_snapshot["learning_record_ids"] = [str(record.id) for record in retrieval.records]
        return retrieval

    def _annotate_with_learning(
        self,
        agent_result: AgentResult,
        retrieval: LearningRetrieval | None,
    ) -> AgentResult:
        if retrieval is None or not retrieval.records:
            return agent_result
        output = attach_approved_experience(agent_result.structured_output, retrieval.records)
        recommendations = list(agent_result.recommendations)
        recommendations.append(retrieval.explanation)
        return agent_result.model_copy(
            update={
                "structured_output": output,
                "recommendations": recommendations,
            }
        )

    def _build_scoped_context(self, assembly: ProjectContextAssembly) -> dict[str, Any]:
        return {
            "project_id": str(assembly.project_id),
            "project_name": assembly.project_name,
            "pem_version": assembly.pem_version,
            "pem_snapshot_id": str(assembly.pem_snapshot_id) if assembly.pem_snapshot_id else None,
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


def _learning_record_ids(retrieval: LearningRetrieval | None) -> list[str]:
    if retrieval is None:
        return []
    return [str(item.id) for item in retrieval.records]


def _bound_attachment_ids(parameters: dict[str, Any] | None) -> list[str]:
    if not isinstance(parameters, dict):
        return []
    bundle = parameters.get("attachment_context")
    ids: list[str] = []
    if isinstance(bundle, dict):
        for item in bundle.get("attachments") or []:
            if isinstance(item, dict) and item.get("file_id"):
                ids.append(str(item["file_id"]))
    if ids:
        return ids
    raw_ids = parameters.get("attachment_file_ids") or []
    if isinstance(raw_ids, list):
        return [str(item) for item in raw_ids if item]
    return []


def _execution_provenance(
    *,
    definition: AgentDefinition,
    version_number: int,
    version_row: AgentVersion | None,
    project_id: UUID,
    context_snapshot: dict[str, Any],
    run_id: UUID,
    qa_status: str | None,
    learning_record_ids: list[str],
    attachment_file_ids: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "agent_id": str(definition.id),
        "agent_version": version_number,
        "agent_version_id": str(version_row.id) if version_row is not None else None,
        "project_id": str(project_id),
        "pem_snapshot_id": context_snapshot.get("pem_snapshot_id"),
        "pem_version": context_snapshot.get("pem_version"),
        "run_id": str(run_id),
        "qa_status": qa_status,
        "learning_record_ids": learning_record_ids,
        "attachment_file_ids": list(attachment_file_ids or []),
    }


def _attachment_entries(attachment_context: Any) -> list[dict[str, Any]]:
    if not isinstance(attachment_context, dict):
        return []
    raw_entries = attachment_context.get("attachments")
    if not isinstance(raw_entries, list):
        return []
    return [
        item
        for item in raw_entries
        if isinstance(item, dict) and item.get("filename")
    ]
