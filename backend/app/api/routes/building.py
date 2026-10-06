"""Building generation REST endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from app.api.deps import (
    get_accessible_project,
    get_actor_id,
    get_building_design_pipeline,
    get_pem_service,
)
from app.api.schemas.building import (
    BuildingGenerateResponse,
    BuildingViewResponse,
    GenerateBuildingRequest,
)
from app.application.building_design_pipeline import BuildingDesignPipeline
from app.application.building_view import serialize_building_view
from app.application.exceptions import ApplicationError, PemNotFoundError
from app.application.project_service import PemService
from app.infrastructure.config import get_settings

router = APIRouter(
    prefix="/projects/{project_id}/building",
    tags=["building"],
    dependencies=[Depends(get_accessible_project)],
)


@router.post("/generate", response_model=BuildingGenerateResponse)
def generate_building(
    project_id: UUID,
    body: GenerateBuildingRequest,
    pipeline: Annotated[BuildingDesignPipeline, Depends(get_building_design_pipeline)],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> BuildingGenerateResponse:
    result = pipeline.generate_from_brief(
        project_id,
        body.brief,
        created_by=actor_id,
        max_iterations=body.max_iterations,
        generate_drawings=body.generate_drawings,
    )
    view = serialize_building_view(result.assembled.pem) if result.assembled.status != "WAITING_FOR_INPUT" else {}
    return BuildingGenerateResponse(
        project_id=project_id,
        status=result.assembled.status,
        pem_version=result.pem_version,
        snapshot_id=result.snapshot_id,
        approval_request_id=result.approval_request_id,
        drawing_ids=result.drawing_ids,
        sheet_paths=result.sheet_paths,
        missing_inputs=result.assembled.missing_inputs,
        summary=result.summary,
        view=view,
    )


@router.get("", response_model=BuildingViewResponse)
def get_building(
    project_id: UUID,
    pem_service: Annotated[PemService, Depends(get_pem_service)],
) -> BuildingViewResponse:
    meta = pem_service.get_current_snapshot_meta(project_id)
    pem = pem_service.get_current_pem(project_id)
    if meta is None or pem is None:
        raise PemNotFoundError(project_id)
    return BuildingViewResponse(
        project_id=project_id,
        pem_version=meta.version,
        snapshot_id=meta.id,
        view=serialize_building_view(pem),
        sheet_names=_sheet_names(project_id),
    )


@router.get("/sheets/{sheet_name}")
def download_sheet(
    project_id: UUID,
    sheet_name: str,
) -> FileResponse:
    root = (get_settings().resolved_file_storage_root / "sheets" / str(project_id)).resolve()
    path = (root / Path(sheet_name).name).resolve()
    if not str(path).startswith(str(root)) or not path.is_file():
        raise ApplicationError("SHEET_NOT_FOUND", "Drawing sheet was not found", status_code=404)
    return FileResponse(path, media_type="application/pdf", filename=path.name)


def _sheet_names(project_id: UUID) -> list[str]:
    folder = get_settings().resolved_file_storage_root / "sheets" / str(project_id)
    if not folder.is_dir():
        return []
    return sorted(path.name for path in folder.glob("*.pdf"))
