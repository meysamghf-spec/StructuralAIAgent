"""Revision REST endpoints — /api/v1/projects/{project_id}/revisions."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import get_revision_service
from app.api.schemas.common import RevisionResponse
from app.api.schemas.revision import RevisionListResponse
from app.application.revision_service import RevisionService

router = APIRouter(prefix="/projects/{project_id}/revisions", tags=["revisions"])


@router.get("", response_model=RevisionListResponse)
def list_revisions(
    project_id: UUID,
    revision_service: Annotated[RevisionService, Depends(get_revision_service)],
) -> RevisionListResponse:
    revisions = revision_service.list_revisions(project_id)
    return RevisionListResponse(
        revisions=[RevisionResponse.from_domain(r) for r in revisions]
    )


@router.get("/{revision_number}", response_model=RevisionResponse)
def get_revision(
    project_id: UUID,
    revision_number: int,
    revision_service: Annotated[RevisionService, Depends(get_revision_service)],
) -> RevisionResponse:
    revision = revision_service.get_revision(project_id, revision_number)
    return RevisionResponse.from_domain(revision)
