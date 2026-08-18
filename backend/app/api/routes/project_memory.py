"""Project Memory REST endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import get_project_memory_service
from app.api.schemas.project_memory import (
    ProjectMemoryCreateRequest,
    ProjectMemoryContextResponse,
    ProjectMemoryListResponse,
    ProjectMemoryResponse,
)
from app.application.exceptions import ProjectMemoryNotFoundError
from app.application.project_memory_service import ProjectMemoryService
from app.domain.models.project_memory import MemoryType

router = APIRouter(
    prefix="/projects/{project_id}/memory",
    tags=["project-memory"],
)


@router.post(
    "",
    response_model=ProjectMemoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_memory(
    project_id: UUID,
    request: ProjectMemoryCreateRequest,
    memory_service: Annotated[
        ProjectMemoryService,
        Depends(get_project_memory_service),
    ],
) -> ProjectMemoryResponse:
    memory = memory_service.create_memory(
        project_id,
        request.memory_type,
        request.content,
        source_type=request.source_type,
        source_id=request.source_id,
        confidence=request.confidence,
        metadata=request.metadata,
        created_by=request.created_by,
    )
    return ProjectMemoryResponse.from_domain(memory)


@router.get(
    "",
    response_model=ProjectMemoryListResponse,
)
def list_memories(
    project_id: UUID,
    memory_service: Annotated[
        ProjectMemoryService,
        Depends(get_project_memory_service),
    ],
    source_type: str | None = Query(default=None),
    source_id: UUID | None = Query(default=None),
    memory_type: MemoryType | None = Query(default=None),
) -> ProjectMemoryListResponse:
    if source_type is not None or source_id is not None or memory_type is not None:
        memories = memory_service.retrieve_memories(
            project_id,
            source_type=source_type,
            source_id=source_id,
            memory_type=memory_type,
        )
    else:
        memories = memory_service.list_memories(project_id)
    return ProjectMemoryListResponse(
        memories=[ProjectMemoryResponse.from_domain(m) for m in memories]
    )


@router.get(
    "/context",
    response_model=ProjectMemoryContextResponse,
)
def get_project_memory_context(
    project_id: UUID,
    memory_service: Annotated[
        ProjectMemoryService,
        Depends(get_project_memory_service),
    ],
) -> ProjectMemoryContextResponse:
    context = memory_service.get_project_context(project_id)
    return ProjectMemoryContextResponse.from_domain(context)


@router.get(
    "/type/{memory_type}",
    response_model=ProjectMemoryListResponse,
)
def list_memories_by_type(
    project_id: UUID,
    memory_type: MemoryType,
    memory_service: Annotated[
        ProjectMemoryService,
        Depends(get_project_memory_service),
    ],
) -> ProjectMemoryListResponse:
    memories = memory_service.list_memories_by_type(
        project_id,
        memory_type,
    )
    return ProjectMemoryListResponse(
        memories=[ProjectMemoryResponse.from_domain(m) for m in memories]
    )


@router.get(
    "/{memory_id}",
    response_model=ProjectMemoryResponse,
)
def get_memory(
    project_id: UUID,
    memory_id: UUID,
    memory_service: Annotated[
        ProjectMemoryService,
        Depends(get_project_memory_service),
    ],
) -> ProjectMemoryResponse:
    memory = memory_service.get_memory(project_id, memory_id)

    if memory is None:
        raise ProjectMemoryNotFoundError(project_id, memory_id)

    return ProjectMemoryResponse.from_domain(memory)


@router.delete(
    "/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_memory(
    project_id: UUID,
    memory_id: UUID,
    memory_service: Annotated[
        ProjectMemoryService,
        Depends(get_project_memory_service),
    ],
) -> Response:
    deleted = memory_service.delete_memory(project_id, memory_id)

    if not deleted:
        raise ProjectMemoryNotFoundError(project_id, memory_id)

    return Response(status_code=status.HTTP_204_NO_CONTENT)
