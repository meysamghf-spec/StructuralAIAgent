"""Dependency-aware multi-step engineering task execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from app.application.architectural_concept_service import ArchitecturalConceptService
from app.application.engineering_agent_handlers import EngineeringAgentHandler
from app.application.engineering_task_workflow_service import EngineeringTaskWorkflowService
from app.application.hybrid_orchestration_service import HybridOrchestrationService
from app.application.integration_service import IntegrationService
from app.application.structural_solver_integration_service import StructuralSolverIntegrationService
from app.domain.models.agent import AgentDefinition, EngineeringAgentType
from app.domain.models.agent_runtime import AgentExecutionStatus, AgentResult, AgentValidationStatus
from app.domain.models.cad import CadDrawingRequest, CadOutputFormat
from app.domain.models.engineering_task import (
    EngineeringTask,
    EngineeringTaskArtifact,
    EngineeringTaskStatus,
    EngineeringTaskStep,
    WorkflowStepStatus,
)
from app.domain.models.integration import IntegrationSoftware
from app.domain.models.orchestration import OrchestrationTask
from app.infrastructure.config import get_settings

_INTEGRATION_CAPABILITY_MAP = {
    "integration.etabs": IntegrationSoftware.ETABS,
    "integration.sap2000": IntegrationSoftware.SAP2000,
    "integration.safe": IntegrationSoftware.SAFE,
}

_SUCCESS_CAPABILITY_STATUSES = {
    "SUCCESS",
    "READY_FOR_MODELING_WORKFLOW",
    "READY_FOR_SEISMIC_REVIEW",
    "PASS",
    "COMPLETED",
}

_UNSUPPORTED_CAPABILITY_STATUSES = {
    "NOT_IMPLEMENTED",
    "NOT_AVAILABLE",
    "UNAVAILABLE",
    "REQUIRES_LOCAL_SOFTWARE",
    "REQUIRES_SOLVER",
    "NOT_INSTALLED",
    "MISSING_MODEL",
}


@dataclass(frozen=True)
class WorkflowExecutionOutcome:
    task: EngineeringTask
    agent_result: AgentResult
    requires_approval: bool
    approval_step_id: str | None
    execution_status: AgentExecutionStatus
    selected_agent_type: EngineeringAgentType | None


class EngineeringTaskExecutionService:
    def __init__(
        self,
        *,
        workflow_service: EngineeringTaskWorkflowService,
        hybrid_orchestration: HybridOrchestrationService | None = None,
        integration_service: IntegrationService | None = None,
        solver_integration: StructuralSolverIntegrationService | None = None,
        architectural_concept_service: ArchitecturalConceptService | None = None,
        cad_generation_service=None,
        handlers: dict[EngineeringAgentType, EngineeringAgentHandler] | None = None,
    ) -> None:
        self._workflow = workflow_service
        self._hybrid = hybrid_orchestration
        self._integration = integration_service
        self._solver = solver_integration
        self._architectural = architectural_concept_service or ArchitecturalConceptService()
        self._cad = cad_generation_service
        self._handlers = handlers or {}

    def should_execute_multi_step(self, task: EngineeringTask) -> bool:
        executable_agent_steps = sum(
            1 for step in task.steps if step.capability_kind == "agent" and step.agent_type is not None
        )
        integration_steps = sum(1 for step in task.steps if step.capability_kind == "integration")
        deliverable_steps = sum(
            1
            for step in task.steps
            if step.capability_kind in {"deliverable", "architectural"}
            or step.capability == "architectural.concept"
        )
        return executable_agent_steps + integration_steps + deliverable_steps > 1

    def execute_workflow(
        self,
        *,
        task: EngineeringTask,
        project_id: UUID,
        user_request: str,
        context_snapshot: dict[str, Any],
        parameters: dict[str, Any],
        agent_definition: AgentDefinition,
        actor_id: str,
        execution_id: UUID | None = None,
        resume: bool = False,
    ) -> WorkflowExecutionOutcome:
        if execution_id is not None:
            task.execution_id = execution_id
        task.status = EngineeringTaskStatus.RUNNING
        task.shared_context.setdefault("workflow_parameters", {}).update(parameters)
        if parameters.get("allow_missing_inputs"):
            for step in task.steps:
                if step.status == WorkflowStepStatus.BLOCKED and step.capability_kind in {
                    "input_validation",
                    "agent",
                }:
                    step.status = WorkflowStepStatus.EXECUTABLE
        if resume and task.resume_from_step_id:
            task.paused_step_id = None

        task = self._workflow.evaluate_steps(task, context_snapshot)
        self._record_unavailable_integrations(
            task=task,
            project_id=project_id,
            actor_id=actor_id,
            parameters=parameters,
        )
        if parameters.get("allow_missing_inputs"):
            for step in task.steps:
                if step.status == WorkflowStepStatus.BLOCKED and step.capability_kind in {
                    "input_validation",
                    "agent",
                    "architectural",
                    "deterministic_service",
                }:
                    step.status = WorkflowStepStatus.EXECUTABLE
        ordered_steps = self._order_steps(task.steps)
        aggregate_recommendations: list[str] = []
        aggregate_artifacts: list[dict[str, Any]] = []
        aggregate_validation: dict[str, Any] = {"workflow_steps": []}
        last_agent_type = task.primary_agent_type or agent_definition.agent_type
        requires_approval = False
        approval_step_id: str | None = None

        start_index = 0
        if resume and task.resume_from_step_id:
            for index, step in enumerate(ordered_steps):
                if step.step_id == task.resume_from_step_id:
                    start_index = index
                    break

        for step in ordered_steps[start_index:]:
            if step.status == WorkflowStepStatus.EXECUTED:
                continue
            if step.status in {WorkflowStepStatus.UNSUPPORTED, WorkflowStepStatus.BLOCKED}:
                continue
            if not self._dependencies_satisfied(step, task):
                step.status = WorkflowStepStatus.BLOCKED
                step.blocking_reason = "Waiting for upstream workflow steps."
                continue

            if step.status != WorkflowStepStatus.EXECUTABLE:
                continue

            step_result = self._execute_step(
                step=step,
                task=task,
                project_id=project_id,
                user_request=user_request,
                context_snapshot=context_snapshot,
                parameters=parameters,
                actor_id=actor_id,
            )
            aggregate_validation["workflow_steps"].append(
                {
                    "step_id": step.step_id,
                    "title": step.title,
                    "status": step.status.value,
                    "capability": step.capability,
                }
            )

            if step.execution_result:
                recommendations = step.execution_result.get("recommendations")
                if isinstance(recommendations, list):
                    aggregate_recommendations.extend(str(item) for item in recommendations[:3])

            for artifact in step.step_artifacts:
                task.artifacts.append(artifact)
                if artifact.generation_status == "generated":
                    aggregate_artifacts.append(artifact.model_dump(mode="json"))

            if step_result.get("pause_for_approval"):
                requires_approval = True
                approval_step_id = step.step_id
                task.paused_step_id = step.step_id
                task.resume_from_step_id = step.step_id
                task.status = EngineeringTaskStatus.WAITING_FOR_APPROVAL
                break

            if step.status == WorkflowStepStatus.FAILED:
                task.status = EngineeringTaskStatus.FAILED
                break

            if step.agent_type is not None:
                last_agent_type = step.agent_type

        if not requires_approval:
            task = self._workflow.evaluate_steps(task, context_snapshot)
            task.status = self._workflow._derive_task_status(task)  # noqa: SLF001

        agent_result = self._build_aggregate_result(
            task=task,
            selected_agent_type=last_agent_type,
            aggregate_recommendations=aggregate_recommendations,
            aggregate_artifacts=aggregate_artifacts,
            aggregate_validation=aggregate_validation,
        )
        execution_status = (
            AgentExecutionStatus.REQUIRES_HUMAN_APPROVAL
            if requires_approval
            else AgentExecutionStatus.COMPLETED
            if task.status
            in {EngineeringTaskStatus.COMPLETED, EngineeringTaskStatus.PARTIALLY_COMPLETED}
            else AgentExecutionStatus.FAILED
            if task.status == EngineeringTaskStatus.FAILED
            else AgentExecutionStatus.BLOCKED
            if task.status == EngineeringTaskStatus.WAITING_FOR_INPUT
            else AgentExecutionStatus.COMPLETED
        )
        return WorkflowExecutionOutcome(
            task=task,
            agent_result=agent_result,
            requires_approval=requires_approval,
            approval_step_id=approval_step_id,
            execution_status=execution_status,
            selected_agent_type=last_agent_type,
        )

    def resume_after_approval(
        self,
        *,
        task: EngineeringTask,
        project_id: UUID,
        user_request: str,
        context_snapshot: dict[str, Any],
        parameters: dict[str, Any],
        agent_definition: AgentDefinition,
        actor_id: str,
        execution_id: UUID,
    ) -> WorkflowExecutionOutcome:
        if task.paused_step_id:
            paused = self._find_step(task, task.paused_step_id)
            if paused is not None and paused.status != WorkflowStepStatus.EXECUTED:
                paused.status = WorkflowStepStatus.EXECUTED
        task.resume_from_step_id = task.paused_step_id
        return self.execute_workflow(
            task=task,
            project_id=project_id,
            user_request=user_request,
            context_snapshot=context_snapshot,
            parameters=parameters,
            agent_definition=agent_definition,
            actor_id=actor_id,
            execution_id=execution_id,
            resume=True,
        )

    def _execute_step(
        self,
        *,
        step: EngineeringTaskStep,
        task: EngineeringTask,
        project_id: UUID,
        user_request: str,
        context_snapshot: dict[str, Any],
        parameters: dict[str, Any],
        actor_id: str,
    ) -> dict[str, Any]:
        if step.capability == "project.validate":
            return self._execute_project_validate(step, task, project_id)
        if step.capability == "input.validation":
            step.status = WorkflowStepStatus.EXECUTED
            step.execution_result = {
                "missing_inputs": task.missing_required_inputs,
                "proceeded_with_gaps": bool(parameters.get("allow_missing_inputs")),
            }
            step.outputs = {"inputs_reviewed": True}
            return {}
        if step.capability == "document.review":
            return self._execute_document_review(step, task, context_snapshot)
        if step.capability == "architectural.concept":
            return self._execute_architectural_concept(step, task, project_id, user_request)
        if step.capability_kind == "integration":
            return self._execute_integration(step, task, project_id, actor_id, parameters)
        if step.capability_kind == "agent" and step.agent_type is not None:
            return self._execute_agent_step(
                step=step,
                task=task,
                project_id=project_id,
                user_request=user_request,
                context_snapshot=context_snapshot,
                parameters=parameters,
                actor_id=actor_id,
            )
        step.status = WorkflowStepStatus.UNSUPPORTED
        step.blocking_reason = f"No executor registered for capability {step.capability}."
        return {}

    def _execute_project_validate(
        self,
        step: EngineeringTaskStep,
        task: EngineeringTask,
        project_id: UUID,
    ) -> dict[str, Any]:
        if self._hybrid is None:
            step.status = WorkflowStepStatus.UNSUPPORTED
            step.blocking_reason = "Validation service is not configured."
            return {}
        result = self._hybrid.execute(
            OrchestrationTask(task_type="project.validate", project_id=project_id, payload={})
        )
        step.status = WorkflowStepStatus.EXECUTED
        step.execution_result = result.model_dump(mode="json")
        step.outputs = {"validation_status": result.status}
        task.shared_context["validation_status"] = result.status
        return {}

    def _execute_document_review(
        self,
        step: EngineeringTaskStep,
        task: EngineeringTask,
        context_snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        attachments = context_snapshot.get("chat_attachments", {}).get("attachments", [])
        previews = [
            item.get("text_preview")
            for item in attachments
            if isinstance(item, dict) and item.get("text_preview")
        ]
        step.status = WorkflowStepStatus.EXECUTED if previews or task.input_file_ids else WorkflowStepStatus.BLOCKED
        if step.status == WorkflowStepStatus.BLOCKED:
            step.blocking_reason = "Attached documents do not contain extracted text context."
            return {}
        step.execution_result = {
            "reviewed_file_ids": task.input_file_ids,
            "extracted_preview_count": len(previews),
        }
        step.outputs = {"document_context_available": True}
        task.shared_context["document_context_available"] = True
        return {}

    def _execute_architectural_concept(
        self,
        step: EngineeringTaskStep,
        task: EngineeringTask,
        project_id: UUID,
        user_request: str,
    ) -> dict[str, Any]:
        concept = self._architectural.derive_concept(user_request)
        task.assumptions.extend(self._architectural.concept_to_assumptions(concept))
        step.execution_result = concept.model_dump(mode="json")
        step.outputs = {"architectural_concept": concept.model_dump(mode="json")}
        task.shared_context["architectural_concept"] = concept.model_dump(mode="json")
        step.status = WorkflowStepStatus.EXECUTED

        dxf_payload = self._architectural.render_zoning_dxf(concept)
        if dxf_payload is None:
            step.limitations = list(concept.limitations)
            return {}

        output_dir = Path(get_settings().resolved_file_storage_root) / "cad" / str(project_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        file_path = output_dir / f"architectural_zoning_{task.id}.dxf"
        file_path.write_text(str(dxf_payload["content"]), encoding="utf-8")
        artifact = EngineeringTaskArtifact(
            artifact_id=f"arch-{task.id}",
            artifact_type="architectural_zoning_dxf",
            filename=str(dxf_payload["filename"]),
            generation_status="generated",
            producing_capability="architectural.concept",
            source_step_id=step.step_id,
            input_provenance=[user_request[:120]],
            validation_status="SCHEMATIC",
            href=str(file_path),
        )
        step.step_artifacts.append(artifact)
        step.outputs["architectural_dxf_path"] = str(file_path)
        task.shared_context["architectural_dxf_path"] = str(file_path)
        return {}

    def _record_unavailable_integrations(
        self,
        *,
        task: EngineeringTask,
        project_id: UUID,
        actor_id: str,
        parameters: dict[str, Any],
    ) -> None:
        """Persist a named solver that the plan already knows cannot run.

        Planning marks missing local software as unsupported before the step
        executes. The attempt is still an integration record tied to this project
        and the current PEM, with no engineering results attached.
        """
        if self._solver is None:
            return
        for step in task.steps:
            if step.capability_kind != "integration" or step.status != WorkflowStepStatus.UNSUPPORTED:
                continue
            if step.outputs.get("integration_execution_id"):
                continue
            software = _INTEGRATION_CAPABILITY_MAP.get(step.capability)
            if software is None:
                continue
            recorded = self._solver.record_unavailable_analysis(
                project_id,
                software,
                analysis_type=str(parameters.get("analysis_type") or "STATIC"),
                parameters=parameters,
                created_by=actor_id,
            )
            availability = str(recorded.outputs.get("solver_status") or recorded.status.value)
            step.execution_result = {
                "capability_status": availability,
                "message": recorded.message,
                "integration_execution_id": str(recorded.id),
                "engineering_results_available": False,
            }
            step.outputs = {
                "integration_execution_id": str(recorded.id),
                "solver": software.value,
                "solver_status": availability,
                "engineering_results_available": False,
            }
            task.shared_context.update(step.outputs)

    def _execute_integration(
        self,
        step: EngineeringTaskStep,
        task: EngineeringTask,
        project_id: UUID,
        actor_id: str,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        software = _INTEGRATION_CAPABILITY_MAP.get(step.capability)
        if software is None or self._solver is None:
            step.status = WorkflowStepStatus.UNSUPPORTED
            step.blocking_reason = "Integration capability is not configured."
            return {}

        capability = self._solver.get_capability(software)
        if capability.availability.value != "AVAILABLE":
            recorded = self._solver.record_unavailable_analysis(
                project_id,
                software,
                analysis_type=str(parameters.get("analysis_type") or "STATIC"),
                parameters=parameters,
                created_by=actor_id,
            )
            step.status = WorkflowStepStatus.UNSUPPORTED
            step.limitations = [capability.message or capability.availability.value]
            step.execution_result = {
                "capability_status": capability.availability.value,
                "message": capability.message,
                "integration_execution_id": str(recorded.id),
                "engineering_results_available": False,
            }
            step.outputs = {
                "integration_execution_id": str(recorded.id),
                "solver": software.value,
                "solver_status": capability.availability.value,
                "engineering_results_available": False,
            }
            task.shared_context.update(step.outputs)
            return {}

        if step.step_id == "etabs_model" or (
            step.capability == "integration.etabs" and "model" in step.title.lower()
        ):
            export_execution = self._solver.export_model(project_id, software, created_by=actor_id)
            step.status = (
                WorkflowStepStatus.EXECUTED
                if export_execution.status.value == "SUCCESS"
                else WorkflowStepStatus.UNSUPPORTED
            )
            step.execution_result = export_execution.model_dump(mode="json")
            step.outputs = {
                "integration_execution_id": str(export_execution.id),
                "software": software.value,
            }
            task.shared_context["etabs_export_execution_id"] = str(export_execution.id)
            if export_execution.metadata.get("external_model_path"):
                artifact = EngineeringTaskArtifact(
                    artifact_id=str(export_execution.id),
                    artifact_type="etabs_model",
                    filename=str(export_execution.metadata.get("external_model_path")),
                    generation_status="generated" if step.status == WorkflowStepStatus.EXECUTED else "unavailable",
                    producing_capability=step.capability,
                    source_step_id=step.step_id,
                    input_provenance=["PEM export"],
                )
                step.step_artifacts.append(artifact)
            return {}

        analysis_type = str(parameters.get("analysis_type") or "LATERAL")
        analysis_run_id = task.shared_context.get("analysis_run_id")
        if isinstance(analysis_run_id, str):
            analysis_run_id = UUID(analysis_run_id)
        else:
            analysis_run_id = None

        result = self._solver.run_solver_analysis(
            project_id,
            software,
            analysis_type=analysis_type,
            analysis_run_id=analysis_run_id,
            created_by=actor_id,
        )
        capability_status = str(result.get("capability_status") or result.get("status", "")).upper()
        if capability_status in _UNSUPPORTED_CAPABILITY_STATUSES or not result.get("engineering_results_available"):
            step.status = WorkflowStepStatus.UNSUPPORTED
            step.limitations = [str(result.get("message") or capability_status)]
        else:
            step.status = WorkflowStepStatus.EXECUTED
        step.execution_result = result
        step.outputs = {
            "engineering_results_available": bool(result.get("engineering_results_available")),
            "integration_execution_id": result.get("integration_execution_id"),
            "result_set_id": result.get("result_set_id"),
        }
        if result.get("result_set_id"):
            task.shared_context["result_set_id"] = result["result_set_id"]
        if result.get("analysis_run_id"):
            task.shared_context["analysis_run_id"] = result["analysis_run_id"]
        return {}

    def _execute_agent_step(
        self,
        *,
        step: EngineeringTaskStep,
        task: EngineeringTask,
        project_id: UUID,
        user_request: str,
        context_snapshot: dict[str, Any],
        parameters: dict[str, Any],
        actor_id: str,
    ) -> dict[str, Any]:
        assert step.agent_type is not None
        handler = self._handlers.get(step.agent_type)
        if handler is None:
            step.status = WorkflowStepStatus.UNSUPPORTED
            step.blocking_reason = f"No handler registered for {step.agent_type.value}."
            return {}

        merged_parameters = {
            **parameters,
            **task.shared_context.get("workflow_parameters", {}),
            "workflow_step_id": step.step_id,
            "allow_missing_inputs": True,
        }
        if step.agent_type == EngineeringAgentType.ANALYSIS_AGENT:
            if task.shared_context.get("etabs_export_execution_id"):
                merged_parameters.setdefault("solver", "ETABS")
            if task.shared_context.get("analysis_run_id"):
                merged_parameters["analysis_run_id"] = task.shared_context["analysis_run_id"]
        if step.agent_type in {
            EngineeringAgentType.CONCRETE_DESIGN_AGENT,
            EngineeringAgentType.STEEL_DESIGN_AGENT,
        } and task.shared_context.get("result_set_id"):
            merged_parameters["result_set_id"] = task.shared_context["result_set_id"]
        if step.agent_type == EngineeringAgentType.CAD_AGENT:
            drawing_type = "FRAMING_PLAN"
            if "construction" in step.title.lower():
                drawing_type = "BEAM_PLAN"
            merged_parameters.setdefault("drawing_type", drawing_type)
            merged_parameters.setdefault("output_format", "DXF")

        local_context = dict(context_snapshot)
        local_context["workflow_shared_context"] = dict(task.shared_context)
        agent_result = handler.execute(
            user_request=user_request,
            parameters=merged_parameters,
            context=local_context,
        )
        capability_status = str(
            agent_result.validation_information.get("capability_status")
            or agent_result.structured_output.get("capability_status")
            or ""
        ).upper()
        if capability_status in _UNSUPPORTED_CAPABILITY_STATUSES:
            step.status = WorkflowStepStatus.UNSUPPORTED
            step.limitations = [
                str(agent_result.structured_output.get("status_message") or capability_status)
            ]
        elif capability_status and capability_status not in _SUCCESS_CAPABILITY_STATUSES:
            step.status = WorkflowStepStatus.EXECUTED
        else:
            step.status = WorkflowStepStatus.EXECUTED

        step.execution_result = {
            "capability_status": capability_status or agent_result.structured_output.get("capability_status"),
            "status_message": agent_result.structured_output.get("status_message"),
            "structured_output": agent_result.structured_output,
            "recommendations": agent_result.recommendations,
        }
        step.outputs = {
            "capability_status": step.execution_result.get("capability_status"),
            "analysis_run_id": agent_result.structured_output.get("analysis_run_id"),
            "result_set_id": agent_result.structured_output.get("result_set_id"),
            "drawing_id": (
                agent_result.generated_artifacts[0].get("drawing_id")
                if agent_result.generated_artifacts
                else None
            ),
        }
        for key in (
            "analysis_run_id",
            "result_set_id",
            "integration_execution_id",
            "solver",
            "solver_status",
            "engineering_results_available",
        ):
            if agent_result.structured_output.get(key) is not None:
                step.outputs[key] = agent_result.structured_output[key]
                task.shared_context[key] = agent_result.structured_output[key]

        for raw in agent_result.generated_artifacts[:5]:
            if not isinstance(raw, dict):
                continue
            artifact = EngineeringTaskArtifact(
                artifact_id=str(raw.get("id") or raw.get("drawing_id") or raw.get("report_id") or step.step_id),
                artifact_type=str(raw.get("type") or raw.get("artifact_type") or "artifact"),
                filename=str(raw.get("filename") or raw.get("path") or raw.get("name") or "") or None,
                generation_status="generated" if raw.get("path") or raw.get("drawing_id") or raw.get("report_id") else "unavailable",
                producing_capability=step.capability,
                producing_agent_type=step.agent_type,
                source_step_id=step.step_id,
                drawing_id=str(raw.get("drawing_id")) if raw.get("drawing_id") else None,
                report_id=str(raw.get("report_id")) if raw.get("report_id") else None,
                href=str(raw.get("path")) if raw.get("path") else None,
            )
            step.step_artifacts.append(artifact)

        if step.requires_approval or step.approval_required:
            return {"pause_for_approval": True}
        return {}

    def _build_aggregate_result(
        self,
        *,
        task: EngineeringTask,
        selected_agent_type: EngineeringAgentType | None,
        aggregate_recommendations: list[str],
        aggregate_artifacts: list[dict[str, Any]],
        aggregate_validation: dict[str, Any],
    ) -> AgentResult:
        executed = [step for step in task.steps if step.status == WorkflowStepStatus.EXECUTED]
        blocked = [step for step in task.steps if step.status == WorkflowStepStatus.BLOCKED]
        unsupported = [step for step in task.steps if step.status == WorkflowStepStatus.UNSUPPORTED]
        summary_lines = [
            f"Workflow status: {task.status.value}",
            f"Executed steps: {len(executed)}",
            f"Blocked steps: {len(blocked)}",
            f"Unsupported steps: {len(unsupported)}",
        ]
        if task.missing_required_inputs:
            summary_lines.append("Missing inputs: " + "; ".join(task.missing_required_inputs[:6]))
        workflow_output = {
            "agent_type": selected_agent_type.value if selected_agent_type else "WORKFLOW",
            "action": "multi_step_workflow",
            "capability_status": task.status.value,
            "status_message": "\n".join(summary_lines),
            "workflow_summary": {
                "executed": [step.title for step in executed],
                "blocked": [step.title for step in blocked],
                "unsupported": [step.title for step in unsupported],
            },
            "shared_context": task.shared_context,
        }
        for key in (
            "analysis_run_id",
            "result_set_id",
            "integration_execution_id",
            "solver",
            "solver_status",
            "engineering_results_available",
        ):
            if task.shared_context.get(key) is not None:
                workflow_output[key] = task.shared_context[key]
        return AgentResult(
            structured_output=workflow_output,
            confidence=0.6 if executed else 0.2,
            generated_artifacts=aggregate_artifacts,
            recommendations=aggregate_recommendations[:8],
            validation_information={
                **aggregate_validation,
                "capability_status": task.status.value,
                "workflow_task_id": str(task.id),
            },
        )

    @staticmethod
    def _order_steps(steps: list[EngineeringTaskStep]) -> list[EngineeringTaskStep]:
        by_id = {step.step_id: step for step in steps}
        ordered: list[EngineeringTaskStep] = []
        visited: set[str] = set()

        def visit(step: EngineeringTaskStep) -> None:
            if step.step_id in visited:
                return
            visited.add(step.step_id)
            for dependency in step.dependencies:
                upstream = by_id.get(dependency)
                if upstream is not None:
                    visit(upstream)
            ordered.append(step)

        for step in sorted(steps, key=lambda item: item.step_number):
            visit(step)
        return ordered

    @staticmethod
    def _dependencies_satisfied(step: EngineeringTaskStep, task: EngineeringTask) -> bool:
        if not step.dependencies:
            return True
        by_id = {item.step_id: item for item in task.steps}
        for dependency in step.dependencies:
            upstream = by_id.get(dependency)
            if upstream is None:
                continue
            if upstream.status != WorkflowStepStatus.EXECUTED:
                return False
        return True

    @staticmethod
    def _find_step(task: EngineeringTask, step_id: str) -> EngineeringTaskStep | None:
        for step in task.steps:
            if step.step_id == step_id:
                return step
        return None
