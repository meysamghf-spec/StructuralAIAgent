"""Hybrid orchestration — route tasks to deterministic engines, validation, or AI."""

from __future__ import annotations

from uuid import UUID

from app.application.ai_gateway_service import AIGatewayService
from app.application.analysis_engine_service import AnalysisEngineService
from app.application.design_engine_service import DesignEngineService
from app.application.optimization_engine_service import OptimizationEngineService
from app.application.code_engine_service import CodeEngineService
from app.application.exceptions import OrchestrationTaskNotSupportedError, ProjectNotFoundError
from app.application.project_service import PemService, ProjectService
from app.application.unit_conversion_service import UnitConversionService
from app.application.validation_engine_service import ValidationEngineService
from app.domain.models.ai_gateway import AICompletionRequest, AIMessage, AIMessageRole
from app.domain.models.analysis import AnalysisRequest
from app.domain.models.design import DesignRequest
from app.domain.models.optimization import OptimizationRequest
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

_ANALYSIS_TASKS = {
    "engineering.analysis.run",
}

_DESIGN_TASKS = {
    "engineering.design.run",
}

_OPTIMIZATION_TASKS = {
    "engineering.optimization.run",
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
        analysis_engine_service: AnalysisEngineService | None = None,
        design_engine_service: DesignEngineService | None = None,
        optimization_engine_service: OptimizationEngineService | None = None,
    ) -> None:
        self._projects = project_service
        self._pem = pem_service
        self._validation = validation_service
        self._code_engine = code_engine_service
        self._units = unit_conversion_service
        self._ai = ai_gateway_service
        self._analysis = analysis_engine_service
        self._design = design_engine_service
        self._optimization = optimization_engine_service

    def execute(self, task: OrchestrationTask) -> OrchestrationResult:
        trace = [f"Received task {task.task_type}"]

        if task.task_type in _VALIDATION_TASKS:
            return self._run_validation(task, trace)

        if task.task_type in _ANALYSIS_TASKS:
            return self._run_analysis(task, trace)

        if task.task_type in _DESIGN_TASKS:
            return self._run_design(task, trace)

        if task.task_type in _OPTIMIZATION_TASKS:
            return self._run_optimization(task, trace)

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

    def _run_analysis(self, task: OrchestrationTask, trace: list[str]) -> OrchestrationResult:
        if self._analysis is None:
            raise OrchestrationTaskNotSupportedError(task_type=task.task_type)
        project_id = self._require_project_id(task)
        trace.append("Routing to AnalysisEngine")
        request = AnalysisRequest(
            project_id=project_id,
            analysis_type=str(task.payload.get("analysis_type", "STATIC")),
            parameters=dict(task.payload.get("parameters", {})),
            pem_version=task.payload.get("pem_version"),
        )
        if task.payload.get("solver"):
            request.parameters["solver"] = task.payload.get("solver")
        result = self._analysis.run_analysis(
            request,
            created_by=str(task.payload.get("created_by", "orchestration")),
        )
        return OrchestrationResult(
            task_type=task.task_type,
            route=OrchestrationRoute.ENGINE,
            status=result.status.value,
            output=result.model_dump(mode="json"),
            trace=trace,
        )

    def _run_design(self, task: OrchestrationTask, trace: list[str]) -> OrchestrationResult:
        if self._design is None:
            raise OrchestrationTaskNotSupportedError(task_type=task.task_type)
        project_id = self._require_project_id(task)
        trace.append("Routing to DesignEngine")
        request = DesignRequest(
            project_id=project_id,
            design_type=str(task.payload.get("design_type", "CONCRETE_BEAM")),
            parameters=dict(task.payload.get("parameters", {})),
            pem_version=task.payload.get("pem_version"),
            analysis_run_id=task.payload.get("analysis_run_id"),
        )
        result = self._design.run_design(
            request,
            created_by=str(task.payload.get("created_by", "orchestration")),
        )
        return OrchestrationResult(
            task_type=task.task_type,
            route=OrchestrationRoute.ENGINE,
            status=result.status.value,
            output=result.model_dump(mode="json"),
            trace=trace,
        )

    def _run_optimization(self, task: OrchestrationTask, trace: list[str]) -> OrchestrationResult:
        if self._optimization is None:
            raise OrchestrationTaskNotSupportedError(task_type=task.task_type)
        project_id = self._require_project_id(task)
        trace.append("Routing to OptimizationEngine")
        request = OptimizationRequest(
            project_id=project_id,
            optimization_type=str(task.payload.get("optimization_type", "WEIGHT")),
            objective=str(task.payload.get("objective", "Minimize structural weight")),
            constraints=dict(task.payload.get("constraints", {})),
            parameters=dict(task.payload.get("parameters", {})),
            pem_version=task.payload.get("pem_version"),
            analysis_run_id=task.payload.get("analysis_run_id"),
            design_run_id=task.payload.get("design_run_id"),
        )
        result = self._optimization.run_optimization(
            request,
            created_by=str(task.payload.get("created_by", "orchestration")),
        )
        return OrchestrationResult(
            task_type=task.task_type,
            route=OrchestrationRoute.ENGINE,
            status=result.status.value,
            output=result.model_dump(mode="json"),
            trace=trace,
        )

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
