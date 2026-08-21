"""Project engineering model REST endpoints — /api/v1/projects/{project_id}/model."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import get_actor_id, get_pem_model_service, get_project_service
from app.api.schemas.model import (
    AnalysisModelUpdateRequest,
    DesignParametersUpdateRequest,
    GeometryUpdateRequest,
    LoadCasesUpdateRequest,
    LoadCombinationsUpdateRequest,
    MaterialsUpdateRequest,
    MembersUpdateRequest,
    ModelEnvelopeResponse,
    ModelSummaryResponse,
    ModelUpdateResponse,
    ModelValidationResponse,
    SectionsUpdateRequest,
    SupportsUpdateRequest,
)
from app.application.exceptions import ProjectNotFoundError
from app.application.pem_model_service import PemModelService
from app.application.project_service import ProjectService

router = APIRouter(prefix="/projects/{project_id}/model", tags=["model"])


def _ensure_project(project_service: ProjectService, project_id: UUID) -> None:
    if project_service.get_project(project_id) is None:
        raise ProjectNotFoundError(project_id)


@router.get("", response_model=ModelEnvelopeResponse)
def get_current_model(
    project_id: UUID,
    project_service: Annotated[ProjectService, Depends(get_project_service)],
    model_service: Annotated[PemModelService, Depends(get_pem_model_service)],
) -> ModelEnvelopeResponse:
    _ensure_project(project_service, project_id)
    pem, version, snapshot_id = model_service.get_current_model(project_id)
    return ModelEnvelopeResponse(
        project_id=project_id,
        pem_version=version,
        snapshot_id=snapshot_id,
        structural_model=pem.structural_model,
        code_configuration=pem.code_configuration.model_dump(mode="json"),
        unit_configuration=pem.unit_configuration.model_dump(mode="json"),
    )


@router.get("/summary", response_model=ModelSummaryResponse)
def get_model_summary(
    project_id: UUID,
    project_service: Annotated[ProjectService, Depends(get_project_service)],
    model_service: Annotated[PemModelService, Depends(get_pem_model_service)],
) -> ModelSummaryResponse:
    _ensure_project(project_service, project_id)
    return ModelSummaryResponse.from_domain(model_service.get_model_summary(project_id))


@router.post("/validate", response_model=ModelValidationResponse)
def validate_model(
    project_id: UUID,
    project_service: Annotated[ProjectService, Depends(get_project_service)],
    model_service: Annotated[PemModelService, Depends(get_pem_model_service)],
) -> ModelValidationResponse:
    _ensure_project(project_service, project_id)
    return ModelValidationResponse.from_domain(model_service.validate_model(project_id))


@router.put("/geometry", response_model=ModelUpdateResponse)
def update_geometry(
    project_id: UUID,
    body: GeometryUpdateRequest,
    project_service: Annotated[ProjectService, Depends(get_project_service)],
    model_service: Annotated[PemModelService, Depends(get_pem_model_service)],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> ModelUpdateResponse:
    _ensure_project(project_service, project_id)
    result = model_service.update_geometry(
        project_id,
        body.geometry,
        summary=body.summary,
        created_by=actor_id,
        request_approval=body.request_approval,
    )
    return ModelUpdateResponse.from_domain(result)


@router.put("/materials", response_model=ModelUpdateResponse)
def update_materials(
    project_id: UUID,
    body: MaterialsUpdateRequest,
    project_service: Annotated[ProjectService, Depends(get_project_service)],
    model_service: Annotated[PemModelService, Depends(get_pem_model_service)],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> ModelUpdateResponse:
    _ensure_project(project_service, project_id)
    result = model_service.update_materials(
        project_id,
        body.materials,
        summary=body.summary,
        created_by=actor_id,
        request_approval=body.request_approval,
    )
    return ModelUpdateResponse.from_domain(result)


@router.put("/sections", response_model=ModelUpdateResponse)
def update_sections(
    project_id: UUID,
    body: SectionsUpdateRequest,
    project_service: Annotated[ProjectService, Depends(get_project_service)],
    model_service: Annotated[PemModelService, Depends(get_pem_model_service)],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> ModelUpdateResponse:
    _ensure_project(project_service, project_id)
    result = model_service.update_sections(
        project_id,
        body.sections,
        summary=body.summary,
        created_by=actor_id,
        request_approval=body.request_approval,
    )
    return ModelUpdateResponse.from_domain(result)


@router.put("/members", response_model=ModelUpdateResponse)
def update_members(
    project_id: UUID,
    body: MembersUpdateRequest,
    project_service: Annotated[ProjectService, Depends(get_project_service)],
    model_service: Annotated[PemModelService, Depends(get_pem_model_service)],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> ModelUpdateResponse:
    _ensure_project(project_service, project_id)
    result = model_service.update_members(
        project_id,
        body.members,
        summary=body.summary,
        created_by=actor_id,
        request_approval=body.request_approval,
    )
    return ModelUpdateResponse.from_domain(result)


@router.put("/supports", response_model=ModelUpdateResponse)
def update_supports(
    project_id: UUID,
    body: SupportsUpdateRequest,
    project_service: Annotated[ProjectService, Depends(get_project_service)],
    model_service: Annotated[PemModelService, Depends(get_pem_model_service)],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> ModelUpdateResponse:
    _ensure_project(project_service, project_id)
    result = model_service.update_supports(
        project_id,
        body.supports,
        summary=body.summary,
        created_by=actor_id,
        request_approval=body.request_approval,
    )
    return ModelUpdateResponse.from_domain(result)


@router.put("/load-cases", response_model=ModelUpdateResponse)
def update_load_cases(
    project_id: UUID,
    body: LoadCasesUpdateRequest,
    project_service: Annotated[ProjectService, Depends(get_project_service)],
    model_service: Annotated[PemModelService, Depends(get_pem_model_service)],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> ModelUpdateResponse:
    _ensure_project(project_service, project_id)
    result = model_service.update_load_cases(
        project_id,
        body.load_cases,
        summary=body.summary,
        created_by=actor_id,
        request_approval=body.request_approval,
    )
    return ModelUpdateResponse.from_domain(result)


@router.put("/load-combinations", response_model=ModelUpdateResponse)
def update_load_combinations(
    project_id: UUID,
    body: LoadCombinationsUpdateRequest,
    project_service: Annotated[ProjectService, Depends(get_project_service)],
    model_service: Annotated[PemModelService, Depends(get_pem_model_service)],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> ModelUpdateResponse:
    _ensure_project(project_service, project_id)
    result = model_service.update_load_combinations(
        project_id,
        body.load_combinations,
        summary=body.summary,
        created_by=actor_id,
        request_approval=body.request_approval,
    )
    return ModelUpdateResponse.from_domain(result)


@router.put("/analysis-model", response_model=ModelUpdateResponse)
def update_analysis_model(
    project_id: UUID,
    body: AnalysisModelUpdateRequest,
    project_service: Annotated[ProjectService, Depends(get_project_service)],
    model_service: Annotated[PemModelService, Depends(get_pem_model_service)],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> ModelUpdateResponse:
    _ensure_project(project_service, project_id)
    result = model_service.update_analysis_model(
        project_id,
        body.analysis_model,
        summary=body.summary,
        created_by=actor_id,
        request_approval=body.request_approval,
    )
    return ModelUpdateResponse.from_domain(result)


@router.put("/design-parameters", response_model=ModelUpdateResponse)
def update_design_parameters(
    project_id: UUID,
    body: DesignParametersUpdateRequest,
    project_service: Annotated[ProjectService, Depends(get_project_service)],
    model_service: Annotated[PemModelService, Depends(get_pem_model_service)],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> ModelUpdateResponse:
    _ensure_project(project_service, project_id)
    result = model_service.update_design_parameters(
        project_id,
        body.design_parameters,
        summary=body.summary,
        created_by=actor_id,
        request_approval=body.request_approval,
    )
    return ModelUpdateResponse.from_domain(result)
