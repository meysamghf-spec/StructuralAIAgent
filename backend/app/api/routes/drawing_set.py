"""PEM drawing-set index and PDF for one project."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.api.deps import get_accessible_project, get_pem_service
from app.api.schemas.drawing_set import (
    DrawingSetIndexResponse,
    DrawingSheetIndexItem,
    PendingDrawingSheet,
)
from app.application.drawing_set_query_service import DrawingSetQueryService
from app.application.project_service import PemService
from app.domain.models.drawing import DrawingSet
from app.infrastructure.reporting.drawing_set_pdf import render_drawing_set_pdf

router = APIRouter(
    prefix="/projects/{project_id}/drawing-set",
    tags=["drawing-set"],
    dependencies=[Depends(get_accessible_project)],
)


def get_drawing_set_query_service(
    pem_service: Annotated[PemService, Depends(get_pem_service)],
) -> DrawingSetQueryService:
    return DrawingSetQueryService(pem_service)


def _pending_sheets(drawing_set: DrawingSet) -> list[PendingDrawingSheet]:
    pending: list[PendingDrawingSheet] = []
    raw = drawing_set.metadata.get("pending_milestones")
    if not isinstance(raw, list):
        return pending
    produced = set(drawing_set.sheet_numbers)
    for item in raw:
        text = str(item).strip()
        if not text:
            continue
        number, _, title = text.partition(" ")
        if number in produced:
            continue
        pending.append(PendingDrawingSheet(sheet_number=number, title=title or number))
    return pending


def _index(drawing_set: DrawingSet) -> DrawingSetIndexResponse:
    if drawing_set.pem_version is None or drawing_set.source_snapshot_id is None:
        raise RuntimeError("Drawing set is missing its PEM snapshot")
    return DrawingSetIndexResponse(
        project_id=drawing_set.project_id,
        pem_snapshot_id=UUID(drawing_set.source_snapshot_id),
        pem_version=drawing_set.pem_version,
        drawing_set_id=drawing_set.id,
        generated_at=drawing_set.generated_at,
        sheets=[
            DrawingSheetIndexItem(
                sheet_number=sheet.sheet_number,
                title=sheet.title,
                discipline=sheet.discipline.value,
                availability=sheet.availability.value,
                schedule_family=(
                    str(sheet.metadata["schedule_family"])
                    if sheet.metadata.get("schedule_family")
                    else None
                ),
                missing_data=list(sheet.missing_data),
                content_signature=sheet.content_signature,
            )
            for sheet in drawing_set.sheets
        ],
        pending_sheets=_pending_sheets(drawing_set),
        disclaimers=list(drawing_set.disclaimers),
    )


@router.get("", response_model=DrawingSetIndexResponse)
def get_current_drawing_set(
    project_id: UUID,
    drawings: Annotated[DrawingSetQueryService, Depends(get_drawing_set_query_service)],
) -> DrawingSetIndexResponse:
    return _index(drawings.current_drawing_set(project_id))


@router.get("/pdf")
def download_current_drawing_set_pdf(
    project_id: UUID,
    drawings: Annotated[DrawingSetQueryService, Depends(get_drawing_set_query_service)],
) -> Response:
    drawing_set = drawings.current_drawing_set(project_id)
    pdf = render_drawing_set_pdf(drawing_set)
    version = drawing_set.pem_version if drawing_set.pem_version is not None else 0
    filename = f"drawing-set-{project_id}-v{version}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
