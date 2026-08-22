"""Project REST endpoints — /api/v1/projects."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import (
    get_accessible_project,
    get_actor_id,
    get_current_account,
    get_project_access_service,
    get_project_context_assembly_service,
    get_project_service,
)
from app.api.schemas.common import ProjectResponse, RevisionResponse
from app.api.schemas.project import (
    CreateProjectRequest,
    CreateProjectResponse,
    ProjectListResponse,
)
from app.api.schemas.project_context import ProjectContextAssemblyResponse
from app.application.project_access_service import ProjectAccessService
from app.application.project_context_assembly_service import ProjectContextAssemblyService
from app.application.project_service import ProjectService
from app.domain.models.project import Project
from app.domain.models.user import AuthenticatedAccount

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CreateProjectResponse)
def create_project(
    body: CreateProjectRequest,
    project_service: Annotated[ProjectService, Depends(get_project_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
) -> CreateProjectResponse:
    result = project_service.create_project(
        name=body.name,
        description=body.description,
        created_by=account.account_id,
        owner_account_id=account.account_id,
    )

    return CreateProjectResponse(
        project=ProjectResponse.model_validate(result.project.model_dump()),
        pem_version=result.snapshot_version,
        snapshot_id=str(result.snapshot_id),
        revision=RevisionResponse.from_domain(result.revision),
    )


@router.get("", response_model=ProjectListResponse)
def list_projects(
    access_service: Annotated[ProjectAccessService, Depends(get_project_access_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
) -> ProjectListResponse:
    projects = access_service.list_accessible_projects(account)
    return ProjectListResponse(
        projects=[ProjectResponse.model_validate(p.model_dump()) for p in projects]
    )


@router.get("/{project_id}/context", response_model=ProjectContextAssemblyResponse)
def get_project_context(
    project_id: UUID,
    _: Annotated[Project, Depends(get_accessible_project)],
    context_service: Annotated[
        ProjectContextAssemblyService,
        Depends(get_project_context_assembly_service),
    ],
) -> ProjectContextAssemblyResponse:
    context = context_service.assemble(project_id)
    return ProjectContextAssemblyResponse.from_domain(context)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project: Annotated[Project, Depends(get_accessible_project)],
) -> ProjectResponse:
    return ProjectResponse.model_validate(project.model_dump())
