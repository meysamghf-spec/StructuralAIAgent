"""3D frame text exports (ETABS .e2k, SAFE .f2k, DXF) — /api/v1/frame3d."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.api.deps import get_current_account
from app.application import csi_text_export as cte
from app.application.analysis.frame3d_solver import SpaceFrameSolverError
from app.application.frame3d_chat_analysis import build_frame3d_payload, run_frame3d_for_export
from app.domain.models.user import AuthenticatedAccount

router = APIRouter(prefix="/frame3d", tags=["frame3d"])


class Frame3dExportRequest(BaseModel):
    format: str = Field(description="e2k | f2k | dxf_plans | dxf_3d")
    inputs: dict[str, Any] = Field(description="`inputs` of a frame3d_analysis result (plus optional `parsed_from_request`)")


@router.post("/export")
def export_frame3d(
    body: Frame3dExportRequest,
    _: Annotated[AuthenticatedAccount, Depends(get_current_account)],
) -> Response:
    meta = cte.FORMATS.get(body.format)
    if meta is None:
        raise HTTPException(status_code=422, detail=f"Unknown format {body.format!r}; use one of {sorted(cte.FORMATS)}")
    try:
        inp, raw, design = run_frame3d_for_export(body.inputs)
        content = cte.build_export(body.format, inp, raw, design)
    except (TypeError, ValueError, SpaceFrameSolverError) as exc:
        raise HTTPException(status_code=422, detail=f"Cannot export this model: {exc}") from exc
    return Response(
        content=content.encode("utf-8"),
        media_type=meta["mime"],
        headers={"Content-Disposition": f'attachment; filename="{meta["filename"]}"'},
    )


class Frame3dRunRequest(BaseModel):
    inputs: dict[str, Any] = Field(description="Frame3dInputs fields from the manual Model page (storeys, bays_x, bay_x_m, ...)")


@router.post("/run")
def run_frame3d_manual(
    body: Frame3dRunRequest,
    _: Annotated[AuthenticatedAccount, Depends(get_current_account)],
) -> dict[str, Any]:
    """Run the in-house 3D frame solver (+ 2800, Mabhas 9 design, footings) on manual-form inputs; same payload as chat."""
    try:
        payload = build_frame3d_payload("", manual_inputs=body.inputs)
    except (TypeError, ValueError, SpaceFrameSolverError) as exc:
        raise HTTPException(status_code=422, detail=f"Cannot analyse this model: {exc}") from exc
    return {"frame3d_analysis": payload}
