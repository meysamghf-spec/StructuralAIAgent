"""Project file REST endpoints — /api/v1/projects/{project_id}/files."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import Response

from app.api.deps import get_actor_id, get_file_ingestion_service, get_file_registry_service
from app.api.schemas.file import ProjectFileListResponse, ProjectFileResponse
from app.application.file_ingestion_service import FileIngestionService
from app.application.file_registry_service import FileRegistryService

router = APIRouter(prefix="/projects/{project_id}/files", tags=["files"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ProjectFileResponse)
async def upload_project_file(
    project_id: UUID,
    file: Annotated[UploadFile, File(...)],
    ingestion_service: Annotated[FileIngestionService, Depends(get_file_ingestion_service)],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> ProjectFileResponse:
    content = await file.read()
    record = ingestion_service.ingest_upload(
        project_id,
        filename=file.filename or "upload.txt",
        content=content,
        content_type=file.content_type,
        created_by=actor_id,
    )
    return ProjectFileResponse.from_domain(record)


@router.get("", response_model=ProjectFileListResponse)
def list_project_files(
    project_id: UUID,
    registry_service: Annotated[FileRegistryService, Depends(get_file_registry_service)],
) -> ProjectFileListResponse:
    files = registry_service.list_project_files(project_id)
    return ProjectFileListResponse(
        project_id=project_id,
        files=[ProjectFileResponse.from_domain(item) for item in files],
    )


@router.get("/{file_id}", response_model=ProjectFileResponse)
def get_project_file(
    project_id: UUID,
    file_id: UUID,
    registry_service: Annotated[FileRegistryService, Depends(get_file_registry_service)],
) -> ProjectFileResponse:
    record = registry_service.get_project_file(project_id, file_id)
    return ProjectFileResponse.from_domain(record)


@router.get("/{file_id}/content")
def download_project_file_content(
    project_id: UUID,
    file_id: UUID,
    ingestion_service: Annotated[FileIngestionService, Depends(get_file_ingestion_service)],
) -> Response:
    record, content = ingestion_service.get_file_content(project_id, file_id)
    media_type = record.content_type or "application/octet-stream"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{record.filename}"'},
    )
