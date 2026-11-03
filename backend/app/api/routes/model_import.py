"""Import ETABS .e2k (next: .s2k / .f2k / .dxf) into a project's model, engineer review, analysis — /api/v1/model-import.

Parsing and analysis are deterministic (SAIA's own parser + 3D direct-stiffness solver); no LLM is involved.
State is saved per project as a ``*.saia-import.json`` project file (plus the original upload), so no DB migration.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.api.deps import (
    get_current_account, get_file_ingestion_service, get_file_registry_service, get_project_access_service,
)
from app.application.billing import service as billing
from app.application.model_import import ImportError_, analyze_imported_model, parse_model_file, review_summary
from app.application.model_import.analyze import apply_review
from app.application.model_import.common import MAX_IMPORT_BYTES
from app.domain.models.user import AuthenticatedAccount

router = APIRouter(prefix="/model-import", tags=["model-import"])
STATE_SUFFIX = ".saia-import.json"


def _access(project_id: str | None, acc, access) -> UUID | None:
    if not project_id:
        return None
    try:
        pid = UUID(project_id)
        access.require_project(pid, acc)
    except ValueError as exc:
        raise HTTPException(422, "invalid project_id") from exc
    return pid


def _save_state(files, pid: UUID | None, acc, state: dict[str, Any]) -> str:
    if pid is None:
        return ""
    stem = str(state["model"].get("filename") or "model").rsplit(".", 1)[0][:60] or "model"
    try:
        rec = files.ingest_upload(pid, filename=f"{stem}{STATE_SUFFIX}", content=json.dumps(state).encode("utf-8"),
                                  content_type="application/json", created_by=acc.account_id)
        return str(rec.id)
    except Exception:  # noqa: BLE001 — persistence is best effort; the response still carries the full state
        import logging; logging.getLogger(__name__).exception("model-import state save failed")
        return ""


def _state(model: dict[str, Any], stage: str, analysis: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"version": 1, "stage": stage, "saved_at": datetime.now(timezone.utc).isoformat(),
            "model": model, "review": review_summary(model), "analysis": analysis}


@router.post("/parse")
async def parse_import(
    acc: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    file: Annotated[UploadFile, File(...)],
    project_id: Annotated[str | None, Form()] = None,
    files=Depends(get_file_ingestion_service),
    access=Depends(get_project_access_service),
) -> dict[str, Any]:
    pid = _access(project_id, acc, access)
    data = await file.read(MAX_IMPORT_BYTES + 1)
    try:
        model = parse_model_file(file.filename or "", data)
    except ImportError_ as exc:
        raise HTTPException(422, {"code": exc.code, "en": exc.en, "fa": exc.fa}) from exc
    if pid is not None:
        try:
            files.ingest_upload(pid, filename=file.filename or "model.e2k", content=data,
                                content_type="application/octet-stream", created_by=acc.account_id)
        except Exception:  # noqa: BLE001
            pass
    state = _state(model, "review")
    state["state_file_id"] = _save_state(files, pid, acc, state)
    return state


class ReviewRequest(BaseModel):
    model: dict[str, Any] = Field(description="model returned by /parse (or a previous /review)")
    edits: dict[str, Any] = Field(default_factory=dict, description="sections, materials, beam_line_loads, confirmed")
    project_id: str | None = None


@router.post("/review")
def review_import(body: ReviewRequest, acc: Annotated[AuthenticatedAccount, Depends(get_current_account)],
                  files=Depends(get_file_ingestion_service), access=Depends(get_project_access_service)) -> dict[str, Any]:
    pid = _access(body.project_id, acc, access)
    try:
        model = apply_review(body.model, body.edits)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(422, f"Invalid model or edits: {exc}") from exc
    state = _state(model, "review")
    state["state_file_id"] = _save_state(files, pid, acc, state)
    return state


class AnalyzeRequest(BaseModel):
    model: dict[str, Any]
    project_id: str | None = None


@router.post("/analyze")
def analyze_import(body: AnalyzeRequest, acc: Annotated[AuthenticatedAccount, Depends(get_current_account)],
                   files=Depends(get_file_ingestion_service), access=Depends(get_project_access_service)) -> dict[str, Any]:
    pid = _access(body.project_id, acc, access)
    model = body.model
    review = review_summary(model)
    if not review["can_analyze"]:
        raise HTTPException(409, {"en": "Resolve the blocking review items first.", "fa": "ابتدا موارد مسدودکننده‌ی بازبینی را برطرف کنید.",
                                  "blocking": [i for i in review["issues"] if i["severity"] == "blocking"]})
    unconfirmed = review["requires_confirmation"]
    if unconfirmed:
        raise HTTPException(409, {"en": "Confirm every approximated / ignored item in the engineer review before analysis.",
                                  "fa": "قبل از تحلیل، همه‌ی موارد تقریبی یا نادیده‌گرفته‌شده را در بازبینی مهندس تأیید کنید.",
                                  "unconfirmed": unconfirmed})
    billing.consume(getattr(acc, "account_id", None), "analyses_per_month")
    try:
        result = analyze_imported_model(model)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(422, f"Cannot analyse this model: {exc}") from exc
    state = _state(model, "analyzed", result)
    state["state_file_id"] = _save_state(files, pid, acc, state)
    return state


@router.get("/latest")
def latest_import(project_id: str, acc: Annotated[AuthenticatedAccount, Depends(get_current_account)],
                  registry=Depends(get_file_registry_service), files=Depends(get_file_ingestion_service),
                  access=Depends(get_project_access_service)) -> dict[str, Any]:
    pid = _access(project_id, acc, access)
    recs = [r for r in registry.list_project_files(pid) if r.filename.endswith(STATE_SUFFIX)]
    if not recs:
        return {"state": None}
    rec = max(recs, key=lambda r: r.created_at)
    _, content = files.get_file_content(pid, rec.id)
    try:
        state = json.loads(content.decode("utf-8"))
    except ValueError:
        return {"state": None}
    state["state_file_id"] = str(rec.id)
    return {"state": state}
