"""Integration REST endpoints — /api/v1/integrations."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import get_integration_service, get_structural_solver_integration_service
from app.api.schemas.integration import (
    IntegrationExecutionResponse,
    IntegrationRequestBody,
    IntegrationResultResponse,
    SoftwareCapabilityResponse,
)
from app.application.integration_service import IntegrationService
from app.application.structural_solver_integration_service import StructuralSolverIntegrationService
from app.domain.models.integration import IntegrationSoftware

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/adapters", response_model=list[IntegrationResultResponse])
def list_integration_adapters(
    integration_service: Annotated[IntegrationService, Depends(get_integration_service)],
) -> list[IntegrationResultResponse]:
    return [
        IntegrationResultResponse.from_domain(result)
        for result in integration_service.list_adapters()
    ]


@router.get("/capabilities", response_model=list[SoftwareCapabilityResponse])
def list_solver_capabilities(
    solver_service: Annotated[
        StructuralSolverIntegrationService, Depends(get_structural_solver_integration_service)
    ],
) -> list[SoftwareCapabilityResponse]:
    return [
        SoftwareCapabilityResponse.from_domain(report)
        for report in solver_service.list_capabilities()
    ]


@router.get("/capabilities/{software}", response_model=SoftwareCapabilityResponse)
def get_solver_capability(
    software: IntegrationSoftware,
    solver_service: Annotated[
        StructuralSolverIntegrationService, Depends(get_structural_solver_integration_service)
    ],
) -> SoftwareCapabilityResponse:
    return SoftwareCapabilityResponse.from_domain(solver_service.get_capability(software))


@router.get("/{project_id}/executions", response_model=list[IntegrationExecutionResponse])
def list_project_integration_executions(
    project_id: UUID,
    solver_service: Annotated[
        StructuralSolverIntegrationService, Depends(get_structural_solver_integration_service)
    ],
    software: IntegrationSoftware | None = None,
) -> list[IntegrationExecutionResponse]:
    executions = solver_service.list_executions(project_id, software=software)
    return [IntegrationExecutionResponse.from_domain(item) for item in executions]


@router.get("/{project_id}/executions/{execution_id}", response_model=IntegrationExecutionResponse)
def get_project_integration_execution(
    project_id: UUID,
    execution_id: UUID,
    solver_service: Annotated[
        StructuralSolverIntegrationService, Depends(get_structural_solver_integration_service)
    ],
) -> IntegrationExecutionResponse:
    execution = solver_service.get_execution(project_id, execution_id)
    if execution is None:
        from app.application.exceptions import IntegrationExecutionNotFoundError

        raise IntegrationExecutionNotFoundError(project_id, execution_id)
    return IntegrationExecutionResponse.from_domain(execution)


@router.post("/{project_id}/connect/{software}", response_model=IntegrationExecutionResponse)
def connect_solver_software(
    project_id: UUID,
    software: IntegrationSoftware,
    solver_service: Annotated[
        StructuralSolverIntegrationService, Depends(get_structural_solver_integration_service)
    ],
) -> IntegrationExecutionResponse:
    execution = solver_service.connect(project_id, software)
    return IntegrationExecutionResponse.from_domain(execution)


@router.post("/{project_id}/disconnect/{software}", response_model=IntegrationExecutionResponse)
def disconnect_solver_software(
    project_id: UUID,
    software: IntegrationSoftware,
    solver_service: Annotated[
        StructuralSolverIntegrationService, Depends(get_structural_solver_integration_service)
    ],
) -> IntegrationExecutionResponse:
    execution = solver_service.disconnect(project_id, software)
    return IntegrationExecutionResponse.from_domain(execution)


@router.post("/{project_id}/export/{software}", response_model=IntegrationExecutionResponse)
def export_project_model_to_solver(
    project_id: UUID,
    software: IntegrationSoftware,
    solver_service: Annotated[
        StructuralSolverIntegrationService, Depends(get_structural_solver_integration_service)
    ],
    pem_version: int | None = None,
) -> IntegrationExecutionResponse:
    execution = solver_service.export_model(project_id, software, pem_version=pem_version)
    return IntegrationExecutionResponse.from_domain(execution)


@router.post("/{project_id}/extract/{software}")
def extract_solver_results(
    project_id: UUID,
    software: IntegrationSoftware,
    solver_service: Annotated[
        StructuralSolverIntegrationService, Depends(get_structural_solver_integration_service)
    ],
    pem_version: int | None = None,
    analysis_run_id: UUID | None = None,
    external_model_identity: str | None = None,
) -> dict:
    return solver_service.extract_solver_results(
        project_id,
        software,
        pem_version=pem_version,
        analysis_run_id=analysis_run_id,
        external_model_identity=external_model_identity,
    )


@router.post("/execute", response_model=IntegrationResultResponse)
def execute_integration(
    body: IntegrationRequestBody,
    integration_service: Annotated[IntegrationService, Depends(get_integration_service)],
) -> IntegrationResultResponse:
    result = integration_service.execute(body.to_domain())
    return IntegrationResultResponse.from_domain(result)
