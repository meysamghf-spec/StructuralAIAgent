"""Full section optimization (async jobs) — /api/v1/optimization-full.

Sources: the chat/Model-page 3D frame (inputs or the project's latest complete frame) or an imported model
(ETABS/SAP via /model-import).  Section lists, bar diameters, materials and member types come from chat text or an
attached PDF / Excel file; anything missing is assumed (reported back).  Deterministic: no LLM involved.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.application import frame3d_limits as fl
from app.api.deps import get_conversation_service, get_current_account, get_project_access_service
from app.application.billing import service as billing
from app.domain.models.user import AuthenticatedAccount

router = APIRouter(prefix="/optimization-full", tags=["optimization-full"])
MAX_SECTION_FILE = 15 * 1024 * 1024


class SectionTextRequest(BaseModel):
    text: str = Field(default="", max_length=50_000)


class OptimizationJobRequest(BaseModel):
    source: str = Field(default="frame", description="frame | model")
    inputs: dict[str, Any] | None = None
    model: dict[str, Any] | None = None
    project_id: str | None = None
    section_text: str = Field(default="", max_length=50_000)
    lists: dict[str, Any] | None = None
    options: dict[str, Any] = Field(default_factory=dict)
    assume_defaults: bool = True


def _frame_model(body: OptimizationJobRequest, acc, conv, access, out_inputs: dict[str, Any] | None = None) -> tuple[dict[str, Any], list[str]]:
    from app.application import frame3d_chat_analysis as f3
    from app.application.optimization_full.builder import model_from_frame

    inputs = body.inputs
    assumed_notes: list[str] = []
    if not inputs:
        if body.project_id:
            from uuid import UUID

            try:
                access.require_project(UUID(body.project_id), acc)
            except ValueError as exc:
                raise HTTPException(422, "invalid project_id") from exc
        from app.api.routes.autocad import latest_frame_inputs
        from app.application.optimization_full.model_resolver import resolve_project_frame

        inputs = latest_frame_inputs(conv, acc, body.project_id) if body.project_id else None
        if inputs:
            from app.application.optimization_full.model_resolver import LABELS

            assumed_notes = [f"منبع مدل: {LABELS['frame']['fa']}"]
        if not inputs:
            # Whole project chat history (runs + frame descriptions), else the documented defaults — never "no model".
            res = resolve_project_frame(conv, acc, body.project_id)
            inputs = res["inputs"]
            assumed_notes = [f"منبع مدل: {res['label']['fa']}", *res["assumptions_fa"]]
    billing.check_frame_size(getattr(acc, "account_id", None), inputs)
    data = {"seismic_code": "IRAN_2800", **inputs}
    inp = f3.inputs_from_dict(data)
    assumed: list[str] = []
    missing = f3.missing_inputs(inp)
    if missing and body.assume_defaults:
        from app.application import frame3d_followup as fu

        assumed = fu.apply_defaults(inp)
        missing = f3.missing_inputs(inp)
    if missing:
        raise HTTPException(422, "missing: " + ", ".join(f3.input_labels(missing, "en")))
    if not fl.within_limits(inp.storeys, inp.bays_x, inp.bays_y, optimisation=True):
        raise HTTPException(422, "optimisation " + fl.limit_text(optimisation=True))
    if out_inputs is not None:
        from dataclasses import asdict

        out_inputs.update({k: v for k, v in asdict(inp).items() if k not in f3.INTERNAL_FIELDS})
    return model_from_frame(inp), assumed_notes + [f"{k} (default)" for k in assumed]


def _limit_warning(inputs: dict[str, Any]) -> dict[str, str] | None:
    """The chat's frame is reported as written; if it is beyond the solver/optimizer limits say so (never silently shrink it)."""
    from app.application.frame3d_limits import MAX_BAYS, MAX_NODES, MAX_OPT_NODES, MAX_STOREYS, node_count

    try:
        s, bx, by = int(inputs["storeys"]), int(inputs["bays_x"]), int(inputs["bays_y"])
    except (KeyError, TypeError, ValueError):
        return None
    n = node_count(s, bx, by)
    if s <= MAX_STOREYS and bx <= MAX_BAYS and by <= MAX_BAYS and n <= MAX_OPT_NODES:
        return None
    return {
        "fa": f"این قاب ({s} طبقه، {bx}×{by} دهانه، {n:,} گره) از حد مجاز بزرگ‌تر است: حداکثر {MAX_BAYS} دهانه در هر جهت، "
              f"{MAX_NODES:,} گره برای تحلیل و {MAX_OPT_NODES:,} گره برای بهینه‌سازی. یک بخش نماینده (مثلاً یک بلوک بین درزهای انقطاع) را مدل کنید.",
        "en": f"This frame ({s} storeys, {bx}x{by} bays, {n:,} nodes) exceeds the limits: max {MAX_BAYS} bays per direction, "
              f"{MAX_NODES:,} nodes for analysis and {MAX_OPT_NODES:,} for optimization. Model a representative block (e.g. between expansion joints).",
    }


