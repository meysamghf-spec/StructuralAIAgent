"""PEM REST endpoints — /api/v1/projects/{project_id}/pem."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import get_accessible_project, get_actor_id, get_pem_revision_service, get_pem_service
from app.api.schemas.common import RevisionResponse
from app.api.schemas.pem import (
    PemEnvelopeResponse,
    PemVersionListResponse,
    UpdatePemRequest,
    UpdatePemResponse,
)
from app.application.exceptions import PemNotFoundError
from app.application.pem_revision_service import PemRevisionService
from app.application.project_service import PemService

router = APIRouter(
    prefix="/projects/{project_id}/pem",
    tags=["pem"],
    dependencies=[Depends(get_accessible_project)],
)


@router.get("/current", response_model=PemEnvelopeResponse)
def get_current_pem(
    project_id: UUID,
    pem_service: Annotated[PemService, Depends(get_pem_service)],
) -> PemEnvelopeResponse:
    meta = pem_service.get_current_snapshot_meta(project_id)
    if meta is None:
        raise PemNotFoundError(project_id)
    pem = pem_service.get_current_pem(project_id)
    assert pem is not None
    return PemEnvelopeResponse(
        project_id=meta.project_id,
        version=meta.version,
        snapshot_id=meta.id,
        is_current=meta.is_current,
        pem=pem,
    )


@router.get("/versions", response_model=PemVersionListResponse)
def list_pem_versions(
    project_id: UUID,
    pem_service: Annotated[PemService, Depends(get_pem_service)],
) -> PemVersionListResponse:
    return PemVersionListResponse(
        project_id=project_id,
        versions=pem_service.list_pem_versions(project_id),
    )


@router.get("/versions/{version}", response_model=PemEnvelopeResponse)
def get_pem_version(
    project_id: UUID,
    version: int,
    pem_service: Annotated[PemService, Depends(get_pem_service)],
) -> PemEnvelopeResponse:
    meta = pem_service.get_snapshot_meta_by_version(project_id, version)
    if meta is None:
        raise PemNotFoundError(project_id, version=version)
    pem = pem_service.get_pem_version(project_id, version)
    assert pem is not None
    return PemEnvelopeResponse(
        project_id=meta.project_id,
        version=meta.version,
        snapshot_id=meta.id,
        is_current=meta.is_current,
        pem=pem,
    )


@router.put("", response_model=UpdatePemResponse)
def update_pem(
    project_id: UUID,
    body: UpdatePemRequest,
    pem_revision_service: Annotated[PemRevisionService, Depends(get_pem_revision_service)],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> UpdatePemResponse:
    result = pem_revision_service.update_pem(
        project_id,
        body.pem,
        change_type=body.change_type,
        summary=body.summary,
        created_by=actor_id,
        metadata=body.metadata,
    )
    return UpdatePemResponse(
        pem_version=result.pem_version,
        snapshot_id=result.snapshot_id,
        before_snapshot_id=result.before_snapshot_id,
        revision=RevisionResponse.from_domain(result.revision),
    )
