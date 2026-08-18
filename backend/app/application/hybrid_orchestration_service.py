"""Hybrid orchestration — route tasks to deterministic engines, validation, or AI."""

from __future__ import annotations

from uuid import UUID

from app.application.ai_gateway_service import AIGatewayService
from app.application.code_engine_service import CodeEngineService
from app.application.exceptions import OrchestrationTaskNotSupportedError, ProjectNotFoundError
from app.application.project_service import PemService, ProjectService
from app.application.unit_conversion_service import UnitConversionService
from app.application.validation_engine_service import ValidationEngineService
from app.domain.models.ai_gateway import AICompletionRequest, AIMessage, AIMessageRole
from app.domain.models.orchestration import OrchestrationResult, OrchestrationRoute, OrchestrationTask
from app.domain.models.units import EngineeringQuantityType


_DETERMINISTIC_TASKS = {
    "unit.convert",
    "code.validate",
    "code.defaults",
}

_VALIDATION_TASKS = {
    "project.validate",
}


class HybridOrchestrationService:
    def __init__(
        self,
        *,
        project_service: ProjectService,
        pem_service: PemService,
        validation_service: ValidationEngineService,
        code_engine_service: CodeEngineService,
        unit_conversion_service: UnitConversionService,
        ai_gateway_service: AIGatewayService,
    ) -> None:
        self._projects = project_service
        self._pem = pem_service
        self._validation = validation_service
        self._code_engine = code_engine_service
        self._units = unit_conversion_service
        self._ai = ai_gateway_service

    def execute(self, task: OrchestrationTask) -> OrchestrationResult:
        trace = [f"Received task {task.task_type}"]

        if task.task_type in _VALIDATION_TASKS:
            return self._run_validation(task, trace)

        if task.task_type in _DETERMINISTIC_TASKS:
            return self._run_deterministic(task, trace)

        if task.task_type.startswith("integration."):
            trace.append("Integration tasks must use IntegrationService directly")
            raise OrchestrationTaskNotSupportedError(task_type=task.task_type)

        return self._run_ai(task, trace)

    def _run_validation(self, task: OrchestrationTask, trace: list[str]) -> OrchestrationResult:
        project_id = self._require_project_id(task)
        trace.append("Routing to ValidationEngine")
        report = self._validation.validate_project(project_id)
        return OrchestrationResult(
            task_type=task.task_type,
            route=OrchestrationRoute.VALIDATION,
            status=report.overall_status.value,
            output=report.model_dump(mode="json"),
            trace=trace,
        )

    def _run_deterministic(self, task: OrchestrationTask, trace: list[str]) -> OrchestrationResult:
        trace.append("Routing to deterministic service")
        if task.task_type == "unit.convert":
            payload = task.payload
            result = self._units.convert(
                float(payload["value"]),
                from_unit=str(payload["from_unit"]),
                to_unit=str(payload["to_unit"]),
                quantity_type=EngineeringQuantityType(str(payload["quantity_type"])),
            )
            return OrchestrationResult(
                task_type=task.task_type,
                route=OrchestrationRoute.DETERMINISTIC,
                status="SUCCESS",
                output=result.model_dump(mode="json"),
                trace=trace,
            )

        if task.task_type == "code.validate":
            pem = self._require_pem(task)
            result = self._code_engine.validate_configuration(pem.code_configuration)
            return OrchestrationResult(
                task_type=task.task_type,
                route=OrchestrationRoute.DETERMINISTIC,
                status="SUCCESS" if result.is_valid else "WARNING",
                output=result.model_dump(mode="json"),
                trace=trace,
            )

        if task.task_type == "code.defaults":
            defaults = self._code_engine.get_defaults()
            return OrchestrationResult(
                task_type=task.task_type,
                route=OrchestrationRoute.DETERMINISTIC,
                status="SUCCESS",
                output=defaults.model_dump(mode="json"),
                trace=trace,
            )

        raise OrchestrationTaskNotSupportedError(task_type=task.task_type)

    def _run_ai(self, task: OrchestrationTask, trace: list[str]) -> OrchestrationResult:
        trace.append("Routing to AI Gateway")
        request = AICompletionRequest(
            model=str(task.payload.get("model", "stub-default")),
            messages=[
                AIMessage(role=AIMessageRole.SYSTEM, content="You are a structural engineering assistant."),
                AIMessage(
                    role=AIMessageRole.USER,
                    content=str(task.payload.get("prompt", task.task_type)),
                ),
            ],
            context=task.payload.get("context", {}),
        )
        response = self._ai.complete(request)
        return OrchestrationResult(
            task_type=task.task_type,
            route=OrchestrationRoute.AI,
            status="SUCCESS",
            output=response.model_dump(mode="json"),
            trace=trace,
        )

    def _require_project_id(self, task: OrchestrationTask) -> UUID:
        if task.project_id is None:
            raise OrchestrationTaskNotSupportedError(task_type=task.task_type)
        if self._projects.get_project(task.project_id) is None:
            raise ProjectNotFoundError(task.project_id)
        return task.project_id

    def _require_pem(self, task: OrchestrationTask):
        project_id = self._require_project_id(task)
        pem = self._pem.get_current_pem(project_id)
        if pem is None:
            raise ProjectNotFoundError(project_id)
        return pem