@router.get("/project-frame")
def project_frame(project_id: str, acc: Annotated[AuthenticatedAccount, Depends(get_current_account)],
                  conv=Depends(get_conversation_service), access=Depends(get_project_access_service)) -> dict[str, Any]:
    """Geometry of the project's frame from its chat history (same resolver as optimization), defaults filled in.

    Used to pre-fill the Model page form: `from_chat` keys came from the project's chats, `assumed` keys are defaults.
    """
    from uuid import UUID

    from app.application.optimization_full.model_resolver import GEOMETRY, resolve_project_frame

    try:
        access.require_project(UUID(project_id), acc)
    except ValueError as exc:
        raise HTTPException(422, "invalid project_id") from exc
    res = resolve_project_frame(conv, acc, project_id)
    inputs = res["inputs"]
    assumed = list(res["assumed"]) if res["source"] != "default" else list(GEOMETRY)
    return {
        "limit_warning": _limit_warning(inputs),
        "source": res["source"], "label": res["label"], "chat_title": res.get("chat_title"),
        "inputs": {k: v for k, v in inputs.items() if isinstance(v, (int, float, str, bool)) or v is None},
        "from_chat": [k for k in GEOMETRY if k not in assumed], "assumed": assumed,
    }


@router.post("/parse-sections")
def parse_sections(body: SectionTextRequest, acc: Annotated[AuthenticatedAccount, Depends(get_current_account)]) -> dict[str, Any]:
    from app.application.optimization_full.sections import parse_section_lists

    return {"lists": parse_section_lists(body.text)}


@router.post("/parse-sections-file")
async def parse_sections_file(acc: Annotated[AuthenticatedAccount, Depends(get_current_account)],
                              file: Annotated[UploadFile, File()], text: Annotated[str, Form()] = "") -> dict[str, Any]:
    from app.application.optimization_full.sections import extract_text, parse_section_lists

    content = await file.read(MAX_SECTION_FILE + 1)
    if len(content) > MAX_SECTION_FILE:
        raise HTTPException(413, "file too large (max 15 MB)")
    try:
        body = extract_text(file.filename or "list.txt", content)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"lists": parse_section_lists((text + "\n" + body).strip()), "chars": len(body)}


@router.post("/jobs")
def start_job(body: OptimizationJobRequest, acc: Annotated[AuthenticatedAccount, Depends(get_current_account)],
              conv=Depends(get_conversation_service), access=Depends(get_project_access_service)) -> dict[str, Any]:
    from app.application.model_import import review_summary
    from app.application.model_import.common import finalize
    from app.application.optimization_full import jobs
    from app.application.optimization_full.engine import optimize_model
    from app.application.optimization_full.sections import merge_lists, parse_section_lists

    owner = str(getattr(acc, "account_id", "anon"))
    billing.require_feature(getattr(acc, "account_id", None), "optimization")
    if jobs.running_for(owner) >= jobs.MAX_RUNNING_PER_USER:
        raise HTTPException(429, {"en": "Two optimizations are already running.", "fa": "دو بهینه‌سازی در حال اجراست؛ صبر کنید."})
    assumed: list[str] = []
    frame_inputs: dict[str, Any] = {}
    if body.source == "model":
        if not body.model:
            raise HTTPException(422, "model is required for source=model")
        model = finalize(dict(body.model)) if "counts" not in body.model else dict(body.model)
        rev = review_summary(model)
        if not rev["can_analyze"]:
            raise HTTPException(409, {"en": "Resolve the blocking review items of the imported model first.",
                                      "fa": "ابتدا موارد مسدودکننده‌ی بازبینی مدل وارد‌شده را برطرف کنید."})
        from app.application.optimization_full.engine import OptimizationInputError, prepare_model

        try:
            prepare_model(model)
        except OptimizationInputError as exc:
            raise HTTPException(422, {"en": "The imported model cannot be optimized as is.", "fa": str(exc)}) from exc
        if len(model.get("members") or []) > 3000:
            raise HTTPException(422, "model too large for optimization (max 3000 members)")
    else:
        model, assumed = _frame_model(body, acc, conv, access, frame_inputs)
    lists = merge_lists(parse_section_lists(body.section_text) if body.section_text.strip() else None, body.lists)
    billing.consume(getattr(acc, "account_id", None), "analyses_per_month")
    opts = dict(body.options or {})
    opts["time_budget_s"] = min(float(opts.get("time_budget_s") or 120), 900.0)

    def work(progress, cancelled):
        res = optimize_model(model, lists, opts, progress=progress, cancelled=cancelled)
        res["assumed_inputs"] = assumed
        res["lists_used"] = {k: lists.get(k) for k in ("beams", "columns", "braces", "rebar_mm", "materials", "member_types")}
        if frame_inputs and res.get("status") != "cancelled":
            from app.application.optimization_full.chat_run import optimized_frame3d

            opt3d = optimized_frame3d(frame_inputs, res)
            if opt3d:  # re-analysed frame with the optimized sections → applied to the project's model by the page
                res["optimized_frame3d"] = opt3d
                res["original_inputs"] = frame_inputs
        return res

    job = jobs.start(owner, {"source": body.source, "members": len(model["members"])}, work)
    return {"job": jobs.public(job)}


def _own(job_id: str, acc) -> dict[str, Any]:
    from app.application.optimization_full import jobs

    job = jobs.get(job_id)
    if job is None or job.get("owner") != str(getattr(acc, "account_id", "anon")):
        raise HTTPException(404, "job not found")
    return job


@router.get("/jobs/{job_id}")
def job_status(job_id: str, acc: Annotated[AuthenticatedAccount, Depends(get_current_account)]) -> dict[str, Any]:
    from app.application.optimization_full import jobs

    return {"job": jobs.public(_own(job_id, acc))}


@router.post("/jobs/{job_id}/cancel")
def job_cancel(job_id: str, acc: Annotated[AuthenticatedAccount, Depends(get_current_account)]) -> dict[str, Any]:
    from app.application.optimization_full import jobs

    _own(job_id, acc)
    jobs.cancel(job_id)
    return {"ok": True}
