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
    return FileResponse(_dir(jid, account) / "drawing.dxf", media_type="application/dxf", filename=f"saia-{jid[:8]}.dxf")


@router.get("/jobs/{jid}/preview.svg")
def preview(jid: str, account: Annotated[AuthenticatedAccount, Depends(get_current_account)]):
    return Response((_dir(jid, account) / "preview.svg").read_text("utf-8"), media_type="image/svg+xml")


@router.post("/jobs/{jid}/review")
def do_review(jid: str, body: ReviewBody, account: Annotated[AuthenticatedAccount, Depends(get_current_account)]):
    _dir(jid, account)
    return service.review(jid, _owner(account), body.decision, body.note)


# ---------------------------------------------------------------- architectural sets (plans, sections, elevations ...)
class ArchSetBody(BaseModel):
    prompt: str = Field(default="", max_length=2000)
    project_id: str | None = None
    program: dict | None = None


_MEDIA = {".dxf": "application/dxf", ".pdf": "application/pdf", ".png": "image/png", ".zip": "application/zip"}


@router.get("/arch-sets")
def arch_sets(account: Annotated[AuthenticatedAccount, Depends(get_current_account)], project_id: str | None = None):
    from app.application.architecture import service as arch
    keys = ("id", "title", "created_at", "project_id", "sheets", "pdf", "zip", "checks", "assumptions", "warnings", "project_files")
    return {"sets": [{k: m.get(k) for k in keys} for m in arch.list_sets(_owner(account), project_id)]}


@router.post("/arch-sets")
def create_arch_set(body: ArchSetBody, account: Annotated[AuthenticatedAccount, Depends(get_current_account)]):
    from app.application.architecture import program as prog
    from app.application.architecture import service as arch
    p = prog.BuildingProgram.from_dict(body.program) if body.program else prog.BuildingProgram()
    if body.prompt:
        p, _ = prog.parse(body.prompt, p)
    return arch.create_set(p, owner=_owner(account), project_id=body.project_id, source=body.prompt)


@router.get("/arch-sets/{sid}")
def get_arch_set(sid: str, account: Annotated[AuthenticatedAccount, Depends(get_current_account)]):
    from app.application.architecture import service as arch
    m = arch.get_set(sid, _owner(account))
    if not m:
        raise HTTPException(404, "Set not found")
    return m


@router.get("/arch-sets/{sid}/files/{name}")
def arch_file(sid: str, name: str, account: Annotated[AuthenticatedAccount, Depends(get_current_account)]):
    from pathlib import Path as _P

    from app.application.architecture import service as arch
    f = arch.file_path(sid, _owner(account), name)
    if f is None:
        raise HTTPException(404, "File not found")
    ext = _P(name).suffix.lower()
    return FileResponse(f, media_type=_MEDIA.get(ext, "application/octet-stream"),
                        filename=None if ext == ".png" else f"arch-{sid[:6]}-{name}")
# ---------------------------------------------------------------- structural drawing set (S-sheets)
from uuid import UUID as _UUID  # noqa: E402

from app.api.deps import (  # noqa: E402
    get_conversation_service,
    get_file_ingestion_service,
    get_project_access_service,
)


class StructuralSetBody(BaseModel):
    project_id: str | None = None
    inputs: dict | None = None


def latest_frame_inputs(conv_service, account, project_id: str | None) -> dict | None:
    if not project_id:
        return None
    for r in conv_service.list_project_chat_runs(account, _UUID(project_id)):
        if r.get("kind") == "frame3d_analysis" and r.get("inputs"):
            return r["inputs"]
    return None


@router.post("/structural-set")
def structural_set(body: StructuralSetBody, account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
                   conv=Depends(get_conversation_service), files=Depends(get_file_ingestion_service),
                   access=Depends(get_project_access_service)):
    from app.application.autocad import structural_set as ss

    project = None
    if body.project_id:
        try:
            project = access.require_project(_UUID(body.project_id), account)
        except ValueError:
            raise HTTPException(422, "invalid project_id")
    inputs = body.inputs or latest_frame_inputs(conv, account, body.project_id)
    if not inputs:
        raise HTTPException(409, "No 3D frame analysis in this project yet — run one in chat first "
                                 "(e.g. '3 bays x 5 m, 2 bays y 4 m, 4 storeys 3.2 m').")
    pid = body.project_id

    def _save(name: str, data: bytes, ctype: str):
        return str(files.ingest_upload(_UUID(pid), filename=name, content=data, content_type=ctype,
                                       created_by=account.account_id).id)

    try:
        return ss.generate_and_store(inputs, owner=_owner(account), project_id=pid,
                                     project_name=getattr(project, "name", None), save_project_file=_save if pid else None)
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@router.get("/structural-sets")
def structural_sets(account: Annotated[AuthenticatedAccount, Depends(get_current_account)], project_id: str | None = None):
    from app.application.autocad import structural_set as ss
    return {"sets": ss.list_sets(_owner(account), project_id)}


@router.get("/structural-sets/{sid}/set.pdf")
def structural_set_pdf(sid: str, account: Annotated[AuthenticatedAccount, Depends(get_current_account)]):
    from app.application.autocad import structural_set as ss
    try:
        p = ss.set_dir(sid, _owner(account)) / "set.pdf"
    except (FileNotFoundError, OSError):
        raise HTTPException(404, "not found")
    if not p.exists():
        raise HTTPException(404, "no PDF for this set")
    return FileResponse(p, media_type="application/pdf", filename="structural-drawing-set.pdf")
