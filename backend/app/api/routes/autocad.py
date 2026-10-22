"""AutoCAD v1: prompt -> DXF, PDF/image -> DXF, engineer review."""
from __future__ import annotations

import json
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from app.api.deps import get_current_account
from app.application.autocad import service
from app.domain.models.user import AuthenticatedAccount

router = APIRouter(prefix="/autocad", tags=["autocad"])
MAX_UPLOAD = 20 * 1024 * 1024


def _owner(acc: AuthenticatedAccount) -> str:
    return str(acc.account_id)


class PromptBody(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)


class ReviewBody(BaseModel):
    decision: Literal["accept", "flag"]
    note: str = ""


@router.get("/sheets")
def sheets():
    return {"sheets": service.sheet_index()}


@router.post("/prompt")
def from_prompt(body: PromptBody, account: Annotated[AuthenticatedAccount, Depends(get_current_account)]):
    from app.application.autocad.floor_plan import generate_from_prompt
    try:
        doc, summary = generate_from_prompt(body.prompt)
    except Exception as exc:  # parser/generator errors -> friendly 422
        raise HTTPException(422, f"Could not build a plan from this prompt: {exc}") from exc
    return service.save_job(doc, summary, kind="prompt", owner=_owner(account), source=body.prompt)


@router.post("/vectorize")
async def from_upload(account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
                      file: UploadFile = File(...), real_width_m: float | None = Form(None)):
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "File too large (max 20 MB).")
    from app.application.autocad.vectorize import vectorize
    try:
        doc, summary = vectorize(data, file.filename or "upload", real_width_m=real_width_m)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return service.save_job(doc, summary, kind="vectorize", owner=_owner(account), source=file.filename or "upload")


def _dir(jid: str, account):
    try:
        return service.job_dir(jid, _owner(account))
    except (FileNotFoundError, OSError):
        raise HTTPException(404, "Drawing not found")


@router.get("/jobs")
def jobs(account: Annotated[AuthenticatedAccount, Depends(get_current_account)], project_id: str | None = None):
    return {"jobs": service.list_jobs(_owner(account), project_id)}


@router.get("/jobs/{jid}")
def get_job(jid: str, account: Annotated[AuthenticatedAccount, Depends(get_current_account)]):
    d = _dir(jid, account)
    return {**json.loads((d / "meta.json").read_text("utf-8")), "preview_svg": (d / "preview.svg").read_text("utf-8")}


@router.get("/jobs/{jid}/drawing.dxf")
def download(jid: str, account: Annotated[AuthenticatedAccount, Depends(get_current_account)]):
    return FileResponse(_dir(jid, account) / "drawing.dxf", media_type="application/dxf", filename=f"structuralai-{jid[:8]}.dxf")


@router.get("/jobs/{jid}/preview.svg")
def preview(jid: str, account: Annotated[AuthenticatedAccount, Depends(get_current_account)]):
    return Response((_dir(jid, account) / "preview.svg").read_text("utf-8"), media_type="image/svg+xml")


@router.post("/jobs/{jid}/review")
def do_review(jid: str, body: ReviewBody, account: Annotated[AuthenticatedAccount, Depends(get_current_account)]):
    _dir(jid, account)
    return service.review(jid, _owner(account), body.decision, body.note)
