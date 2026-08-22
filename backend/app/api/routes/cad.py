"""CAD drawing REST endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import (
    get_accessible_project,
    get_actor_id,
    get_cad_generation_service,
    get_current_account,
    get_entitlement_authorization_service,
    get_project_access_service,
)
from app.api.schemas.cad import (
    CadCapabilityResponse,
    CadDrawingListResponse,
    CadDrawingRequestBody,
    CadDrawingResponse,
)
from app.application.cad_generation_service import CadGenerationService
from app.application.entitlement_authorization_service import EntitlementAuthorizationService
from app.application.project_access_service import ProjectAccessService
from app.domain.models.platform_features import PlatformFeature
from app.domain.models.user import AuthenticatedAccount

router = APIRouter(prefix="/cad", tags=["cad"])

project_cad_router = APIRouter(
    prefix="/{project_id}",
    dependencies=[Depends(get_accessible_project)],
)


@router.get("/capabilities/autocad", response_model=CadCapabilityResponse)
def get_autocad_capability(
    cad_service: Annotated[CadGenerationService, Depends(get_cad_generation_service)],
) -> CadCapabilityResponse:
    capability = cad_service.get_autocad_capability()
    return CadCapabilityResponse(
        software=capability.get("software", "AUTOCAD"),
        availability=capability.get("availability", "REQUIRES_LOCAL_SOFTWARE"),
        message=capability.get("message", "AutoCAD capability is not available."),
        metadata=capability.get("metadata", {}),
    )


@router.post("/generate", response_model=CadDrawingResponse)
def generate_cad_drawing(
    body: CadDrawingRequestBody,
    cad_service: Annotated[CadGenerationService, Depends(get_cad_generation_service)],
    actor_id: Annotated[str, Depends(get_actor_id)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    access: Annotated[ProjectAccessService, Depends(get_project_access_service)],
    entitlements: Annotated[
        EntitlementAuthorizationService, Depends(get_entitlement_authorization_service)
    ],
) -> CadDrawingResponse:
    access.require_project(body.project_id, account)
    entitlements.require_feature(account.account_id, PlatformFeature.CAD_PLAN_GENERATION)
    drawing = cad_service.generate_drawing(body.to_domain(), created_by=actor_id)
    return CadDrawingResponse.from_domain(drawing)


@project_cad_router.get("/drawings", response_model=CadDrawingListResponse)
def list_cad_drawings(
    project_id: UUID,
    cad_service: Annotated[CadGenerationService, Depends(get_cad_generation_service)],
) -> CadDrawingListResponse:
    drawings = cad_service.list_drawings(project_id)
    return CadDrawingListResponse(
        project_id=project_id,
        drawings=[CadDrawingResponse.from_domain(item) for item in drawings],
    )


@project_cad_router.get("/drawings/{drawing_id}", response_model=CadDrawingResponse)
def get_cad_drawing(
    project_id: UUID,
    drawing_id: UUID,
    cad_service: Annotated[CadGenerationService, Depends(get_cad_generation_service)],
) -> CadDrawingResponse:
    drawing = cad_service.get_drawing(project_id, drawing_id)
    return CadDrawingResponse.from_domain(drawing)


@project_cad_router.get("/drawings/{drawing_id}/validation")
def get_cad_drawing_validation(
    project_id: UUID,
    drawing_id: UUID,
    cad_service: Annotated[CadGenerationService, Depends(get_cad_generation_service)],
) -> dict:
    drawing = cad_service.get_drawing(project_id, drawing_id)
    return cad_service.build_validation_report(drawing)


router.include_router(project_cad_router)
