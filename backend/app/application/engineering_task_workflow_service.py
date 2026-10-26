"""Plan, validate, and execute structured engineering task workflows."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from app.application.agent_capability_catalog import get_agent_capability_profile
from app.application.integration_service import IntegrationService
from app.application.hybrid_orchestration_service import HybridOrchestrationService
from app.domain.models.agent import EngineeringAgentType
from app.domain.models.agent_runtime import (
    AgentExecutionStatus,
    AgentResult,
    PromptGenerationResult,
)
from app.domain.models.engineering_task import (
    AssumptionSource,
    EngineeringAssumption,
    EngineeringTask,
    EngineeringTaskArtifact,
    EngineeringTaskStatus,
    EngineeringTaskStep,
    WorkflowStepStatus,
)
from app.domain.models.integration import IntegrationOperation, IntegrationSoftware
from app.domain.models.orchestration import OrchestrationTask

_COMPLEX_DELIVERABLE_TERMS = (
    "drawing",
    "drawings",
    "model",
    "report",
    "etabs",
    "dwg",
    "dxf",
    "construction",
    "architectural",
)

# Handler capability statuses meaning "I only asked for / listed missing inputs; no engineering work ran".
_WAITING_FOR_INPUT_CAPABILITY_STATUSES = frozenset({"MISSING_REQUIRED_INPUT", "WAITING_FOR_INPUT"})
MODEL_INPUT_MISSING = "Structural model (required inputs)"

_BUILDING_TERMS = ("building", "story", "stories", "frame", "reinforced concrete")

_CRITICAL_INPUTS = (
    "Jurisdiction / authority having jurisdiction",
    "Story heights",
    "Occupancy / use classification",
    "Design loads (dead, live, roof)",
    "Seismic design parameters",
    "Wind design parameters",
    "Soil / geotechnical assumptions",
    "Lateral force-resisting system",
    "Foundation type and constraints",
)

_AGENT_STEP_MAP: dict[str, EngineeringAgentType] = {
    "STRUCTURAL_MODELING_AGENT": EngineeringAgentType.STRUCTURAL_MODELING_AGENT,
    "LOAD_ASSESSMENT_AGENT": EngineeringAgentType.LOAD_ASSESSMENT_AGENT,
    "ANALYSIS_AGENT": EngineeringAgentType.ANALYSIS_AGENT,
    "CONCRETE_DESIGN_AGENT": EngineeringAgentType.CONCRETE_DESIGN_AGENT,
    "STEEL_DESIGN_AGENT": EngineeringAgentType.STEEL_DESIGN_AGENT,
    "SEISMIC_AGENT": EngineeringAgentType.SEISMIC_AGENT,
    "VALIDATION_AGENT": EngineeringAgentType.VALIDATION_AGENT,
    "CAD_AGENT": EngineeringAgentType.CAD_AGENT,
    "REPORTING_AGENT": EngineeringAgentType.REPORTING_AGENT,
    "DOCUMENT_INTERPRETATION_AGENT": EngineeringAgentType.DOCUMENT_INTERPRETATION_AGENT,
}


class EngineeringTaskWorkflowService:
    """Structured engineering workflow planning and honest step execution."""

    def __init__(
        self,
        *,
        hybrid_orchestration: HybridOrchestrationService | None = None,
        integration_service: IntegrationService | None = None,
    ) -> None:
        self._hybrid = hybrid_orchestration
        self._integration = integration_service

    def build_task(
        self,
        *,
        user_request: str,
        project_id: UUID,
        context_snapshot: dict[str, Any],
        prompt_result: PromptGenerationResult,
        conversation_id: str | None = None,
        account_id: str | None = None,
        attachment_context: dict[str, Any] | None = None,
    ) -> EngineeringTask:
        normalized = user_request.strip()
        deliverables = self._extract_deliverables(normalized)
        assumptions = self._extract_assumptions(normalized, context_snapshot)
        missing_inputs = self._collect_missing_inputs(
            user_request=normalized,
            context_snapshot=context_snapshot,
            prompt_result=prompt_result,
            assumptions=assumptions,
            attachment_context=attachment_context,
        )
        steps = self._build_workflow_steps(
            user_request=normalized,
            prompt_result=prompt_result,
            deliverables=deliverables,
            missing_inputs=missing_inputs,
            context_snapshot=context_snapshot,
            attachment_context=attachment_context,
        )
        disciplines = self._derive_disciplines(steps)
        limitations = self._derive_limitations(deliverables, attachment_context)

        task = EngineeringTask(
            conversation_id=UUID(conversation_id) if conversation_id else None,
            project_id=project_id,
            account_id=account_id,
            original_request=normalized,
            normalized_objective=prompt_result.user_intent or prompt_result.objective or normalized,
            requested_deliverables=deliverables,
            required_disciplines=disciplines,
            input_file_ids=self._attachment_file_ids(attachment_context),
            assumptions=assumptions,
            missing_required_inputs=missing_inputs,
            steps=steps,
            limitations=limitations,
            primary_agent_type=prompt_result.selected_agent_type,
            provenance={
                "routing_method": prompt_result.metadata.get("routing_method"),
                "prompt_execution_plan_steps": len(prompt_result.execution_plan),
            },
            status=EngineeringTaskStatus.DRAFT,
        )
        return self.evaluate_steps(task, context_snapshot)

    def refresh_task_for_resume(
        self,
        task: EngineeringTask,
        *,
        supplemental_request: str,
        context_snapshot: dict[str, Any],
        prompt_result: PromptGenerationResult,
        attachment_context: dict[str, Any] | None = None,
    ) -> EngineeringTask:
        combined_request = task.original_request
        supplemental = supplemental_request.strip()
        if supplemental and supplemental not in task.original_request:
            combined_request = f"{task.original_request.rstrip()}\n\nSupplemental input:\n{supplemental}"

        merged_assumptions = {item.field_name: item for item in task.assumptions}
        for assumption in self._extract_assumptions(combined_request, context_snapshot):
            merged_assumptions[assumption.field_name] = assumption
        task.assumptions = list(merged_assumptions.values())
        task.original_request = combined_request

        if attachment_context:
            task.input_file_ids = list(
                dict.fromkeys(task.input_file_ids + self._attachment_file_ids(attachment_context))
            )

        task.missing_required_inputs = self._collect_missing_inputs(
            user_request=combined_request,
            context_snapshot=context_snapshot,
            prompt_result=prompt_result,
            assumptions=task.assumptions,
            attachment_context=attachment_context,
        )

        for step in task.steps:
            if step.status in {
                WorkflowStepStatus.EXECUTED,
                WorkflowStepStatus.FAILED,
                WorkflowStepStatus.UNSUPPORTED,
            }:
                continue
            step.missing_inputs = []
            step.blocking_reason = None
            if step.status == WorkflowStepStatus.BLOCKED:
                step.status = WorkflowStepStatus.PLANNED

        return self.evaluate_steps(task, context_snapshot)

    def evaluate_steps(
        self,
        task: EngineeringTask,
        context_snapshot: dict[str, Any],
    ) -> EngineeringTask:
        pem_version = context_snapshot.get("pem_version")
        has_code = context_snapshot.get("code_configuration") is not None
        has_units = context_snapshot.get("unit_configuration") is not None
        has_model = pem_version not in (None, 0)
        critical_missing = set(task.missing_required_inputs)

        for step in task.steps:
            if step.status in {WorkflowStepStatus.EXECUTED, WorkflowStepStatus.FAILED}:
                continue

            if step.capability_kind == "understanding":
                step.status = WorkflowStepStatus.EXECUTED
                continue

            if step.capability_kind == "input_validation":
                if critical_missing:
                    step.status = WorkflowStepStatus.BLOCKED
                    step.missing_inputs = list(critical_missing)
                else:
                    step.status = WorkflowStepStatus.EXECUTED
                continue

            if step.capability == "document.review":
                if self._attachments_have_extracted_content(task, context_snapshot):
                    step.status = WorkflowStepStatus.EXECUTABLE
                elif task.input_file_ids:
                    step.status = WorkflowStepStatus.BLOCKED
                    step.missing_inputs = ["Extracted content from attached documents"]
                    step.limitations = self._attachment_limitations(context_snapshot)
                else:
                    step.status = WorkflowStepStatus.PLANNED
                continue

            if step.capability == "project.validate":
                step.status = WorkflowStepStatus.EXECUTABLE if has_code and has_units else WorkflowStepStatus.BLOCKED
                if not has_code:
                    step.missing_inputs.append("Project code configuration")
                if not has_units:
                    step.missing_inputs.append("Project unit system")
                continue

            if step.capability_kind == "integration":
                availability = self._integration_availability(step.capability)
                if availability == "AVAILABLE":
                    step.status = WorkflowStepStatus.EXECUTABLE if has_model else WorkflowStepStatus.BLOCKED
                    if not has_model:
                        step.missing_inputs.append("Analysis-ready structural model")
                else:
                    step.status = WorkflowStepStatus.UNSUPPORTED
                    step.limitations = [availability]
                continue

            if step.capability == "architectural.concept":
                step.status = WorkflowStepStatus.EXECUTABLE
                continue

            if step.agent_type is not None:
                profile = get_agent_capability_profile(step.agent_type)
                step.requires_approval = profile.requires_human_approval
                blocked_by_inputs = bool(step.missing_inputs) or bool(
                    profile.blocks_on_missing_inputs and critical_missing
                )
                if step.agent_type in {
                    EngineeringAgentType.STRUCTURAL_MODELING_AGENT,
                    EngineeringAgentType.ANALYSIS_AGENT,
                    EngineeringAgentType.CONCRETE_DESIGN_AGENT,
                    EngineeringAgentType.STEEL_DESIGN_AGENT,
                } and not has_model and "Engineering model baseline" in task.missing_required_inputs:
                    blocked_by_inputs = True
                    step.missing_inputs = sorted(
                        set(step.missing_inputs) | {"Engineering model baseline"}
                    )

                if step.status == WorkflowStepStatus.UNSUPPORTED:
                    continue
                if blocked_by_inputs:
                    step.status = WorkflowStepStatus.BLOCKED
                else:
                    step.status = WorkflowStepStatus.EXECUTABLE

        task.status = self._derive_task_status(task)
        task.touch()
        return task

    def execute_preparatory_steps(
        self,
        task: EngineeringTask,
        *,
        project_id: UUID,
        context_snapshot: dict[str, Any],
    ) -> EngineeringTask:
        task.status = EngineeringTaskStatus.RUNNING
        for step in task.steps:
            if step.status != WorkflowStepStatus.EXECUTABLE:
                continue

            if step.capability == "project.validate" and self._hybrid is not None:
                result = self._hybrid.execute(
                    OrchestrationTask(task_type="project.validate", project_id=project_id, payload={})
                )
                step.status = WorkflowStepStatus.EXECUTED
                step.execution_result = result.model_dump(mode="json")
                continue

            if step.capability == "document.review":
                step.status = WorkflowStepStatus.EXECUTED
                step.execution_result = {
                    "reviewed_file_ids": task.input_file_ids,
                    "extracted": True,
                }
                continue

        task.status = self._derive_task_status(task)
        task.touch()
        return task

    def finalize_with_handler_result(
        self,
        task: EngineeringTask,
        *,
        agent_type: EngineeringAgentType,
        agent_result: AgentResult | None,
        execution_status: AgentExecutionStatus,
        requires_approval: bool,
        execution_id: UUID | None = None,
    ) -> EngineeringTask:
        if execution_id is not None:
            task.execution_id = execution_id

        primary_step = self._find_primary_step(task, agent_type)
        waiting_for_input = False
        if primary_step is not None:
            if execution_status == AgentExecutionStatus.BLOCKED:
                primary_step.status = WorkflowStepStatus.BLOCKED
            elif execution_status == AgentExecutionStatus.FAILED:
                primary_step.status = WorkflowStepStatus.FAILED
            elif requires_approval or execution_status == AgentExecutionStatus.REQUIRES_HUMAN_APPROVAL:
                primary_step.status = WorkflowStepStatus.EXECUTABLE
                task.status = EngineeringTaskStatus.WAITING_FOR_APPROVAL
            elif execution_status == AgentExecutionStatus.COMPLETED and agent_result is not None:
                capability_status = str(
                    agent_result.validation_information.get("capability_status", "")
                ).upper()
                if capability_status in {
                    "NOT_IMPLEMENTED",
                    "NOT_AVAILABLE",
                    "UNAVAILABLE",
                    "REQUIRES_LOCAL_SOFTWARE",
                }:
                    primary_step.status = WorkflowStepStatus.UNSUPPORTED
                    primary_step.limitations = [agent_result.structured_output.get("status_message", capability_status)]
                elif capability_status in _WAITING_FOR_INPUT_CAPABILITY_STATUSES:
                    # The handler only returned a prerequisites report / question: no engineering work was run.
                    primary_step.status = WorkflowStepStatus.BLOCKED
                    primary_step.missing_inputs = [MODEL_INPUT_MISSING]
                    primary_step.blocking_reason = "Waiting for the structural model"
                    waiting_for_input = True
                else:
                    primary_step.status = WorkflowStepStatus.EXECUTED
                primary_step.execution_result = {
                    "capability_status": capability_status or agent_result.structured_output.get("capability_status"),
                    "status_message": agent_result.structured_output.get("status_message"),
                }
            else:
                primary_step.status = WorkflowStepStatus.PLANNED

        if primary_step is not None and primary_step.status != WorkflowStepStatus.EXECUTED:
            # "Validate and record results" must not read as done while the specialist step has produced nothing.
            for step in task.steps:
                if (
                    step.step_number > primary_step.step_number
                    and step.capability == "project.validate"
                    and step.status == WorkflowStepStatus.EXECUTED
                ):
                    step.status = WorkflowStepStatus.PLANNED
                    step.execution_result = None

        if agent_result is not None:
            task.artifacts.extend(self._artifacts_from_agent_result(task, agent_type, agent_result))

        if task.status != EngineeringTaskStatus.WAITING_FOR_APPROVAL:
            task.status = self._derive_task_status(task, execution_status=execution_status)
            if waiting_for_input:
                task.status = EngineeringTaskStatus.WAITING_FOR_INPUT
                if MODEL_INPUT_MISSING not in task.missing_required_inputs:
                    task.missing_required_inputs = [*task.missing_required_inputs, MODEL_INPUT_MISSING]
        task.touch()
        return task

    def task_blocks_execution(self, task: EngineeringTask) -> bool:
        return task.status == EngineeringTaskStatus.WAITING_FOR_INPUT

    def _derive_task_status(
        self,
        task: EngineeringTask,
        *,
        execution_status: AgentExecutionStatus | None = None,
    ) -> EngineeringTaskStatus:
        if execution_status == AgentExecutionStatus.REQUIRES_HUMAN_APPROVAL:
            return EngineeringTaskStatus.WAITING_FOR_APPROVAL

        if execution_status == AgentExecutionStatus.BLOCKED and task.missing_required_inputs:
            return EngineeringTaskStatus.WAITING_FOR_INPUT

        statuses = {step.status for step in task.steps}
        executed_count = sum(1 for step in task.steps if step.status == WorkflowStepStatus.EXECUTED)

        if statuses == {WorkflowStepStatus.EXECUTED}:
            return EngineeringTaskStatus.COMPLETED
        if WorkflowStepStatus.EXECUTED in statuses and (
            WorkflowStepStatus.UNSUPPORTED in statuses
            or WorkflowStepStatus.BLOCKED in statuses
            or WorkflowStepStatus.PLANNED in statuses
            or WorkflowStepStatus.EXECUTABLE in statuses
        ):
            return EngineeringTaskStatus.PARTIALLY_COMPLETED
        if execution_status == AgentExecutionStatus.FAILED:
            return EngineeringTaskStatus.FAILED
        if WorkflowStepStatus.EXECUTABLE in statuses or execution_status == AgentExecutionStatus.RUNNING:
            return EngineeringTaskStatus.RUNNING
        if task.missing_required_inputs and executed_count <= 1:
            return EngineeringTaskStatus.WAITING_FOR_INPUT
        return EngineeringTaskStatus.READY

    def _build_workflow_steps(
        self,
        *,
        user_request: str,
        prompt_result: PromptGenerationResult,
        deliverables: list[str],
        missing_inputs: list[str],
        context_snapshot: dict[str, Any],
        attachment_context: dict[str, Any] | None,
    ) -> list[EngineeringTaskStep]:
        if self._is_complex_request(user_request, deliverables):
            return self._complex_building_workflow(
                prompt_result=prompt_result,
                deliverables=deliverables,
                missing_inputs=missing_inputs,
                attachment_context=attachment_context,
            )
        return self._simple_workflow_from_plan(
            prompt_result=prompt_result,
            missing_inputs=missing_inputs,
            context_snapshot=context_snapshot,
        )

    def _simple_workflow_from_plan(
        self,
        *,
        prompt_result: PromptGenerationResult,
        missing_inputs: list[str],
        context_snapshot: dict[str, Any],
    ) -> list[EngineeringTaskStep]:
        steps: list[EngineeringTaskStep] = [
            EngineeringTaskStep(
                step_number=1,
                title="Understand engineer goal",
                description=prompt_result.user_intent or prompt_result.objective,
                capability="request.analysis",
                capability_kind="understanding",
                status=WorkflowStepStatus.EXECUTED,
            ),
            EngineeringTaskStep(
                step_number=2,
                title="Validate required inputs",
                description="Confirm project configuration and request inputs",
                capability="input.validation",
                capability_kind="input_validation",
                missing_inputs=list(missing_inputs),
            ),
        ]
        step_number = 3
        if context_snapshot.get("chat_attachments") or context_snapshot.get("files"):
            steps.append(
                EngineeringTaskStep(
                    step_number=step_number,
                    title="Review attached or project files",
                    description="Use extracted attachment context where available",
                    capability="document.review",
                    capability_kind="deterministic_service",
                )
            )
            step_number += 1

        profile = get_agent_capability_profile(prompt_result.selected_agent_type)
        steps.append(
            EngineeringTaskStep(
                step_number=step_number,
                title="Execute specialist assistant work",
                description=prompt_result.user_intent,
                capability=prompt_result.selected_agent_type.value,
                capability_kind="agent",
                agent_type=prompt_result.selected_agent_type,
                requires_approval=profile.requires_human_approval,
                missing_inputs=list(missing_inputs),
            )
        )
        step_number += 1
        steps.append(
            EngineeringTaskStep(
                step_number=step_number,
                title="Validate and record results",
                description="Apply validation checks and traceability links",
                capability="project.validate",
                capability_kind="deterministic_service",
            )
        )
        return steps

    def _complex_building_workflow(
        self,
        *,
        prompt_result: PromptGenerationResult,
        deliverables: list[str],
        missing_inputs: list[str],
        attachment_context: dict[str, Any] | None,
    ) -> list[EngineeringTaskStep]:
        steps: list[EngineeringTaskStep] = [
            EngineeringTaskStep(
                step_id="understand_request",
                step_number=1,
                title="Understand engineering request",
                description=prompt_result.objective,
                capability="request.analysis",
                capability_kind="understanding",
                status=WorkflowStepStatus.EXECUTED,
            ),
            EngineeringTaskStep(
                step_id="validate_inputs",
                step_number=2,
                title="Validate required inputs",
                description="Confirm code, units, geometry, loads, and site parameters",
                capability="input.validation",
                capability_kind="input_validation",
                missing_inputs=list(missing_inputs),
            ),
        ]
        step_number = 3
        base_dependencies = ["validate_inputs"]
        if attachment_context and attachment_context.get("attachments"):
            steps.append(
                EngineeringTaskStep(
                    step_id="document_review",
                    step_number=step_number,
                    title="Review attached engineering documents",
                    description="Use extracted attachment context where available",
                    capability="document.review",
                    capability_kind="deterministic_service",
                    dependencies=["validate_inputs"],
                )
            )
            base_dependencies.append("document_review")
            step_number += 1

        requested = {item.lower() for item in deliverables}
        if any("architectural" in item for item in requested):
            steps.append(
                EngineeringTaskStep(
                    step_id="architectural_concept",
                    step_number=step_number,
                    title="Produce architectural drawings",
                    description="Generate structured architectural concept and schematic zoning DXF",
                    capability="architectural.concept",
                    capability_kind="architectural",
                    dependencies=list(base_dependencies),
                    missing_inputs=list(missing_inputs),
                )
            )
            step_number += 1

        core_steps: list[tuple[str, str, str, EngineeringAgentType, list[str], list[str]]] = [
            (
                "structural_assumptions",
                "Establish structural system assumptions",
                "Confirm framing system, materials, and layout constraints",
                EngineeringAgentType.STRUCTURAL_MODELING_AGENT,
                missing_inputs,
                list(base_dependencies),
            ),
            (
                "establish_loads",
                "Establish design loads",
                "Confirm dead, live, roof, and environmental loads",
                EngineeringAgentType.LOAD_ASSESSMENT_AGENT,
                [
                    item
                    for item in missing_inputs
                    if "load" in item.lower() or "seismic" in item.lower() or "wind" in item.lower()
                ],
                ["validate_inputs"],
            ),
            (
                "structural_model",
                "Create or update structural model",
                "Prepare analysis-ready model from approved inputs",
                EngineeringAgentType.STRUCTURAL_MODELING_AGENT,
                missing_inputs,
                ["structural_assumptions", "establish_loads"],
            ),
            (
                "structural_analysis",
                "Run structural analysis",
                "Execute analysis using available solver workflows",
                EngineeringAgentType.ANALYSIS_AGENT,
                missing_inputs,
                ["structural_model"],
            ),
            (
                "concrete_design",
                "Design reinforced concrete members",
                "Perform member design checks where analysis results exist",
                EngineeringAgentType.CONCRETE_DESIGN_AGENT,
                missing_inputs,
                ["structural_analysis"],
            ),
            (
                "engineering_validation",
                "Validate engineering results",
                "Apply project validation and code checks",
                EngineeringAgentType.VALIDATION_AGENT,
                [],
                ["concrete_design"],
            ),
        ]
        for step_id, title, description, agent_type, step_missing, dependencies in core_steps:
            profile = get_agent_capability_profile(agent_type)
            steps.append(
                EngineeringTaskStep(
                    step_id=step_id,
                    step_number=step_number,
                    title=title,
                    description=description,
                    capability=agent_type.value,
                    capability_kind="agent",
                    agent_type=agent_type,
                    dependencies=dependencies,
                    requires_approval=profile.requires_human_approval,
                    missing_inputs=list(step_missing),
                )
            )
            step_number += 1

        requested = {item.lower() for item in deliverables}
        deliverable_specs: list[tuple[str, str, str, str, EngineeringAgentType | None, list[str]]] = [
            (
                "structural design drawings",
                "cad_structural",
                "CAD_AGENT",
                "agent",
                EngineeringAgentType.CAD_AGENT,
                ["engineering_validation"],
            ),
            (
                "construction drawings",
                "cad_construction",
                "CAD_AGENT",
                "agent",
                EngineeringAgentType.CAD_AGENT,
                ["cad_structural"],
            ),
            (
                "ETABS model",
                "etabs_model",
                "integration.etabs",
                "integration",
                None,
                ["structural_model"],
            ),
            (
                "engineering report",
                "engineering_report",
                "REPORTING_AGENT",
                "agent",
                EngineeringAgentType.REPORTING_AGENT,
                ["engineering_validation"],
            ),
        ]
        for label, step_id, capability, kind, agent_type, dependencies in deliverable_specs:
            if not any(label.lower() in item or item in label.lower() for item in requested):
                continue
            steps.append(
                EngineeringTaskStep(
                    step_id=step_id,
                    step_number=step_number,
                    title=f"Produce {label}",
                    description=f"Generate {label} only when supported capabilities are available",
                    capability=capability,
                    capability_kind=kind,
                    agent_type=agent_type,
                    dependencies=dependencies,
                    requires_approval=agent_type is not None
                    and get_agent_capability_profile(agent_type).requires_human_approval,
                    missing_inputs=list(missing_inputs),
                )
            )
            step_number += 1

        steps.append(
            EngineeringTaskStep(
                step_id="final_validation",
                step_number=step_number,
                title="Validate and record results",
                description="Apply validation checks and traceability links",
                capability="project.validate",
                capability_kind="deterministic_service",
                dependencies=[steps[-1].step_id] if len(steps) > 2 else ["validate_inputs"],
            )
        )
        return steps

    def _collect_missing_inputs(
        self,
        *,
        user_request: str,
        context_snapshot: dict[str, Any],
        prompt_result: PromptGenerationResult,
        assumptions: list[EngineeringAssumption],
        attachment_context: dict[str, Any] | None,
    ) -> list[str]:
        missing = list(dict.fromkeys(prompt_result.missing_information))

        assumption_fields = {item.field_name for item in assumptions if item.value}
        if context_snapshot.get("code_configuration") is None and "Project code configuration" not in missing:
            missing.append("Project code configuration")
        if context_snapshot.get("unit_configuration") is None and "Project unit system" not in missing:
            missing.append("Project unit system")

        if self._is_complex_request(user_request, self._extract_deliverables(user_request)):
            for item in _CRITICAL_INPUTS:
                key = item.split("/")[0].strip().lower()
                if any(key in field.lower() for field in assumption_fields):
                    continue
                if item == "Design loads (dead, live, roof)" and self._attachments_have_extracted_content_from_dict(
                    attachment_context
                ):
                    continue
                if item not in missing:
                    missing.append(item)
        return missing

    def _extract_assumptions(
        self,
        user_request: str,
        context_snapshot: dict[str, Any],
    ) -> list[EngineeringAssumption]:
        assumptions: list[EngineeringAssumption] = []
        normalized = user_request.lower()

        story_match = re.search(r"(\d+)\s*[- ]?stor", normalized)
        if story_match:
            assumptions.append(
                EngineeringAssumption(
                    field_name="Number of stories",
                    value=story_match.group(1),
                    source=AssumptionSource.USER_PROVIDED,
                )
            )

        dimension_match = re.search(
            r"(\d+(?:\.\d+)?)\s*m\s*[x×]\s*(\d+(?:\.\d+)?)\s*m",
            normalized,
        )
        if dimension_match:
            assumptions.append(
                EngineeringAssumption(
                    field_name="Plan dimensions",
                    value=f"{dimension_match.group(1)} m x {dimension_match.group(2)} m",
                    source=AssumptionSource.USER_PROVIDED,
                )
            )

        if "reinforced concrete" in normalized or "concrete frame" in normalized:
            assumptions.append(
                EngineeringAssumption(
                    field_name="Primary structural material",
                    value="Reinforced concrete",
                    source=AssumptionSource.USER_PROVIDED,
                )
            )

        code_config = context_snapshot.get("code_configuration")
        if isinstance(code_config, dict):
            edition = None
            governing = code_config.get("governing_building_code")
            if isinstance(governing, dict):
                edition = governing.get("edition")
            assumptions.append(
                EngineeringAssumption(
                    field_name="Design code",
                    value=str(edition) if edition else None,
                    source=AssumptionSource.PROJECT_CONFIGURED,
                )
            )

        unit_config = context_snapshot.get("unit_configuration")
        if isinstance(unit_config, dict) and unit_config.get("system"):
            assumptions.append(
                EngineeringAssumption(
                    field_name="Unit system",
                    value=str(unit_config.get("system")),
                    source=AssumptionSource.PROJECT_CONFIGURED,
                )
            )

        return assumptions

    def _extract_deliverables(self, user_request: str) -> list[str]:
        normalized = user_request.lower()
        deliverables: list[str] = []
        mapping = {
            "architectural drawings": ("architectural drawing", "architectural drawings"),
            "structural design drawings": ("structural design drawing", "structural drawings", "structural design"),
            "construction drawings": ("construction drawing", "construction drawings"),
            "ETABS model": ("etabs model",),
            "engineering report": ("report", "engineering report"),
            "analysis results": ("analysis", "analyze"),
        }
        for label, terms in mapping.items():
            if any(term in normalized for term in terms):
                deliverables.append(label)
        return deliverables

    def _derive_disciplines(self, steps: list[EngineeringTaskStep]) -> list[str]:
        disciplines: list[str] = []
        for step in steps:
            if step.agent_type is None:
                continue
            label = step.agent_type.value.replace("_AGENT", "").replace("_", " ").title()
            if label not in disciplines:
                disciplines.append(label)
        return disciplines

    def _derive_limitations(
        self,
        deliverables: list[str],
        attachment_context: dict[str, Any] | None,
    ) -> list[str]:
        limitations: list[str] = []
        if any("ETABS" in item for item in deliverables):
            limitations.append(
                "ETABS model export requires installed ETABS integration; unavailable environments are reported honestly."
            )
        if any("architectural" in item.lower() for item in deliverables):
            limitations.append(
                "Architectural deliverables are schematic zoning concepts and DXF diagrams, not full architectural design packages."
            )
        if attachment_context:
            for attachment in attachment_context.get("attachments", []):
                if attachment.get("limitation"):
                    limitations.append(str(attachment["limitation"]))
        return list(dict.fromkeys(limitations))

    def _is_complex_request(self, user_request: str, deliverables: list[str]) -> bool:
        normalized = user_request.lower()
        if len(deliverables) >= 2:
            return True
        if any(term in normalized for term in _BUILDING_TERMS) and any(
            term in normalized for term in _COMPLEX_DELIVERABLE_TERMS
        ):
            return True
        return "design" in normalized and "building" in normalized

    def _integration_availability(self, capability: str) -> str:
        if self._integration is None:
            return "Integration service is not configured."
        software_map = {
            "integration.etabs": IntegrationSoftware.ETABS,
            "integration.sap2000": IntegrationSoftware.SAP2000,
            "integration.safe": IntegrationSoftware.SAFE,
        }
        software = software_map.get(capability)
        if software is None:
            return "Integration capability is not supported."
        try:
            adapter = self._integration.get_adapter(software)
            if hasattr(adapter, "detect_capability"):
                report = adapter.detect_capability()
                return report.availability.value
            status = adapter.get_status()
            return str(status.metadata.get("availability", "REQUIRES_LOCAL_SOFTWARE"))
        except Exception:
            return "REQUIRES_LOCAL_SOFTWARE"

    def _attachments_have_extracted_content(
        self,
        task: EngineeringTask,
        context_snapshot: dict[str, Any],
    ) -> bool:
        if self._attachments_have_extracted_content_from_dict(context_snapshot.get("chat_attachments")):
            return True
        return bool(task.input_file_ids) and bool(context_snapshot.get("files"))

    @staticmethod
    def _attachments_have_extracted_content_from_dict(payload: dict[str, Any] | None) -> bool:
        if not isinstance(payload, dict):
            return False
        for attachment in payload.get("attachments", []):
            if attachment.get("text_preview") or attachment.get("indexed_memory_content"):
                return True
            if attachment.get("availability") in {"indexed", "extracted"}:
                return True
        return False

    @staticmethod
    def _attachment_file_ids(attachment_context: dict[str, Any] | None) -> list[str]:
        if not isinstance(attachment_context, dict):
            return []
        ids = attachment_context.get("file_ids") or attachment_context.get("attachment_file_ids") or []
        if isinstance(ids, list) and ids:
            return [str(item) for item in ids]
        attachments = attachment_context.get("attachments") or []
        return [str(item.get("file_id")) for item in attachments if item.get("file_id")]

    @staticmethod
    def _attachment_limitations(context_snapshot: dict[str, Any]) -> list[str]:
        limitations: list[str] = []
        chat_attachments = context_snapshot.get("chat_attachments")
        if not isinstance(chat_attachments, dict):
            return limitations
        for attachment in chat_attachments.get("attachments", []):
            if attachment.get("limitation"):
                limitations.append(str(attachment["limitation"]))
        return limitations

    @staticmethod
    def _find_primary_step(
        task: EngineeringTask,
        agent_type: EngineeringAgentType,
    ) -> EngineeringTaskStep | None:
        for step in reversed(task.steps):
            if step.agent_type == agent_type and step.capability_kind == "agent":
                return step
        for step in task.steps:
            if step.agent_type == agent_type:
                return step
        return None

    def _artifacts_from_agent_result(
        self,
        task: EngineeringTask,
        agent_type: EngineeringAgentType,
        agent_result: AgentResult,
    ) -> list[EngineeringTaskArtifact]:
        artifacts: list[EngineeringTaskArtifact] = []
        for index, raw in enumerate(agent_result.generated_artifacts[:10]):
            if not isinstance(raw, dict):
                continue
            artifact_type = str(raw.get("type") or raw.get("artifact_type") or "artifact")
            filename = raw.get("filename") or raw.get("path") or raw.get("name")
            file_id = raw.get("file_id") or raw.get("drawing_id")
            report_id = raw.get("report_id")
            generation_status = "generated" if file_id or report_id or raw.get("path") else "unavailable"
            artifacts.append(
                EngineeringTaskArtifact(
                    artifact_id=str(raw.get("id") or file_id or report_id or f"{task.id}-{index}"),
                    artifact_type=artifact_type,
                    filename=str(filename) if filename else None,
                    generation_status=generation_status,
                    producing_capability=agent_type.value,
                    producing_agent_type=agent_type,
                    input_provenance=[task.original_request[:120]],
                    file_id=str(file_id) if file_id else None,
                    report_id=str(report_id) if report_id else None,
                )
            )
        return artifacts
