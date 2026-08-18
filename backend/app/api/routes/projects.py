"""Project REST endpoints — /api/v1/projects."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import get_actor_id, get_project_service
from app.api.schemas.common import ProjectResponse, RevisionResponse
from app.api.schemas.project import (
    CreateProjectRequest,
    CreateProjectResponse,
    ProjectListResponse,
)
from app.application.exceptions import ProjectNotFoundError
from app.application.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CreateProjectResponse)
def create_project(
    body: CreateProjectRequest,
    project_service: Annotated[ProjectService, Depends(get_project_service)],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> CreateProjectResponse:
    result = project_service.create_project(
        name=body.name,
        description=body.description,
        created_by=actor_id,
    )

    return CreateProjectResponse(
        project=ProjectResponse.model_validate(result.project.model_dump()),
        pem_version=result.snapshot_version,
        snapshot_id=str(result.snapshot_id),
        revision=RevisionResponse.from_domain(result.revision),
    )


@router.get("", response_model=ProjectListResponse)
def list_projects(
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectListResponse:
    projects = project_service.list_projects()
    return ProjectListResponse(
        projects=[ProjectResponse.model_validate(p.model_dump()) for p in projects]
    )


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: UUID,
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectResponse:
    project = project_service.get_project(project_id)
    if project is None:
        raise ProjectNotFoundError(project_id)
    return ProjectResponse.model_validate(project.model_dump())
